import os
import unicodedata
from typing import Dict, List
from datetime import datetime
import numpy as np
from langchain_openai import OpenAIEmbeddings
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from langchain_core.documents import Document

from .logger import logger
from dotenv import load_dotenv, set_key, dotenv_values
# Load environment variables
load_dotenv()

class MongoDb:
    def __init__(
        self,
        uri: str = os.getenv("MONGO_URI"),
        database_name: str = "django_rag_analytics",
        collection_name: str = "mycollection",
        recreate_collection: bool = False,
    ):      
        if not uri:
            raise ValueError("MongoDB URI is not set in environment variables")
        cleaned_collection_name = clean_filename_for_collection(collection_name)
        self.uri = uri
        self.client = MongoClient(self.uri, server_api=ServerApi("1"))
        self.embedding_model = OpenAIEmbeddings()

        self.ping()  # Check if the connection is successful
        self.database_name = self.client[database_name]

        if recreate_collection:
            if cleaned_collection_name in self.database_name.list_collection_names():
                self.client[database_name].drop_collection(cleaned_collection_name)

        self.collection = self.database_name[cleaned_collection_name]
        logger.info(f"Connected to the collection '{cleaned_collection_name}'")

    def ping(self):
        # Send a ping to confirm a successful connection
        try:
            self.client.admin.command("ping")
            logger.debug(
                "Pinged your deployment. You successfully connected to MongoDB!"
            )
        except Exception as e:
            logger.error(e)

    def collection_exists(self, collection_name: str) -> bool:
        if collection_name in self.database_name.list_collection_names():
            logger.info(f"Collection '{collection_name}' already exists")
            return True
        logger.info(f"Collection '{collection_name}' does not exist")
        return False

    def change_collection(self, collection_name: str):
        self.collection = self.database_name[collection_name]
        logger.info(f"Changed to collection '{collection_name}'")

    def __getattr__(self, name):
        collection = self.__dict__.get('collection', None)
        if collection and hasattr(collection, name):
            return getattr(collection, name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def query(self, query_text: str, top_k: int = 5):
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.embed_query(query_text.lower())

            # Cosine similarity function
            def cosine_similarity(vec1, vec2):
                return np.dot(vec1, vec2) / (
                    np.linalg.norm(vec1) * np.linalg.norm(vec2)
                )

            # Get all documents
            all_documents = list(self.collection.find({}))

            # Calculate scores for each document
            results = []
            for doc in all_documents:
                doc = self.collection.find_one()
                score = cosine_similarity(query_embedding, np.array(doc["embedding"]))
                results.append(
                    {
                        "page": doc["page"],
                        "text": doc["text"],
                        "score": score,
                    }
                )

            # Sort by score and get top_k
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]

        except Exception as e:
            print(f"Errore durante l'esecuzione della query: {e}")
            return []
        
    def query_with_keyword_filter(
        self, query_text: str, top_k: int = 5, keyword_filter: List[str] = None
    ):
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.embed_query(query_text.lower())

            # Cosine similarity function
            def cosine_similarity(vec1, vec2):
                return np.dot(vec1, vec2) / (
                    np.linalg.norm(vec1) * np.linalg.norm(vec2)
                )

            # Get unique pages and their best matching segments
            page_scores = {}  # Dictionary to store best score per page

            # Get all documents
            all_documents = list(self.collection.find({}))

            # Apply keyword filter if provided
            if keyword_filter:
                filtered_documents = [
                    doc
                    for doc in all_documents
                    if any(
                        kw.lower() in doc.get("keywords", []) for kw in keyword_filter
                    )
                ]
                documents_to_process = (
                    filtered_documents if filtered_documents else all_documents
                )
            else:
                documents_to_process = all_documents

            # Process each document
            for doc in documents_to_process:
                page = doc["page"]
                score = cosine_similarity(query_embedding, np.array(doc["embedding"]))

                # Update page_scores if this is a better match for the page
                if page not in page_scores or score > page_scores[page]["score"]:
                    page_scores[page] = {"text": doc["text"], "score": score}

            # Convert to list and sort by score
            results = [
                {"page": page, "text": data["text"], "score": data["score"]}
                for page, data in page_scores.items()
            ]

            # Sort by score and get top_k
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]

        except Exception as e:
            print(f"Errore durante l'esecuzione della query: {e}")
            return []

    def index_chunks(self, chunks: List[Document], doc):
        logger.info(f"Indexing {len(chunks)} chunks for document ID: {doc.id}")

        for chunk in chunks:
            try:
                # Generate embedding for the chunk
                embedding = self.embedding_model.embed_documents([chunk.page_content])[0]

                # Prepare the document to be inserted
                document = {
                    "text": chunk.page_content,
                    "embedding": embedding,  # Convert numpy array to list
                    "page": chunk.metadata.get("page", []),
                    "doc_id": doc.id,
                    "doc_title": doc.title,
                    "doc_size": doc.file.size if doc.file else None,
                    "doc_uploaded_at": doc.uploaded_at,
                    "embedding_model": self.embedding_model.model,
                    "embeddings_created_at": datetime.now(),
                }

                # Insert the document into the collection
                self.collection.insert_one(document)
            except Exception as e:
                logger.error(f"Error indexing chunk: {e}")
                continue

def clean_filename_for_collection(filename: str) -> str:
    # Rimuove i caratteri non alfanumerici e sostituisce gli spazi con underscore
    cleaned_name = "".join(
        char if char.isalnum() or char in ["_", "-"] else "_" for char in filename
    )
    return cleaned_name.strip("_")
# Order files by page number
def sort_files(files: List[str]) -> List[str]:
    def extract_page_number(filename):
        return int(filename.replace("page_", "").replace(".txt", ""))

    return sorted(files, key=extract_page_number)

def clean_text(text):
    """
    Rimuove i caratteri speciali e normalizza il testo.
    """
    # Remove non-printable characters
    text = "".join(char for char in text if char.isprintable())
    # Normalize text
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    # Remove extra whitespaces
    text = " ".join(text.split())
    return text

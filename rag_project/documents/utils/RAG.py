from copy import deepcopy
from datetime import datetime
import os
from openai import OpenAI
from langchain_core.documents import Document
from .vector_db import MongoDb
from .logger import logger

class RAG:
    def __init__(
        self,
        top_k_documents: int = 5,
        mongo_uri: str = None,
        database_name: str = "django_rag_analytics",
        collection_name: str = "mycollection",
        ):
        self.vector_db = MongoDb(uri=mongo_uri, database_name=database_name, collection_name=collection_name)
        self.llm_client = OpenAI()
        self.top_k_documents = top_k_documents

    def answer_question(self, user_query: str,):
        # Step 1: Retrieve relevant documents from the database
        logger.debug(f"Retrieving relevant documents for query: {user_query}")
        relevant_docs = self.vector_db.query(user_query, top_k=self.top_k_documents)
        logger.debug(f"{len(relevant_docs)} results found in knowledge base.")

        # Step 2: Call the LLM with the user query and relevant documents
        mock_response = self._call_llm(user_query=user_query, relevant_docs=relevant_docs)
        # mock_response = "This is a mock response from the assistant based on the user query and relevant documents."

        return mock_response
    
    def _call_llm(self, user_query: str, relevant_docs: list):
        """
        Summarizes the given text using OpenAI's GPT model.

        Args:
            text (str): The text to be summarized.
            model (str): The OpenAI model to use for summarization. Default is "gpt-3.5-turbo".

        Returns:
            str: The summarized text.
        """
        if not user_query:
            return "No content to summarize."

        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OpenAI API key is not set. Please check your environment variables.")

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        if not relevant_docs:
            logger.warning("No relevant documents found for the query.")
            return [{"text": "No relevant documents found for the query."}]

        # Prepare the payload for the OpenAI API
        messages = [{"role": "system", "content": "You are an advanced RAG assistant. Your task is to provide accurate and concise answers based on the provided documents."},
                    {"role": "user", "content": user_query},
                    # You can include relevant documents in the prompt if needed
                    {"role": "user", "content": "Here are some relevant documents to consider:"},
                    {"role": "user", "content": "\n".join([doc['text'] for doc in relevant_docs])}
                ]
        
        logger.debug(f"Calling OpenAI API with messages: {messages}")

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=.4,
            )
        except Exception as e:
            logger.error(f"Error during OpenAI API call: {e}")

        summary = response.choices[0].message.content
        return summary


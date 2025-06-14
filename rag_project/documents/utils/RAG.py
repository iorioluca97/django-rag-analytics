from copy import deepcopy
from datetime import datetime
import os
from openai import OpenAI
from langchain_core.documents import Document
from .vector_db import MongoDb
from .logger import logger
from openai import OpenAI
import yaml

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
    
    def _call_llm(self, user_query: str, relevant_docs: list) -> str:
        if not user_query:
            return "No query provided."

        if not relevant_docs:
            logger.warning("No relevant documents found for the query.")
            return "No relevant documents found for the query."

        try:
            prompt_parts = self._load_prompt_template()

            documents_content = "\n\n".join([doc.get('text', '') for doc in relevant_docs])
            

            messages = [
                {"role": "system", "content": prompt_parts['system']},
                {"role": "user", "content": f"{prompt_parts['user_intro']}\n\n{user_query}"},
                {"role": "user", "content": f"{prompt_parts['document_intro']}\n\n{documents_content}"}
            ]

            logger.debug("Calling OpenAI API with structured prompt.")
            logger.debug(f"Messages: {messages}")
            response = self.llm_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.4
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            return "An error occurred while generating the response."

    def _load_prompt_template(self):
        with open("./rag_project/documents/utils/rag_prompt.yaml", "r") as f:
            prompt_template = yaml.safe_load(f)
        if not prompt_template:
            raise ValueError("Prompt template is empty or not found.")
        return prompt_template
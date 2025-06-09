from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class TextExtractor:
    chunk_size: int = 1000
    chunk_overlap: int = 200

    def extract_text(self, text: str) -> List[Document]:
        """
        Extracts text from a given string and splits it into chunks.

        Args:
            text (str): The input text to be processed.

        Returns:
            List[Document]: A list of Document objects containing the extracted text.
        """
        if not text.strip():
            return []

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        
        return text_splitter.create_documents([text])
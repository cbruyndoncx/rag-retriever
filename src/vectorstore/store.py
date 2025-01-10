"""Vector store management module using Chroma."""

import os
import logging
from typing import List, Tuple, Optional

from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

from src.utils.config import config

logger = logging.getLogger(__name__)

def get_vectorstore_path() -> str:
    """Get the vector store directory path."""
    return os.path.join(os.getcwd(), "chromadb")

class VectorStore:
    """Manage vector storage and retrieval using Chroma."""

    def __init__(self, persist_directory: Optional[str] = None):
        """Initialize vector store."""
        self.persist_directory = persist_directory or get_vectorstore_path()
        logger.debug("Vector store directory: %s", self.persist_directory)
        self.embeddings = self._get_embeddings()
        self._db = None

    def _get_embeddings(self) -> OpenAIEmbeddings:
        """Get OpenAI embeddings instance with configuration."""
        return OpenAIEmbeddings(
            model=config.vector_store["embedding_model"],
            dimensions=config.vector_store["embedding_dimensions"],
        )

    def _get_or_create_db(self, documents: Optional[List[Document]] = None) -> Chroma:
        """Get existing vector store or create a new one."""
        if self._db is not None:
            logger.debug("Using existing database instance")
            return self._db

        # Create the directory if it doesn't exist
        os.makedirs(self.persist_directory, exist_ok=True)
        logger.debug("Created directory: %s", self.persist_directory)

        # Load existing DB if it exists
        if os.path.exists(self.persist_directory) and os.listdir(self.persist_directory):
            logger.debug("Loading existing database from: %s", self.persist_directory)
            self._db = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings,
                collection_metadata={"hnsw:space": "cosine"}
            )
            # Add new documents if provided
            if documents is not None:
                logger.debug("Adding %d documents to existing database", len(documents))
                self._db.add_documents(documents)
            return self._db

        # Create new DB with documents
        if documents is None:
            logger.error("No existing database found and no documents provided")
            raise ValueError(
                "No existing vector store found and no documents provided to create one."
            )

        logger.debug("Creating new database with %d documents", len(documents))
        self._db = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            persist_directory=self.persist_directory,
            collection_metadata={"hnsw:space": "cosine"}
        )
        return self._db

    def add_documents(self, documents: List[Document]) -> int:
        """Add documents to the vector store."""
        try:
            # Split documents into chunks using configured values
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=config.content["chunk_size"],
                chunk_overlap=config.content["chunk_overlap"],
                length_function=len,
            )
            logger.debug("Splitting documents with chunk_size=%d, chunk_overlap=%d", 
                       config.content["chunk_size"], config.content["chunk_overlap"])
            splits = text_splitter.split_documents(documents)
            logger.debug("Split %d documents into %d chunks", len(documents), len(splits))

            # Try to get existing DB
            logger.debug("Attempting to add %d chunks", len(splits))
            db = self._get_or_create_db()
            db.add_documents(splits)
            return len(splits)
        except ValueError:
            # No existing DB, create new one with documents
            logger.debug("Creating new database with documents")
            db = self._get_or_create_db(splits)
            return len(splits)

    def search(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.2,
    ) -> List[Tuple[Document, float]]:
        """Search for documents similar to query."""
        db = self._get_or_create_db()
        results = db.similarity_search_with_relevance_scores(
            query,
            k=limit,
            score_threshold=score_threshold,
        )
        return results

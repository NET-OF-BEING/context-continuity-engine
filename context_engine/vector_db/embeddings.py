"""
Embedding Store Module

Manages vector embeddings for semantic similarity search.
"""

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class EmbeddingStore:
    """Manages vector embeddings for semantic context matching."""

    def __init__(self, persist_directory: str, collection_name: str = "context_embeddings",
                 model_name: str = "all-MiniLM-L6-v2"):
        """Initialize the embedding store.

        Args:
            persist_directory: Directory for ChromaDB persistence
            collection_name: Name of the collection
            model_name: SentenceTransformer model to use
        """
        self.persist_dir = Path(persist_directory)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.collection_name = collection_name
        self.model_name = model_name

        # Initialize SentenceTransformer
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)

        # Initialize ChromaDB
        self.client = chromadb.Client(Settings(
            persist_directory=str(self.persist_dir),
            anonymized_telemetry=False
        ))

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

        logger.info(f"Embedding store initialized with {self.collection.count()} embeddings")

    def add_text(self, text: str, metadata: Dict[str, Any], doc_id: Optional[str] = None) -> str:
        """Add text and generate embedding.

        Args:
            text: Text to embed
            metadata: Associated metadata
            doc_id: Optional document ID (auto-generated if not provided)

        Returns:
            Document ID
        """
        if not text or not text.strip():
            logger.warning("Empty text provided, skipping embedding")
            return None

        # Generate embedding
        embedding = self.model.encode(text).tolist()

        # Generate ID if not provided
        if doc_id is None:
            doc_id = f"doc_{self.collection.count() + 1}"

        # Add to collection
        self.collection.add(
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata],
            ids=[doc_id]
        )

        return doc_id

    def add_batch(self, texts: List[str], metadatas: List[Dict[str, Any]],
                  doc_ids: Optional[List[str]] = None) -> List[str]:
        """Add multiple texts in batch.

        Args:
            texts: List of texts to embed
            metadatas: List of metadata dicts
            doc_ids: Optional list of document IDs

        Returns:
            List of document IDs
        """
        if not texts:
            return []

        # Filter out empty texts
        valid_items = [(t, m, i) for t, m, i in zip(
            texts,
            metadatas,
            doc_ids or [None] * len(texts)
        ) if t and t.strip()]

        if not valid_items:
            logger.warning("No valid texts to embed")
            return []

        texts, metadatas, doc_ids = zip(*valid_items)

        # Generate embeddings
        embeddings = self.model.encode(list(texts)).tolist()

        # Generate IDs if not provided
        if doc_ids[0] is None:
            start_id = self.collection.count() + 1
            doc_ids = [f"doc_{i}" for i in range(start_id, start_id + len(texts))]

        # Add to collection
        self.collection.add(
            embeddings=embeddings,
            documents=list(texts),
            metadatas=list(metadatas),
            ids=list(doc_ids)
        )

        return list(doc_ids)

    def search_similar(self, query_text: str, n_results: int = 10,
                      where: Optional[Dict[str, Any]] = None,
                      threshold: float = 0.0) -> List[Dict[str, Any]]:
        """Search for semantically similar content.

        Args:
            query_text: Query text
            n_results: Number of results to return
            where: Metadata filter conditions
            threshold: Minimum similarity threshold (0.0 - 1.0)

        Returns:
            List of similar documents with metadata and scores
        """
        if not query_text or not query_text.strip():
            return []

        # Generate query embedding
        query_embedding = self.model.encode(query_text).tolist()

        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )

        # Format results
        formatted_results = []
        if results['ids'] and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                # Convert distance to similarity score (cosine)
                distance = results['distances'][0][i] if results['distances'] else 0
                similarity = 1 - distance  # ChromaDB returns cosine distance

                if similarity < threshold:
                    continue

                formatted_results.append({
                    'id': doc_id,
                    'text': results['documents'][0][i] if results['documents'] else None,
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'similarity': similarity
                })

        return formatted_results

    def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID.

        Args:
            doc_id: Document ID

        Returns:
            Document data or None
        """
        results = self.collection.get(ids=[doc_id])

        if results['ids']:
            return {
                'id': results['ids'][0],
                'text': results['documents'][0] if results['documents'] else None,
                'metadata': results['metadatas'][0] if results['metadatas'] else {}
            }

        return None

    def update_metadata(self, doc_id: str, metadata: Dict[str, Any]):
        """Update metadata for a document.

        Args:
            doc_id: Document ID
            metadata: New metadata
        """
        self.collection.update(
            ids=[doc_id],
            metadatas=[metadata]
        )

    def delete(self, doc_id: str):
        """Delete a document.

        Args:
            doc_id: Document ID
        """
        self.collection.delete(ids=[doc_id])

    def delete_batch(self, doc_ids: List[str]):
        """Delete multiple documents.

        Args:
            doc_ids: List of document IDs
        """
        if doc_ids:
            self.collection.delete(ids=doc_ids)

    def count(self) -> int:
        """Get total number of embeddings.

        Returns:
            Count of embeddings
        """
        return self.collection.count()

    def clear(self):
        """Clear all embeddings from the collection."""
        # Delete and recreate collection
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def find_related_contexts(self, current_context: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Find contexts related to the current activity.

        Args:
            current_context: Description of current context
            n_results: Number of related contexts to find

        Returns:
            List of related contexts with similarity scores
        """
        return self.search_similar(
            query_text=current_context,
            n_results=n_results,
            threshold=0.5  # Only return reasonably similar contexts
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the embedding store.

        Returns:
            Dictionary of statistics
        """
        return {
            'total_embeddings': self.count(),
            'collection_name': self.collection_name,
            'model_name': self.model_name,
            'persist_directory': str(self.persist_dir)
        }

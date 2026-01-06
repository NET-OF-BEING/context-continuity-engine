"""
Context Continuity Engine

Maintains awareness across all devices and applications by tracking
context, predicting needs, and surfacing relevant information.
"""

__version__ = "0.1.0"
__author__ = "DarkReach Labs"

from .storage.activity_db import ActivityDatabase
from .vector_db.embeddings import EmbeddingStore
from .graph.temporal_graph import TemporalGraph
from .prediction.context_predictor import ContextPredictor

__all__ = [
    "ActivityDatabase",
    "EmbeddingStore",
    "TemporalGraph",
    "ContextPredictor",
]

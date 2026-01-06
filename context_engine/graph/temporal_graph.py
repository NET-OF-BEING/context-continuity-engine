"""
Temporal Knowledge Graph Module

Builds and maintains a graph of activities and their relationships over time.
"""

import networkx as nx
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import pickle
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class TemporalGraph:
    """Manages temporal relationships between activities and contexts."""

    def __init__(self, persist_path: Optional[str] = None, max_nodes: int = 10000,
                 decay_factor: float = 0.95):
        """Initialize the temporal graph.

        Args:
            persist_path: Path to save/load graph
            max_nodes: Maximum number of nodes to maintain
            decay_factor: Decay factor for connection strength over time
        """
        self.graph = nx.DiGraph()
        self.persist_path = Path(persist_path) if persist_path else None
        self.max_nodes = max_nodes
        self.decay_factor = decay_factor

        # Load existing graph if available
        if self.persist_path and self.persist_path.exists():
            self.load()

        logger.info(f"Temporal graph initialized with {self.graph.number_of_nodes()} nodes")

    def add_activity_node(self, activity_id: str, activity_type: str,
                         timestamp: datetime, **attributes):
        """Add an activity node to the graph.

        Args:
            activity_id: Unique activity identifier
            activity_type: Type of activity
            timestamp: When the activity occurred
            **attributes: Additional node attributes
        """
        self.graph.add_node(
            activity_id,
            node_type='activity',
            activity_type=activity_type,
            timestamp=timestamp,
            **attributes
        )

        # Prune if exceeds max nodes
        if self.graph.number_of_nodes() > self.max_nodes:
            self._prune_old_nodes()

    def add_context_node(self, context_id: str, context_name: str, **attributes):
        """Add a context node to the graph.

        Args:
            context_id: Unique context identifier
            context_name: Name of the context
            **attributes: Additional node attributes
        """
        self.graph.add_node(
            context_id,
            node_type='context',
            context_name=context_name,
            created_at=datetime.now(),
            **attributes
        )

    def add_temporal_edge(self, from_node: str, to_node: str, relationship: str,
                         strength: float = 1.0, **attributes):
        """Add or update an edge between nodes.

        Args:
            from_node: Source node ID
            to_node: Target node ID
            relationship: Type of relationship
            strength: Strength of the relationship (0.0 - 1.0)
            **attributes: Additional edge attributes
        """
        if self.graph.has_edge(from_node, to_node):
            # Update existing edge
            edge_data = self.graph[from_node][to_node]
            edge_data['strength'] = min(1.0, edge_data.get('strength', 0) + strength)
            edge_data['last_updated'] = datetime.now()
            edge_data.update(attributes)
        else:
            # Create new edge
            self.graph.add_edge(
                from_node,
                to_node,
                relationship=relationship,
                strength=strength,
                created_at=datetime.now(),
                last_updated=datetime.now(),
                **attributes
            )

    def connect_sequential_activities(self, activity_id1: str, activity_id2: str,
                                      time_delta: timedelta):
        """Connect two sequential activities.

        Args:
            activity_id1: First activity ID
            activity_id2: Second activity ID (occurs after first)
            time_delta: Time between activities
        """
        # Stronger connection for activities closer in time
        strength = 1.0 / (1.0 + time_delta.total_seconds() / 3600)  # Decay over hours

        self.add_temporal_edge(
            activity_id1,
            activity_id2,
            relationship='followed_by',
            strength=strength,
            time_delta=time_delta.total_seconds()
        )

    def link_activity_to_context(self, activity_id: str, context_id: str,
                                confidence: float = 1.0):
        """Link an activity to a context.

        Args:
            activity_id: Activity ID
            context_id: Context ID
            confidence: Confidence of the association
        """
        self.add_temporal_edge(
            activity_id,
            context_id,
            relationship='belongs_to',
            strength=confidence
        )

    def get_related_activities(self, activity_id: str, max_depth: int = 2,
                              min_strength: float = 0.1) -> List[Dict[str, Any]]:
        """Get activities related to the given activity.

        Args:
            activity_id: Activity ID to find relations for
            max_depth: Maximum graph depth to traverse
            min_strength: Minimum edge strength to consider

        Returns:
            List of related activities with relationship info
        """
        if activity_id not in self.graph:
            return []

        related = []

        # BFS traversal with depth limit
        visited = {activity_id}
        queue = [(activity_id, 0, 1.0)]  # (node, depth, cumulative_strength)

        while queue:
            current_node, depth, cumulative_strength = queue.pop(0)

            if depth >= max_depth:
                continue

            # Get outgoing edges
            for neighbor in self.graph.neighbors(current_node):
                if neighbor in visited:
                    continue

                edge_data = self.graph[current_node][neighbor]
                edge_strength = edge_data.get('strength', 0)

                if edge_strength < min_strength:
                    continue

                new_strength = cumulative_strength * edge_strength

                node_data = self.graph.nodes[neighbor]

                if node_data.get('node_type') == 'activity':
                    related.append({
                        'activity_id': neighbor,
                        'relationship': edge_data.get('relationship'),
                        'strength': new_strength,
                        'depth': depth + 1,
                        'activity_type': node_data.get('activity_type'),
                        'timestamp': node_data.get('timestamp')
                    })

                visited.add(neighbor)
                queue.append((neighbor, depth + 1, new_strength))

        # Sort by strength
        related.sort(key=lambda x: x['strength'], reverse=True)

        return related

    def get_context_activities(self, context_id: str) -> List[str]:
        """Get all activities associated with a context.

        Args:
            context_id: Context ID

        Returns:
            List of activity IDs
        """
        if context_id not in self.graph:
            return []

        # Find all incoming edges from activities
        activities = []
        for predecessor in self.graph.predecessors(context_id):
            edge_data = self.graph[predecessor][context_id]
            if edge_data.get('relationship') == 'belongs_to':
                activities.append(predecessor)

        return activities

    def predict_next_activities(self, current_activity_id: str,
                               top_k: int = 5) -> List[Dict[str, Any]]:
        """Predict likely next activities based on historical patterns.

        Args:
            current_activity_id: Current activity ID
            top_k: Number of predictions to return

        Returns:
            List of predicted activities with probabilities
        """
        if current_activity_id not in self.graph:
            return []

        predictions = []

        # Get outgoing 'followed_by' edges
        for neighbor in self.graph.neighbors(current_activity_id):
            edge_data = self.graph[current_activity_id][neighbor]

            if edge_data.get('relationship') == 'followed_by':
                node_data = self.graph.nodes[neighbor]

                predictions.append({
                    'activity_id': neighbor,
                    'probability': edge_data.get('strength', 0),
                    'activity_type': node_data.get('activity_type'),
                    'attributes': {k: v for k, v in node_data.items()
                                 if k not in ['node_type', 'activity_type', 'timestamp']}
                })

        # Sort by probability
        predictions.sort(key=lambda x: x['probability'], reverse=True)

        return predictions[:top_k]

    def decay_edges(self, decay_rate: Optional[float] = None):
        """Apply time-based decay to edge strengths.

        Args:
            decay_rate: Decay rate to apply (uses instance default if None)
        """
        decay_rate = decay_rate or self.decay_factor

        for u, v, data in self.graph.edges(data=True):
            current_strength = data.get('strength', 1.0)
            data['strength'] = current_strength * decay_rate

        # Remove very weak edges
        to_remove = [(u, v) for u, v, data in self.graph.edges(data=True)
                    if data.get('strength', 0) < 0.1]

        self.graph.remove_edges_from(to_remove)
        logger.info(f"Decayed edges, removed {len(to_remove)} weak connections")

    def _prune_old_nodes(self):
        """Remove oldest nodes to maintain max_nodes limit."""
        # Get nodes with timestamps
        timestamped_nodes = [
            (node_id, data.get('timestamp', data.get('created_at')))
            for node_id, data in self.graph.nodes(data=True)
            if data.get('timestamp') or data.get('created_at')
        ]

        if not timestamped_nodes:
            return

        # Sort by timestamp (oldest first)
        timestamped_nodes.sort(key=lambda x: x[1] if x[1] else datetime.min)

        # Remove oldest 10% when pruning
        num_to_remove = max(1, int(self.max_nodes * 0.1))
        to_remove = [node_id for node_id, _ in timestamped_nodes[:num_to_remove]]

        self.graph.remove_nodes_from(to_remove)
        logger.info(f"Pruned {len(to_remove)} old nodes")

    def save(self):
        """Save graph to disk."""
        if not self.persist_path:
            logger.warning("No persist_path set, cannot save graph")
            return

        self.persist_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.persist_path, 'wb') as f:
            pickle.dump(self.graph, f)

        logger.info(f"Graph saved to {self.persist_path}")

    def load(self):
        """Load graph from disk."""
        if not self.persist_path or not self.persist_path.exists():
            logger.warning("No graph file to load")
            return

        with open(self.persist_path, 'rb') as f:
            self.graph = pickle.load(f)

        logger.info(f"Graph loaded from {self.persist_path}")

    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics.

        Returns:
            Dictionary of statistics
        """
        activity_nodes = sum(1 for _, data in self.graph.nodes(data=True)
                           if data.get('node_type') == 'activity')
        context_nodes = sum(1 for _, data in self.graph.nodes(data=True)
                          if data.get('node_type') == 'context')

        return {
            'total_nodes': self.graph.number_of_nodes(),
            'total_edges': self.graph.number_of_edges(),
            'activity_nodes': activity_nodes,
            'context_nodes': context_nodes,
            'max_nodes': self.max_nodes,
            'decay_factor': self.decay_factor
        }

"""
Context Prediction Engine

Predicts and surfaces relevant context based on current activity.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import logging
from collections import Counter

logger = logging.getLogger(__name__)


class ContextPredictor:
    """Predicts relevant context based on current and historical activities."""

    def __init__(self, activity_db, embedding_store, temporal_graph,
                 prediction_window: int = 3600, min_confidence: float = 0.6):
        """Initialize the context predictor.

        Args:
            activity_db: ActivityDatabase instance
            embedding_store: EmbeddingStore instance
            temporal_graph: TemporalGraph instance
            prediction_window: Time window in seconds for predictions
            min_confidence: Minimum confidence threshold for predictions
        """
        self.db = activity_db
        self.embeddings = embedding_store
        self.graph = temporal_graph
        self.prediction_window = prediction_window
        self.min_confidence = min_confidence

    def predict_context(self, current_activity: Dict[str, Any],
                       max_results: int = 10) -> List[Dict[str, Any]]:
        """Predict relevant context for the current activity.

        Args:
            current_activity: Current activity data
            max_results: Maximum number of predictions to return

        Returns:
            List of predicted contexts with confidence scores
        """
        predictions = []

        # Build context description from current activity
        context_description = self._build_context_description(current_activity)

        # 1. Semantic similarity search
        semantic_predictions = self._predict_from_semantics(
            context_description,
            n_results=max_results
        )
        predictions.extend(semantic_predictions)

        # 2. Temporal graph predictions
        if 'activity_id' in current_activity:
            graph_predictions = self._predict_from_graph(
                current_activity['activity_id'],
                top_k=max_results
            )
            predictions.extend(graph_predictions)

        # 3. Time-of-day patterns
        temporal_predictions = self._predict_from_time_patterns(
            current_activity,
            n_results=max_results
        )
        predictions.extend(temporal_predictions)

        # 4. Recent context continuation
        continuation_predictions = self._predict_from_recent_context(
            n_results=max_results
        )
        predictions.extend(continuation_predictions)

        # Deduplicate and rank
        ranked_predictions = self._rank_and_deduplicate(
            predictions,
            max_results=max_results
        )

        # Filter by confidence
        filtered_predictions = [
            p for p in ranked_predictions
            if p.get('confidence', 0) >= self.min_confidence
        ]

        logger.info(f"Generated {len(filtered_predictions)} context predictions")

        return filtered_predictions

    def _build_context_description(self, activity: Dict[str, Any]) -> str:
        """Build a text description of the activity for embedding.

        Args:
            activity: Activity data

        Returns:
            Text description
        """
        parts = []

        if activity.get('app_name'):
            parts.append(f"Application: {activity['app_name']}")

        if activity.get('window_title'):
            parts.append(f"Window: {activity['window_title']}")

        if activity.get('file_path'):
            parts.append(f"File: {activity['file_path']}")

        if activity.get('url'):
            parts.append(f"URL: {activity['url']}")

        return " | ".join(parts) if parts else "Current activity"

    def _predict_from_semantics(self, context_description: str,
                                n_results: int = 10) -> List[Dict[str, Any]]:
        """Predict based on semantic similarity.

        Args:
            context_description: Description of current context
            n_results: Number of results

        Returns:
            List of predictions
        """
        similar_contexts = self.embeddings.search_similar(
            query_text=context_description,
            n_results=n_results,
            threshold=0.5
        )

        predictions = []
        for result in similar_contexts:
            predictions.append({
                'type': 'semantic',
                'confidence': result['similarity'],
                'data': result['metadata'],
                'text': result['text'],
                'reason': f"Semantically similar (score: {result['similarity']:.2f})"
            })

        return predictions

    def _predict_from_graph(self, activity_id: str,
                           top_k: int = 5) -> List[Dict[str, Any]]:
        """Predict based on temporal graph patterns.

        Args:
            activity_id: Current activity ID
            top_k: Number of predictions

        Returns:
            List of predictions
        """
        next_activities = self.graph.predict_next_activities(
            activity_id,
            top_k=top_k
        )

        predictions = []
        for prediction in next_activities:
            predictions.append({
                'type': 'graph',
                'confidence': prediction['probability'],
                'data': prediction['attributes'],
                'activity_type': prediction.get('activity_type'),
                'reason': f"Historically follows current activity ({prediction['probability']:.2f})"
            })

        return predictions

    def _predict_from_time_patterns(self, current_activity: Dict[str, Any],
                                    n_results: int = 5) -> List[Dict[str, Any]]:
        """Predict based on time-of-day patterns.

        Args:
            current_activity: Current activity
            n_results: Number of results

        Returns:
            List of predictions
        """
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()

        # Get activities from same time window in the past
        recent_activities = self.db.get_recent_activities(
            limit=1000,
            hours=24 * 7  # Last week
        )

        # Filter for similar time window
        time_window_activities = []
        for activity in recent_activities:
            activity_time = datetime.fromisoformat(activity['timestamp'])
            if (abs(activity_time.hour - hour) <= 1 and
                activity_time.weekday() == weekday):
                time_window_activities.append(activity)

        # Count most common activities
        activity_counter = Counter()
        for activity in time_window_activities[:n_results * 3]:
            key = (activity.get('app_name'), activity.get('window_title'))
            activity_counter[key] += 1

        predictions = []
        total_count = sum(activity_counter.values())

        for (app_name, window_title), count in activity_counter.most_common(n_results):
            confidence = count / total_count if total_count > 0 else 0

            predictions.append({
                'type': 'temporal_pattern',
                'confidence': confidence,
                'data': {
                    'app_name': app_name,
                    'window_title': window_title
                },
                'reason': f"Common activity at this time ({count} occurrences)"
            })

        return predictions

    def _predict_from_recent_context(self, n_results: int = 5) -> List[Dict[str, Any]]:
        """Predict based on recent context continuation.

        Args:
            n_results: Number of results

        Returns:
            List of predictions
        """
        # Get very recent activities (last hour)
        recent = self.db.get_recent_activities(
            limit=20,
            hours=1
        )

        if not recent:
            return []

        # Count apps/files being worked on
        app_counter = Counter()
        file_counter = Counter()

        for activity in recent:
            if activity.get('app_name'):
                app_counter[activity['app_name']] += 1
            if activity.get('file_path'):
                file_counter[activity['file_path']] += 1

        predictions = []

        # Predict continuation with most used apps
        for app_name, count in app_counter.most_common(n_results):
            confidence = min(0.9, count / len(recent))

            predictions.append({
                'type': 'context_continuation',
                'confidence': confidence,
                'data': {'app_name': app_name},
                'reason': f"Recent focus ({count} recent activities)"
            })

        # Predict continuation with recently accessed files
        for file_path, count in file_counter.most_common(n_results):
            confidence = min(0.9, count / len(recent))

            predictions.append({
                'type': 'context_continuation',
                'confidence': confidence,
                'data': {'file_path': file_path},
                'reason': f"Recently accessed ({count} times)"
            })

        return predictions

    def _rank_and_deduplicate(self, predictions: List[Dict[str, Any]],
                              max_results: int = 10) -> List[Dict[str, Any]]:
        """Rank predictions and remove duplicates.

        Args:
            predictions: List of predictions
            max_results: Maximum results to return

        Returns:
            Ranked and deduplicated predictions
        """
        # Merge duplicate predictions
        merged = {}

        for pred in predictions:
            # Create a key for deduplication
            data = pred.get('data', {})
            key = tuple(sorted(data.items()))

            if key in merged:
                # Average the confidence scores
                existing = merged[key]
                count = existing.get('_count', 1)
                existing['confidence'] = (
                    (existing['confidence'] * count + pred['confidence']) /
                    (count + 1)
                )
                existing['_count'] = count + 1

                # Combine reasons
                if pred['reason'] not in existing['reason']:
                    existing['reason'] += f"; {pred['reason']}"
            else:
                pred['_count'] = 1
                merged[key] = pred

        # Sort by confidence
        ranked = sorted(
            merged.values(),
            key=lambda x: x['confidence'],
            reverse=True
        )

        # Remove internal fields
        for pred in ranked:
            pred.pop('_count', None)

        return ranked[:max_results]

    def get_context_suggestions(self, current_activity: Dict[str, Any]) -> Dict[str, Any]:
        """Get actionable context suggestions.

        Args:
            current_activity: Current activity data

        Returns:
            Dictionary of suggestions organized by type
        """
        predictions = self.predict_context(current_activity, max_results=20)

        suggestions = {
            'related_files': [],
            'related_apps': [],
            'related_contexts': [],
            'next_actions': []
        }

        for pred in predictions:
            data = pred.get('data', {})

            if data.get('file_path'):
                suggestions['related_files'].append({
                    'file_path': data['file_path'],
                    'confidence': pred['confidence'],
                    'reason': pred['reason']
                })

            if data.get('app_name'):
                suggestions['related_apps'].append({
                    'app_name': data['app_name'],
                    'confidence': pred['confidence'],
                    'reason': pred['reason']
                })

            if pred['type'] == 'graph':
                suggestions['next_actions'].append({
                    'activity_type': pred.get('activity_type'),
                    'data': data,
                    'confidence': pred['confidence'],
                    'reason': pred['reason']
                })

        # Deduplicate
        for key in suggestions:
            seen = set()
            unique = []
            for item in suggestions[key]:
                item_key = tuple(sorted(item.items()))
                if item_key not in seen:
                    seen.add(item_key)
                    unique.append(item)
            suggestions[key] = unique[:5]  # Top 5 per category

        return suggestions

#!/usr/bin/env python3
"""
Context Continuity Engine Daemon

Main daemon that coordinates all components.
"""

import sys
import time
import signal
import logging
from pathlib import Path
from datetime import datetime
import yaml

# Add context_engine to path
sys.path.insert(0, str(Path(__file__).parent))

from context_engine.storage.activity_db import ActivityDatabase
from context_engine.vector_db.embeddings import EmbeddingStore
from context_engine.graph.temporal_graph import TemporalGraph
from context_engine.prediction.context_predictor import ContextPredictor
from context_engine.privacy.privacy_filter import PrivacyFilter
from context_engine.monitors.activity_monitor import ActivityMonitor


class ContextEngine:
    """Main Context Continuity Engine."""

    def __init__(self, config_path: str = "config/default_config.yaml"):
        """Initialize the engine.

        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Setup logging
        self._setup_logging()

        logger = logging.getLogger(__name__)
        logger.info("Initializing Context Continuity Engine")

        # Initialize components
        self.db = ActivityDatabase(
            self.config['storage']['database_path']
        )

        self.embeddings = EmbeddingStore(
            persist_directory="data/embeddings",
            collection_name=self.config['vector_db']['collection_name'],
            model_name=self.config['vector_db']['model']
        )

        self.graph = TemporalGraph(
            persist_path="data/temporal_graph.pkl",
            max_nodes=self.config['graph']['max_nodes'],
            decay_factor=self.config['graph']['decay_factor']
        )

        self.predictor = ContextPredictor(
            self.db,
            self.embeddings,
            self.graph,
            prediction_window=self.config['prediction']['prediction_window'],
            min_confidence=self.config['prediction']['min_confidence']
        )

        self.privacy_filter = PrivacyFilter(
            self.config['privacy']
        )

        self.monitor = ActivityMonitor(
            self.config['monitoring'],
            activity_callback=self._handle_activity
        )

        self.running = False

        # Activity counter
        self.activity_count = 0
        self.last_save_time = datetime.now()

        logger.info("Context Continuity Engine initialized successfully")

    def _setup_logging(self):
        """Setup logging configuration."""
        log_config = self.config.get('logging', {})
        log_level = log_config.get('level', 'INFO')
        log_file = log_config.get('file', 'logs/context_engine.log')

        # Create logs directory
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )

    def _handle_activity(self, activity: dict):
        """Handle incoming activity event.

        Args:
            activity: Activity data
        """
        logger = logging.getLogger(__name__)

        try:
            # Check privacy filter
            if not self.privacy_filter.should_track_activity(activity):
                logger.debug(f"Activity blocked by privacy filter")
                return

            # Sanitize activity
            activity = self.privacy_filter.sanitize_activity(activity)

            # Record in database
            activity_id = self.db.record_activity(**activity)

            if not activity_id:
                return

            self.activity_count += 1

            # Build context description for embedding
            context_text = self._build_context_text(activity)

            # Add to vector store
            if context_text:
                self.embeddings.add_text(
                    text=context_text,
                    metadata={
                        'activity_id': activity_id,
                        'timestamp': datetime.now().isoformat(),
                        **activity
                    },
                    doc_id=f"activity_{activity_id}"
                )

            # Add to temporal graph
            activity_type = activity.get('activity_type', 'unknown')
            # Remove activity_type from dict to avoid duplicate keyword argument
            graph_attrs = {k: v for k, v in activity.items() if k != 'activity_type'}
            self.graph.add_activity_node(
                activity_id=f"activity_{activity_id}",
                activity_type=activity_type,
                timestamp=datetime.now(),
                **graph_attrs
            )

            # Get predictions for current activity
            if self.config['prediction']['enabled']:
                predictions = self.predictor.predict_context(activity, max_results=5)

                if predictions:
                    logger.info(f"Context predictions: {len(predictions)}")
                    for pred in predictions[:3]:
                        logger.debug(f"  - {pred.get('reason')} (conf: {pred.get('confidence', 0):.2f})")

            # Periodic save
            if self.activity_count % 10 == 0:
                self._periodic_save()

        except Exception as e:
            logger.error(f"Error handling activity: {e}", exc_info=True)

    def _build_context_text(self, activity: dict) -> str:
        """Build text description of activity for embedding.

        Args:
            activity: Activity data

        Returns:
            Text description
        """
        parts = []

        activity_type = activity.get('activity_type', 'activity')
        parts.append(f"Activity: {activity_type}")

        if activity.get('app_name'):
            parts.append(f"App: {activity['app_name']}")

        if activity.get('window_title'):
            parts.append(f"Window: {activity['window_title']}")

        if activity.get('file_path'):
            file_path = Path(activity['file_path'])
            parts.append(f"File: {file_path.name} in {file_path.parent}")

        return " | ".join(parts)

    def _periodic_save(self):
        """Periodic save of graph and cleanup."""
        logger = logging.getLogger(__name__)

        try:
            # Save graph
            self.graph.save()

            # Apply edge decay
            if self.config['graph']['enabled']:
                self.graph.decay_edges()

            # Cleanup old data
            if self.config['storage']['auto_cleanup']:
                retention_days = self.config['storage']['retention_days']
                deleted = self.db.cleanup_old_data(days=retention_days)

                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} old activity records")

            self.last_save_time = datetime.now()

        except Exception as e:
            logger.error(f"Error in periodic save: {e}")

    def start(self):
        """Start the engine."""
        logger = logging.getLogger(__name__)
        logger.info("Starting Context Continuity Engine")

        self.running = True

        # Start monitoring
        if self.config['monitoring']['enabled']:
            self.monitor.start()

        # Main loop
        try:
            while self.running:
                time.sleep(60)  # Wake up every minute

                # Periodic tasks
                if (datetime.now() - self.last_save_time).total_seconds() > 300:
                    self._periodic_save()

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self.stop()

    def stop(self):
        """Stop the engine."""
        logger = logging.getLogger(__name__)
        logger.info("Stopping Context Continuity Engine")

        self.running = False

        # Stop monitoring
        self.monitor.stop()

        # Final save
        self._periodic_save()

        logger.info("Context Continuity Engine stopped")

    def get_stats(self) -> dict:
        """Get engine statistics.

        Returns:
            Dictionary of statistics
        """
        return {
            'database': self.db.get_stats(),
            'embeddings': self.embeddings.get_stats(),
            'graph': self.graph.get_stats(),
            'privacy': self.privacy_filter.get_privacy_stats(),
            'activity_count': self.activity_count,
            'uptime': str(datetime.now() - self.last_save_time)
        }


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Context Continuity Engine Daemon')
    parser.add_argument('--config', default='config/default_config.yaml',
                       help='Path to configuration file')
    parser.add_argument('--stats', action='store_true',
                       help='Show statistics and exit')

    args = parser.parse_args()

    # Change to script directory
    script_dir = Path(__file__).parent
    import os
    os.chdir(script_dir)

    # Create engine
    engine = ContextEngine(args.config)

    if args.stats:
        # Print stats and exit
        import json
        stats = engine.get_stats()
        print(json.dumps(stats, indent=2, default=str))
        return

    # Setup signal handlers
    def signal_handler(sig, frame):
        engine.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start engine
    engine.start()


if __name__ == '__main__':
    main()

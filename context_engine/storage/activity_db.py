"""
Activity Database Module

Manages SQLite storage for all tracked activities and context.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any
from contextlib import contextmanager


class ActivityDatabase:
    """Manages persistent storage of activity data."""

    def __init__(self, db_path: str):
        """Initialize the activity database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def get_connection(self):
        """Get a database connection with automatic cleanup."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Activities table - main event log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    activity_type TEXT NOT NULL,
                    app_name TEXT,
                    window_title TEXT,
                    file_path TEXT,
                    url TEXT,
                    duration INTEGER DEFAULT 0,
                    metadata TEXT,
                    embedding_id TEXT,
                    UNIQUE(timestamp, activity_type, app_name, window_title)
                )
            """)

            # Contexts table - high-level work contexts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contexts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_active DATETIME,
                    total_duration INTEGER DEFAULT 0,
                    tags TEXT,
                    metadata TEXT
                )
            """)

            # Context activities junction table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS context_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    context_id INTEGER NOT NULL,
                    activity_id INTEGER NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    FOREIGN KEY (context_id) REFERENCES contexts(id) ON DELETE CASCADE,
                    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
                    UNIQUE(context_id, activity_id)
                )
            """)

            # Files table - track file access patterns
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_accessed DATETIME,
                    access_count INTEGER DEFAULT 1,
                    file_type TEXT,
                    project_path TEXT,
                    metadata TEXT
                )
            """)

            # Applications table - track application usage
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_used DATETIME,
                    total_duration INTEGER DEFAULT 0,
                    usage_count INTEGER DEFAULT 1,
                    category TEXT,
                    metadata TEXT
                )
            """)

            # Create indexes for common queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_activities_timestamp ON activities(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_activities_type ON activities(activity_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_activities_app ON activities(app_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contexts_last_active ON contexts(last_active)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_last_accessed ON files(last_accessed)")

            conn.commit()

    def record_activity(self, activity_type: str, **kwargs) -> int:
        """Record a new activity.

        Args:
            activity_type: Type of activity (window_focus, file_access, etc.)
            **kwargs: Additional activity data

        Returns:
            Activity ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Extract known fields
            app_name = kwargs.get('app_name')
            window_title = kwargs.get('window_title')
            file_path = kwargs.get('file_path')
            url = kwargs.get('url')
            duration = kwargs.get('duration', 0)

            # Store additional data as JSON metadata
            metadata = {k: v for k, v in kwargs.items()
                       if k not in ['app_name', 'window_title', 'file_path', 'url', 'duration']}

            cursor.execute("""
                INSERT OR IGNORE INTO activities
                (activity_type, app_name, window_title, file_path, url, duration, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (activity_type, app_name, window_title, file_path, url, duration,
                  json.dumps(metadata) if metadata else None))

            activity_id = cursor.lastrowid

            # Update application usage if app_name provided
            if app_name:
                cursor.execute("""
                    INSERT INTO applications (name, last_used, total_duration)
                    VALUES (?, CURRENT_TIMESTAMP, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        last_used = CURRENT_TIMESTAMP,
                        total_duration = total_duration + excluded.total_duration,
                        usage_count = usage_count + 1
                """, (app_name, duration))

            # Update file access if file_path provided
            if file_path:
                cursor.execute("""
                    INSERT INTO files (path, last_accessed)
                    VALUES (?, CURRENT_TIMESTAMP)
                    ON CONFLICT(path) DO UPDATE SET
                        last_accessed = CURRENT_TIMESTAMP,
                        access_count = access_count + 1
                """, (file_path,))

            return activity_id

    def get_recent_activities(self, limit: int = 100, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent activities within time window.

        Args:
            limit: Maximum number of activities to return
            hours: Look back this many hours

        Returns:
            List of activity records
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cutoff = datetime.now() - timedelta(hours=hours)
            cursor.execute("""
                SELECT * FROM activities
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (cutoff, limit))

            return [dict(row) for row in cursor.fetchall()]

    def get_context_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get context by name.

        Args:
            name: Context name

        Returns:
            Context record or None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contexts WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def create_or_update_context(self, name: str, description: str = "",
                                 tags: List[str] = None) -> int:
        """Create or update a context.

        Args:
            name: Context name
            description: Context description
            tags: List of tags

        Returns:
            Context ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            tags_json = json.dumps(tags) if tags else None

            cursor.execute("""
                INSERT INTO contexts (name, description, tags, last_active)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(name) DO UPDATE SET
                    description = excluded.description,
                    tags = excluded.tags,
                    last_active = CURRENT_TIMESTAMP
            """, (name, description, tags_json))

            if cursor.lastrowid:
                return cursor.lastrowid
            else:
                cursor.execute("SELECT id FROM contexts WHERE name = ?", (name,))
                return cursor.fetchone()[0]

    def link_activity_to_context(self, activity_id: int, context_id: int,
                                 confidence: float = 1.0):
        """Link an activity to a context.

        Args:
            activity_id: Activity ID
            context_id: Context ID
            confidence: Confidence score (0.0 - 1.0)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO context_activities
                (context_id, activity_id, confidence)
                VALUES (?, ?, ?)
            """, (context_id, activity_id, confidence))

    def cleanup_old_data(self, days: int = 90):
        """Remove activity data older than specified days.

        Args:
            days: Number of days to retain
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cutoff = datetime.now() - timedelta(days=days)

            cursor.execute("DELETE FROM activities WHERE timestamp < ?", (cutoff,))
            deleted = cursor.rowcount

            return deleted

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics.

        Returns:
            Dictionary of statistics
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            cursor.execute("SELECT COUNT(*) FROM activities")
            stats['total_activities'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM contexts")
            stats['total_contexts'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM files")
            stats['total_files'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM applications")
            stats['total_applications'] = cursor.fetchone()[0]

            cursor.execute("""
                SELECT MIN(timestamp), MAX(timestamp)
                FROM activities
            """)
            row = cursor.fetchone()
            stats['first_activity'] = row[0]
            stats['last_activity'] = row[1]

            return stats

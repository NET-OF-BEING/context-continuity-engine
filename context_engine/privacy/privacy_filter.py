"""
Privacy Filter Module

Filters and sanitizes activity data based on privacy rules.
"""

import re
import fnmatch
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class PrivacyFilter:
    """Filters sensitive data from activities based on privacy rules."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the privacy filter.

        Args:
            config: Privacy configuration dictionary
        """
        self.enabled = config.get('enabled', True)
        self.blacklist_apps = set(config.get('blacklist_apps', []))
        self.blacklist_urls = config.get('blacklist_urls', [])
        self.blacklist_directories = [
            Path(d).expanduser()
            for d in config.get('blacklist_directories', [])
        ]
        self.exclude_file_types = set(config.get('exclude_file_types', []))

        # Compile URL patterns
        self.url_patterns = [
            self._compile_glob_pattern(pattern)
            for pattern in self.blacklist_urls
        ]

        logger.info(f"Privacy filter initialized (enabled: {self.enabled})")
        logger.info(f"  Blacklisted apps: {len(self.blacklist_apps)}")
        logger.info(f"  Blacklisted directories: {len(self.blacklist_directories)}")
        logger.info(f"  Excluded file types: {len(self.exclude_file_types)}")

    def _compile_glob_pattern(self, pattern: str) -> re.Pattern:
        """Convert glob pattern to regex.

        Args:
            pattern: Glob pattern (e.g., "*://*/login*")

        Returns:
            Compiled regex pattern
        """
        # Convert glob to regex
        regex = fnmatch.translate(pattern)
        return re.compile(regex, re.IGNORECASE)

    def should_track_activity(self, activity: Dict[str, Any]) -> bool:
        """Determine if an activity should be tracked.

        Args:
            activity: Activity data

        Returns:
            True if activity should be tracked, False if it should be blocked
        """
        if not self.enabled:
            return True

        # Check app blacklist
        app_name = activity.get('app_name', '').lower()
        if app_name in self.blacklist_apps:
            logger.debug(f"Blocking activity from blacklisted app: {app_name}")
            return False

        # Check URL blacklist
        url = activity.get('url')
        if url and self._is_url_blacklisted(url):
            logger.debug(f"Blocking activity with blacklisted URL: {url}")
            return False

        # Check directory blacklist
        file_path = activity.get('file_path')
        if file_path and self._is_path_blacklisted(file_path):
            logger.debug(f"Blocking activity in blacklisted directory: {file_path}")
            return False

        # Check file extension blacklist
        if file_path and self._is_file_type_excluded(file_path):
            logger.debug(f"Blocking activity with excluded file type: {file_path}")
            return False

        # Check for sensitive patterns in window title
        window_title = activity.get('window_title', '')
        if self._contains_sensitive_keywords(window_title):
            logger.debug(f"Blocking activity with sensitive keywords in title")
            return False

        return True

    def _is_url_blacklisted(self, url: str) -> bool:
        """Check if URL matches blacklist patterns.

        Args:
            url: URL to check

        Returns:
            True if URL is blacklisted
        """
        for pattern in self.url_patterns:
            if pattern.match(url):
                return True
        return False

    def _is_path_blacklisted(self, file_path: str) -> bool:
        """Check if file path is in a blacklisted directory.

        Args:
            file_path: File path to check

        Returns:
            True if path is blacklisted
        """
        try:
            path = Path(file_path).expanduser().resolve()

            for blacklisted_dir in self.blacklist_directories:
                if path == blacklisted_dir or blacklisted_dir in path.parents:
                    return True

        except Exception as e:
            logger.warning(f"Error checking path {file_path}: {e}")

        return False

    def _is_file_type_excluded(self, file_path: str) -> bool:
        """Check if file type is excluded.

        Args:
            file_path: File path to check

        Returns:
            True if file type is excluded
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        return suffix in self.exclude_file_types

    def _contains_sensitive_keywords(self, text: str) -> bool:
        """Check if text contains sensitive keywords.

        Args:
            text: Text to check

        Returns:
            True if text contains sensitive keywords
        """
        if not text:
            return False

        text_lower = text.lower()

        # Common sensitive keywords
        sensitive_keywords = [
            'password',
            'login',
            'signin',
            'sign in',
            'authenticate',
            'private browsing',
            'incognito',
            'secret',
            'confidential'
        ]

        for keyword in sensitive_keywords:
            if keyword in text_lower:
                return True

        return False

    def sanitize_activity(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize activity data by removing sensitive information.

        Args:
            activity: Activity data

        Returns:
            Sanitized activity data
        """
        if not self.enabled:
            return activity

        sanitized = activity.copy()

        # Redact sensitive parts of window titles
        if 'window_title' in sanitized:
            sanitized['window_title'] = self._sanitize_window_title(
                sanitized['window_title']
            )

        # Redact sensitive parts of URLs
        if 'url' in sanitized:
            sanitized['url'] = self._sanitize_url(sanitized['url'])

        # Redact parts of file paths
        if 'file_path' in sanitized:
            sanitized['file_path'] = self._sanitize_file_path(
                sanitized['file_path']
            )

        return sanitized

    def _sanitize_window_title(self, title: str) -> str:
        """Sanitize window title.

        Args:
            title: Window title

        Returns:
            Sanitized title
        """
        if not title:
            return title

        # Remove potential passwords or sensitive info in parentheses
        title = re.sub(r'\([^)]*password[^)]*\)', '(***)', title, flags=re.IGNORECASE)

        # Remove email addresses
        title = re.sub(r'\b[\w.-]+@[\w.-]+\.\w+\b', '[EMAIL]', title)

        # Remove potential API keys or tokens (long alphanumeric strings)
        title = re.sub(r'\b[A-Za-z0-9]{32,}\b', '[TOKEN]', title)

        return title

    def _sanitize_url(self, url: str) -> str:
        """Sanitize URL by removing sensitive parameters.

        Args:
            url: URL

        Returns:
            Sanitized URL
        """
        if not url:
            return url

        # Remove common sensitive query parameters
        sensitive_params = ['password', 'token', 'key', 'secret', 'auth', 'api_key']

        for param in sensitive_params:
            url = re.sub(
                f'[?&]{param}=[^&]*',
                f'?{param}=[REDACTED]',
                url,
                flags=re.IGNORECASE
            )

        return url

    def _sanitize_file_path(self, file_path: str) -> str:
        """Sanitize file path.

        Args:
            file_path: File path

        Returns:
            Sanitized path
        """
        if not file_path:
            return file_path

        # For blacklisted directories, just show [PRIVATE]
        if self._is_path_blacklisted(file_path):
            return "[PRIVATE]"

        return file_path

    def get_privacy_stats(self) -> Dict[str, Any]:
        """Get privacy filter statistics.

        Returns:
            Dictionary of statistics
        """
        return {
            'enabled': self.enabled,
            'blacklisted_apps': len(self.blacklist_apps),
            'blacklisted_url_patterns': len(self.url_patterns),
            'blacklisted_directories': len(self.blacklist_directories),
            'excluded_file_types': len(self.exclude_file_types)
        }

    def add_blacklist_app(self, app_name: str):
        """Add an app to the blacklist.

        Args:
            app_name: Application name
        """
        self.blacklist_apps.add(app_name.lower())
        logger.info(f"Added app to blacklist: {app_name}")

    def remove_blacklist_app(self, app_name: str):
        """Remove an app from the blacklist.

        Args:
            app_name: Application name
        """
        self.blacklist_apps.discard(app_name.lower())
        logger.info(f"Removed app from blacklist: {app_name}")

    def add_blacklist_directory(self, directory: str):
        """Add a directory to the blacklist.

        Args:
            directory: Directory path
        """
        path = Path(directory).expanduser().resolve()
        self.blacklist_directories.append(path)
        logger.info(f"Added directory to blacklist: {path}")

    def remove_blacklist_directory(self, directory: str):
        """Remove a directory from the blacklist.

        Args:
            directory: Directory path
        """
        path = Path(directory).expanduser().resolve()
        if path in self.blacklist_directories:
            self.blacklist_directories.remove(path)
            logger.info(f"Removed directory from blacklist: {path}")

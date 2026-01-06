"""
Activity Monitoring Daemon

Monitors user activity across the system.
"""

import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from pathlib import Path
import subprocess
import threading

try:
    from Xlib import display, X
    from Xlib.error import XError
    HAS_XLIB = True
except ImportError:
    HAS_XLIB = False
    logging.warning("python-xlib not available - X11 monitoring disabled")

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    logging.warning("watchdog not available - file monitoring disabled")

logger = logging.getLogger(__name__)


class ActivityMonitor:
    """Main activity monitoring daemon."""

    def __init__(self, config: Dict[str, Any],
                 activity_callback: Optional[Callable] = None):
        """Initialize the activity monitor.

        Args:
            config: Monitoring configuration
            activity_callback: Callback function for activity events
        """
        self.config = config
        self.activity_callback = activity_callback
        self.running = False
        self.poll_interval = config.get('poll_interval', 5)

        # Monitoring threads
        self.threads = []

        # Current state
        self.current_window = None
        self.current_app = None
        self.window_start_time = None

        logger.info("Activity monitor initialized")

    def start(self):
        """Start monitoring."""
        if self.running:
            logger.warning("Monitor already running")
            return

        self.running = True
        logger.info("Starting activity monitor")

        # Start window focus monitoring
        if self.config.get('track_window_focus', True) and HAS_XLIB:
            thread = threading.Thread(target=self._monitor_window_focus, daemon=True)
            thread.start()
            self.threads.append(thread)

        # Start file monitoring
        if self.config.get('track_file_access', True) and HAS_WATCHDOG:
            thread = threading.Thread(target=self._monitor_files, daemon=True)
            thread.start()
            self.threads.append(thread)

        logger.info(f"Started {len(self.threads)} monitoring threads")

    def stop(self):
        """Stop monitoring."""
        logger.info("Stopping activity monitor")
        self.running = False

        # Wait for threads
        for thread in self.threads:
            thread.join(timeout=2)

        self.threads.clear()

    def _monitor_window_focus(self):
        """Monitor window focus changes using X11."""
        if not HAS_XLIB:
            logger.error("Cannot monitor windows - python-xlib not installed")
            return

        try:
            disp = display.Display()
            root = disp.screen().root

            # Subscribe to window focus events
            root.change_attributes(event_mask=X.FocusChangeMask | X.PropertyChangeMask)

            logger.info("Window focus monitoring started")

            while self.running:
                try:
                    # Poll current window
                    self._check_current_window(disp)
                    time.sleep(self.poll_interval)

                except XError as e:
                    logger.error(f"X11 error: {e}")
                    time.sleep(self.poll_interval)

        except Exception as e:
            logger.error(f"Window monitoring error: {e}")

    def _check_current_window(self, disp):
        """Check and record current focused window.

        Args:
            disp: X display object
        """
        try:
            # Get focused window
            window = disp.get_input_focus().focus

            # Get window properties
            window_title = self._get_window_title(window)
            app_name = self._get_app_name(window)

            # Check if window changed
            if window_title != self.current_window or app_name != self.current_app:
                # Record end of previous activity
                if self.current_window and self.window_start_time:
                    duration = (datetime.now() - self.window_start_time).total_seconds()

                    self._record_activity({
                        'activity_type': 'window_focus',
                        'app_name': self.current_app,
                        'window_title': self.current_window,
                        'duration': int(duration)
                    })

                # Start new activity
                self.current_window = window_title
                self.current_app = app_name
                self.window_start_time = datetime.now()

                self._record_activity({
                    'activity_type': 'window_focus_start',
                    'app_name': app_name,
                    'window_title': window_title
                })

        except Exception as e:
            logger.debug(f"Error checking window: {e}")

    def _get_window_title(self, window) -> Optional[str]:
        """Get window title.

        Args:
            window: X window object

        Returns:
            Window title or None
        """
        try:
            # Try _NET_WM_NAME first (UTF-8)
            title = window.get_full_property(
                window.display.intern_atom('_NET_WM_NAME'),
                window.display.intern_atom('UTF8_STRING')
            )

            if title:
                return title.value.decode('utf-8') if isinstance(title.value, bytes) else str(title.value)

            # Fallback to WM_NAME
            title = window.get_wm_name()
            return title if title else None

        except Exception:
            return None

    def _get_app_name(self, window) -> Optional[str]:
        """Get application name.

        Args:
            window: X window object

        Returns:
            Application name or None
        """
        try:
            # Get WM_CLASS
            wm_class = window.get_wm_class()
            if wm_class:
                # WM_CLASS returns (instance, class)
                return wm_class[1] if len(wm_class) > 1 else wm_class[0]

            return None

        except Exception:
            return None

    def _monitor_files(self):
        """Monitor file access."""
        if not HAS_WATCHDOG:
            logger.error("Cannot monitor files - watchdog not installed")
            return

        # Monitor common work directories
        watch_dirs = [
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path.home() / "Projects",
            Path.home() / "Code"
        ]

        # Only watch directories that exist
        watch_dirs = [d for d in watch_dirs if d.exists()]

        if not watch_dirs:
            logger.warning("No directories to watch")
            return

        event_handler = FileAccessHandler(self._record_activity)
        observer = Observer()

        for watch_dir in watch_dirs:
            observer.schedule(event_handler, str(watch_dir), recursive=True)
            logger.info(f"Watching directory: {watch_dir}")

        observer.start()

        try:
            while self.running:
                time.sleep(1)
        finally:
            observer.stop()
            observer.join()

    def _record_activity(self, activity: Dict[str, Any]):
        """Record an activity event.

        Args:
            activity: Activity data
        """
        if self.activity_callback:
            try:
                self.activity_callback(activity)
            except Exception as e:
                logger.error(f"Activity callback error: {e}")

    def get_current_activity(self) -> Dict[str, Any]:
        """Get current activity state.

        Returns:
            Current activity data
        """
        duration = 0
        if self.window_start_time:
            duration = (datetime.now() - self.window_start_time).total_seconds()

        return {
            'app_name': self.current_app,
            'window_title': self.current_window,
            'duration': int(duration),
            'timestamp': datetime.now().isoformat()
        }


class FileAccessHandler(FileSystemEventHandler):
    """Handles file system events."""

    def __init__(self, callback: Callable):
        """Initialize handler.

        Args:
            callback: Callback function for file events
        """
        super().__init__()
        self.callback = callback
        self.last_events = {}
        self.debounce_seconds = 5

    def on_modified(self, event):
        """Handle file modification.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        # Debounce rapid events
        if not self._should_record(event.src_path):
            return

        self.callback({
            'activity_type': 'file_access',
            'file_path': event.src_path
        })

    def on_created(self, event):
        """Handle file creation.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        self.callback({
            'activity_type': 'file_created',
            'file_path': event.src_path
        })

    def _should_record(self, file_path: str) -> bool:
        """Check if event should be recorded (debounce).

        Args:
            file_path: File path

        Returns:
            True if event should be recorded
        """
        now = time.time()
        last_time = self.last_events.get(file_path, 0)

        if now - last_time < self.debounce_seconds:
            return False

        self.last_events[file_path] = now
        return True


def get_browser_url() -> Optional[str]:
    """Get current browser URL (best effort).

    Returns:
        Current URL or None
    """
    # This is a simplified version - full implementation would need browser extensions
    # For now, we can try to get URL from window title for some browsers

    try:
        # Use wmctrl to get active window
        result = subprocess.run(
            ['wmctrl', '-l', '-x'],
            capture_output=True,
            text=True,
            timeout=2
        )

        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'firefox' in line.lower() or 'chrome' in line.lower():
                    # Window title often contains URL
                    parts = line.split(None, 3)
                    if len(parts) > 3:
                        title = parts[3]
                        # Try to extract URL from title
                        # This is very basic - real implementation needs browser extension
                        if 'http' in title:
                            return title

    except Exception as e:
        logger.debug(f"Could not get browser URL: {e}")

    return None

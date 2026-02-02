"""
Custom Qt signals for thread-safe communication between components.
"""

from PySide6.QtCore import QObject, Signal


class AppSignals(QObject):
    """
    Central signal hub for application-wide events.

    Use this to communicate between different parts of the application
    in a thread-safe manner.
    """

    # Docker daemon signals
    daemon_started = Signal()
    daemon_stopped = Signal()
    daemon_autostart_changed = Signal(bool)  # True if autostart is now enabled

    # Container signals
    container_created = Signal()
    container_started = Signal()
    container_stopped = Signal()
    container_removed = Signal()
    container_state_changed = Signal(str)  # New state value

    # Image signals
    image_pull_started = Signal()
    image_pull_progress = Signal(str)  # Progress message
    image_pull_complete = Signal(bool)  # Success status

    # Log signals
    log_streaming_started = Signal()
    log_streaming_stopped = Signal()

    # General signals
    error_occurred = Signal(str)  # Error message
    status_message = Signal(str)  # General status/info message

    # Configuration signals
    config_changed = Signal()
    media_path_added = Signal(str)   # Path that was added
    media_path_removed = Signal(str) # Path that was removed


# Global singleton instance
_app_signals = None


def get_app_signals() -> AppSignals:
    """Get the global AppSignals instance."""
    global _app_signals
    if _app_signals is None:
        _app_signals = AppSignals()
    return _app_signals

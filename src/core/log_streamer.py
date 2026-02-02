"""
Real-time log streaming from Docker container.

Runs in a separate thread to avoid blocking the UI.
"""

from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker

from .docker_manager import DockerManager, ContainerState


class LogStreamer(QThread):
    """
    Thread that streams logs from the Docker container.

    Emits signals when new log lines arrive, allowing thread-safe UI updates.
    """

    # Signals
    log_line = Signal(str)  # Emitted for each new log line
    error = Signal(str)     # Emitted on error
    stopped = Signal()      # Emitted when streaming stops

    def __init__(self, docker_manager: DockerManager, parent=None):
        super().__init__(parent)
        self.docker_manager = docker_manager
        self._stop_requested = False
        self._mutex = QMutex()

    def run(self):
        """Main thread execution - streams logs until stopped."""
        try:
            # Check container state first
            state = self.docker_manager.get_container_state()
            if state != ContainerState.RUNNING:
                self.error.emit(f"Container is not running (state: {state.value})")
                self.stopped.emit()
                return

            # Stream logs
            for line in self.docker_manager.stream_logs():
                # Check if stop was requested
                with QMutexLocker(self._mutex):
                    if self._stop_requested:
                        break

                self.log_line.emit(line)

        except Exception as e:
            self.error.emit(f"Log streaming error: {e}")

        finally:
            self.stopped.emit()

    def stop(self):
        """Request the log streaming to stop."""
        with QMutexLocker(self._mutex):
            self._stop_requested = True

    def is_stop_requested(self) -> bool:
        """Check if stop has been requested."""
        with QMutexLocker(self._mutex):
            return self._stop_requested


class ImagePullWorker(QThread):
    """
    Thread that pulls a Docker image with progress updates.
    """

    # Signals
    progress = Signal(str)      # Progress message
    finished = Signal(bool)     # True if successful

    def __init__(self, docker_manager: DockerManager, parent=None):
        super().__init__(parent)
        self.docker_manager = docker_manager

    def run(self):
        """Pull the image and emit progress."""
        try:
            success = False
            for message in self.docker_manager.pull_image():
                self.progress.emit(message)
                # The generator returns True/False at the end
                if isinstance(message, bool):
                    success = message

            # Check if image is now available
            success = self.docker_manager.is_image_pulled()
            self.finished.emit(success)

        except Exception as e:
            self.progress.emit(f"Error: {e}")
            self.finished.emit(False)


class StatusPoller(QThread):
    """
    Thread that periodically polls Docker/container status.

    Useful for keeping the UI updated with current state.
    """

    # Signals
    status_updated = Signal(object)  # Emits DockerStatus object

    def __init__(self, docker_manager: DockerManager, interval_ms: int = 2000, parent=None):
        super().__init__(parent)
        self.docker_manager = docker_manager
        self.interval_ms = interval_ms
        self._stop_requested = False
        self._mutex = QMutex()

    def run(self):
        """Poll status at regular intervals."""
        while True:
            with QMutexLocker(self._mutex):
                if self._stop_requested:
                    break

            try:
                status = self.docker_manager.get_full_status()
                self.status_updated.emit(status)
            except Exception as e:
                # Don't spam errors, just skip this poll
                pass

            # Sleep in small increments to allow quick stopping
            for _ in range(self.interval_ms // 100):
                with QMutexLocker(self._mutex):
                    if self._stop_requested:
                        return
                self.msleep(100)

    def stop(self):
        """Request the polling to stop."""
        with QMutexLocker(self._mutex):
            self._stop_requested = True

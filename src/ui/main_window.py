"""
Main application window.
"""

import webbrowser

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QCloseEvent

from ui.widgets.control_panel import ControlPanel
from ui.widgets.status_widget import StatusWidget
from ui.widgets.log_viewer import LogViewer

from core.docker_manager import DockerManager, ContainerState, DaemonState
from core.config import ConfigManager
from core.log_streamer import LogStreamer, StatusPoller


class MainWindow(QMainWindow):
    """
    Main application window for Jellyfin Manager.
    """

    def __init__(self):
        super().__init__()

        # Initialize core components
        self.config_manager = ConfigManager()
        self.docker_manager = DockerManager(self.config_manager.config)

        # Background workers
        self._log_streamer = None
        self._status_poller = None

        self._setup_ui()
        self._connect_signals()
        self._start_status_polling()

        # Initial status update
        QTimer.singleShot(100, self._update_status)

    def _setup_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Jellyfin Manager")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Status widget at top
        self.status_widget = StatusWidget()
        self.status_widget.set_web_url(self.docker_manager.get_web_url())

        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.StyledPanel)
        status_layout = QVBoxLayout(status_frame)
        status_layout.addWidget(self.status_widget)

        main_layout.addWidget(status_frame)

        # Splitter for control panel and logs
        splitter = QSplitter(Qt.Horizontal)

        # Control panel on the left
        self.control_panel = ControlPanel(
            self.docker_manager,
            self.config_manager
        )
        control_frame = QFrame()
        control_frame.setFrameShape(QFrame.StyledPanel)
        control_frame.setFixedWidth(320)
        control_layout = QVBoxLayout(control_frame)
        control_layout.addWidget(self.control_panel)

        splitter.addWidget(control_frame)

        # Log viewer on the right
        self.log_viewer = LogViewer()
        log_frame = QFrame()
        log_frame.setFrameShape(QFrame.StyledPanel)
        log_layout = QVBoxLayout(log_frame)
        log_layout.addWidget(self.log_viewer)

        splitter.addWidget(log_frame)

        # Set splitter sizes (control panel smaller)
        splitter.setSizes([320, 680])

        main_layout.addWidget(splitter, stretch=1)

        # Apply basic styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QFrame {
                background-color: white;
                border-radius: 8px;
            }
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #9ca3af;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QCheckBox {
                spacing: 8px;
            }
            QListWidget {
                border: 1px solid #e5e7eb;
                border-radius: 4px;
            }
        """)

    def _connect_signals(self):
        """Connect signals between components."""
        # Control panel signals
        self.control_panel.setup_requested.connect(self._on_setup_complete)
        self.control_panel.start_requested.connect(self._on_container_started)
        self.control_panel.stop_requested.connect(self._on_container_stopped)
        self.control_panel.open_webui_requested.connect(self._open_web_ui)

    def _start_status_polling(self):
        """Start background status polling."""
        self._status_poller = StatusPoller(self.docker_manager, interval_ms=2000)
        self._status_poller.status_updated.connect(self._on_status_updated)
        self._status_poller.start()

    def _stop_status_polling(self):
        """Stop background status polling."""
        if self._status_poller:
            self._status_poller.stop()
            self._status_poller.wait(3000)
            self._status_poller = None

    def _update_status(self):
        """Manually trigger a status update."""
        status = self.docker_manager.get_full_status()
        self._on_status_updated(status)

    @Slot(object)
    def _on_status_updated(self, status):
        """Handle status updates from poller."""
        # Update status widget
        self.status_widget.update_status(status)

        # Update control panel button states
        self.control_panel.update_button_states(
            status.daemon_state,
            status.container_state
        )

        # Update web URL visibility
        if status.container_state == ContainerState.RUNNING:
            self.status_widget.set_web_url(self.docker_manager.get_web_url())
        else:
            self.status_widget.clear_web_url()

    @Slot()
    def _on_setup_complete(self):
        """Handle setup completion."""
        self._update_status()
        self.log_viewer.set_status("Container created. Click Start to begin.")

    @Slot()
    def _on_container_started(self):
        """Handle container start."""
        self._update_status()
        self._start_log_streaming()

    @Slot()
    def _on_container_stopped(self):
        """Handle container stop."""
        self._stop_log_streaming()
        self._update_status()
        self.log_viewer.set_status("Container stopped")

    def _start_log_streaming(self):
        """Start streaming logs from the container."""
        # Stop any existing streamer
        self._stop_log_streaming()

        # Load recent logs first
        recent_logs = self.docker_manager.get_logs(tail=50)
        if recent_logs and not recent_logs.startswith("Container not found"):
            self.log_viewer.load_initial_logs(recent_logs)

        # Start streaming
        self._log_streamer = LogStreamer(self.docker_manager)
        self._log_streamer.log_line.connect(self.log_viewer.append_log)
        self._log_streamer.error.connect(self._on_log_error)
        self._log_streamer.stopped.connect(self._on_log_streaming_stopped)

        self._log_streamer.start()
        self.log_viewer.set_streaming(True)

    def _stop_log_streaming(self):
        """Stop the log streaming thread."""
        if self._log_streamer:
            self._log_streamer.stop()
            self._log_streamer.wait(3000)
            self._log_streamer = None

    @Slot(str)
    def _on_log_error(self, error: str):
        """Handle log streaming error."""
        self.log_viewer.append_log(f"[ERROR] {error}")

    @Slot()
    def _on_log_streaming_stopped(self):
        """Handle log streaming stopped."""
        self.log_viewer.set_streaming(False)

    @Slot()
    def _open_web_ui(self):
        """Open Jellyfin web UI in browser."""
        url = self.docker_manager.get_web_url()
        webbrowser.open(url)

    def closeEvent(self, event: QCloseEvent):
        """Handle application close."""
        # Stop background threads
        self._stop_log_streaming()
        self._stop_status_polling()

        # Check if we should stop the container
        container_state = self.docker_manager.get_container_state()
        if container_state == ContainerState.RUNNING:
            reply = QMessageBox.question(
                self,
                "Container Running",
                "Jellyfin container is still running. Stop it before closing?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )

            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            elif reply == QMessageBox.Yes:
                self.docker_manager.stop_container()

        # Check if we should stop the daemon
        if self.config_manager.config.stop_daemon_on_exit:
            if self.docker_manager.is_daemon_running():
                # Make sure container is stopped first
                if self.docker_manager.get_container_state() == ContainerState.RUNNING:
                    self.docker_manager.stop_container()

                success, msg = self.docker_manager.stop_daemon()
                if not success:
                    QMessageBox.warning(
                        self,
                        "Warning",
                        f"Could not stop Docker daemon: {msg}"
                    )

        event.accept()

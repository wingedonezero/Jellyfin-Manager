"""
Control panel widget with Start/Stop/Setup buttons.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QListWidget, QListWidgetItem,
    QMessageBox, QGroupBox, QCheckBox, QProgressDialog
)
from PySide6.QtCore import Qt, Signal, Slot
from pathlib import Path

from core.docker_manager import DockerManager, ContainerState, DaemonState
from core.config import ConfigManager
from core.log_streamer import ImagePullWorker


class ControlPanel(QWidget):
    """
    Control panel with buttons for managing Jellyfin container.
    """

    # Signals
    setup_requested = Signal()
    start_requested = Signal()
    stop_requested = Signal()
    open_webui_requested = Signal()

    def __init__(
        self,
        docker_manager: DockerManager,
        config_manager: ConfigManager,
        parent=None
    ):
        super().__init__(parent)
        self.docker_manager = docker_manager
        self.config_manager = config_manager
        self._pull_worker = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Main control buttons
        buttons_layout = QHBoxLayout()

        self.setup_btn = QPushButton("Setup")
        self.setup_btn.setMinimumHeight(40)
        self.setup_btn.setToolTip("Pull Jellyfin image and create container")

        self.start_btn = QPushButton("Start")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setToolTip("Start Jellyfin container")

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setToolTip("Stop Jellyfin container")

        buttons_layout.addWidget(self.setup_btn)
        buttons_layout.addWidget(self.start_btn)
        buttons_layout.addWidget(self.stop_btn)

        layout.addLayout(buttons_layout)

        # Open Web UI button
        self.webui_btn = QPushButton("Open Jellyfin Web UI")
        self.webui_btn.setMinimumHeight(35)
        layout.addWidget(self.webui_btn)

        # Media paths group
        media_group = QGroupBox("Media Folders")
        media_layout = QVBoxLayout(media_group)

        self.media_list = QListWidget()
        self.media_list.setMaximumHeight(100)
        media_layout.addWidget(self.media_list)

        media_buttons = QHBoxLayout()
        self.add_media_btn = QPushButton("Add Folder")
        self.remove_media_btn = QPushButton("Remove Selected")
        media_buttons.addWidget(self.add_media_btn)
        media_buttons.addWidget(self.remove_media_btn)
        media_layout.addLayout(media_buttons)

        layout.addWidget(media_group)

        # Docker daemon options
        daemon_group = QGroupBox("Docker Daemon")
        daemon_layout = QVBoxLayout(daemon_group)

        self.autostart_checkbox = QCheckBox("Docker starts on boot")
        self.autostart_checkbox.setToolTip("If unchecked, Docker won't run until you start it")
        daemon_layout.addWidget(self.autostart_checkbox)

        self.stop_daemon_checkbox = QCheckBox("Stop Docker daemon when app closes")
        self.stop_daemon_checkbox.setToolTip("Completely stop Docker when you close this app")
        daemon_layout.addWidget(self.stop_daemon_checkbox)

        daemon_buttons = QHBoxLayout()
        self.start_daemon_btn = QPushButton("Start Daemon")
        self.stop_daemon_btn = QPushButton("Stop Daemon")
        daemon_buttons.addWidget(self.start_daemon_btn)
        daemon_buttons.addWidget(self.stop_daemon_btn)
        daemon_layout.addLayout(daemon_buttons)

        layout.addWidget(daemon_group)

        # Hardware acceleration
        hw_group = QGroupBox("Hardware Acceleration")
        hw_layout = QVBoxLayout(hw_group)

        self.hw_accel_checkbox = QCheckBox("Enable VAAPI (AMD/Intel GPU)")
        self.hw_accel_checkbox.setToolTip("Pass through /dev/dri for hardware transcoding")
        hw_layout.addWidget(self.hw_accel_checkbox)

        layout.addWidget(hw_group)

        # Stretch at bottom
        layout.addStretch()

        # Load current config into UI
        self._load_config_to_ui()

    def _connect_signals(self):
        """Connect widget signals to slots."""
        self.setup_btn.clicked.connect(self._on_setup_clicked)
        self.start_btn.clicked.connect(self._on_start_clicked)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        self.webui_btn.clicked.connect(self.open_webui_requested.emit)

        self.add_media_btn.clicked.connect(self._on_add_media)
        self.remove_media_btn.clicked.connect(self._on_remove_media)

        self.autostart_checkbox.stateChanged.connect(self._on_autostart_changed)
        self.stop_daemon_checkbox.stateChanged.connect(self._on_stop_daemon_changed)

        self.start_daemon_btn.clicked.connect(self._on_start_daemon)
        self.stop_daemon_btn.clicked.connect(self._on_stop_daemon)

        self.hw_accel_checkbox.stateChanged.connect(self._on_hw_accel_changed)

    def _load_config_to_ui(self):
        """Load current configuration into UI elements."""
        config = self.config_manager.config

        # Media paths
        self.media_list.clear()
        for path in config.media_paths:
            self.media_list.addItem(str(path))

        # Stop daemon option
        self.stop_daemon_checkbox.setChecked(config.stop_daemon_on_exit)

        # Hardware acceleration
        self.hw_accel_checkbox.setChecked(config.enable_hw_accel)

        # Docker autostart status
        autostart = self.docker_manager.is_daemon_autostart_enabled()
        self.autostart_checkbox.blockSignals(True)
        self.autostart_checkbox.setChecked(autostart)
        self.autostart_checkbox.blockSignals(False)

    def update_button_states(self, daemon_state: DaemonState, container_state: ContainerState):
        """Update button enabled states based on current status."""
        daemon_running = daemon_state == DaemonState.RUNNING
        container_exists = container_state != ContainerState.NOT_FOUND
        container_running = container_state == ContainerState.RUNNING

        # Setup: need daemon running, container should not exist
        self.setup_btn.setEnabled(daemon_running and not container_exists)

        # Start: need daemon and container exists but not running
        self.start_btn.setEnabled(
            daemon_running and container_exists and not container_running
        )

        # Stop: need container running
        self.stop_btn.setEnabled(container_running)

        # Web UI: only when running
        self.webui_btn.setEnabled(container_running)

        # Daemon buttons
        self.start_daemon_btn.setEnabled(not daemon_running)
        self.stop_daemon_btn.setEnabled(daemon_running and not container_running)

        # Media management: only when container is not running
        can_modify = not container_running
        self.add_media_btn.setEnabled(can_modify)
        self.remove_media_btn.setEnabled(can_modify and self.media_list.currentRow() >= 0)

    @Slot()
    def _on_setup_clicked(self):
        """Handle setup button click."""
        # Check if image needs to be pulled
        if not self.docker_manager.is_image_pulled():
            reply = QMessageBox.question(
                self,
                "Pull Image",
                "Jellyfin image needs to be downloaded. This may take a few minutes.\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

            self._pull_image_with_progress()
        else:
            self._create_container()

    def _pull_image_with_progress(self):
        """Pull Docker image with progress dialog."""
        progress = QProgressDialog("Pulling Jellyfin image...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        self._pull_worker = ImagePullWorker(self.docker_manager, self)
        self._pull_worker.progress.connect(lambda msg: progress.setLabelText(msg))

        def on_finished(success):
            progress.close()
            if success:
                self._create_container()
            else:
                QMessageBox.critical(
                    self,
                    "Error",
                    "Failed to pull Jellyfin image. Check your internet connection."
                )

        self._pull_worker.finished.connect(on_finished)
        self._pull_worker.start()

    def _create_container(self):
        """Create the Jellyfin container."""
        # Ensure directories exist
        self.config_manager.ensure_directories()

        success, message = self.docker_manager.create_container()
        if success:
            QMessageBox.information(self, "Success", message)
            self.setup_requested.emit()
        else:
            QMessageBox.critical(self, "Error", message)

    @Slot()
    def _on_start_clicked(self):
        """Handle start button click."""
        # Ensure daemon is running
        if not self.docker_manager.is_daemon_running():
            success, msg = self.docker_manager.start_daemon()
            if not success:
                QMessageBox.critical(self, "Error", f"Failed to start Docker daemon: {msg}")
                return

        success, message = self.docker_manager.start_container()
        if success:
            self.start_requested.emit()
        else:
            QMessageBox.critical(self, "Error", message)

    @Slot()
    def _on_stop_clicked(self):
        """Handle stop button click."""
        success, message = self.docker_manager.stop_container()
        if success:
            self.stop_requested.emit()
        else:
            QMessageBox.critical(self, "Error", message)

    @Slot()
    def _on_add_media(self):
        """Handle add media folder button."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Media Folder",
            str(Path.home()),
            QFileDialog.ShowDirsOnly
        )
        if folder:
            path = Path(folder)
            self.config_manager.add_media_path(path)
            self.media_list.addItem(str(path))

            # If container exists, warn that it needs recreation
            if self.docker_manager.get_container_state() != ContainerState.NOT_FOUND:
                QMessageBox.information(
                    self,
                    "Container Update Required",
                    "Media folder added. You'll need to recreate the container for changes to take effect.\n\n"
                    "Stop the container and use Setup again."
                )

    @Slot()
    def _on_remove_media(self):
        """Handle remove media folder button."""
        current = self.media_list.currentRow()
        if current >= 0:
            item = self.media_list.takeItem(current)
            path = Path(item.text())
            self.config_manager.remove_media_path(path)

    @Slot(int)
    def _on_autostart_changed(self, state):
        """Handle autostart checkbox change."""
        enabled = state == Qt.Checked
        success, message = self.docker_manager.set_daemon_autostart(enabled)
        if not success:
            # Revert checkbox
            self.autostart_checkbox.blockSignals(True)
            self.autostart_checkbox.setChecked(not enabled)
            self.autostart_checkbox.blockSignals(False)
            QMessageBox.warning(self, "Warning", message)

    @Slot(int)
    def _on_stop_daemon_changed(self, state):
        """Handle stop daemon on exit checkbox change."""
        config = self.config_manager.config
        config.stop_daemon_on_exit = state == Qt.Checked
        self.config_manager.save()

    @Slot()
    def _on_start_daemon(self):
        """Handle start daemon button."""
        success, message = self.docker_manager.start_daemon()
        if not success:
            QMessageBox.critical(self, "Error", message)

    @Slot()
    def _on_stop_daemon(self):
        """Handle stop daemon button."""
        # Check if container is running
        if self.docker_manager.get_container_state() == ContainerState.RUNNING:
            QMessageBox.warning(
                self,
                "Warning",
                "Please stop the Jellyfin container first."
            )
            return

        success, message = self.docker_manager.stop_daemon()
        if not success:
            QMessageBox.critical(self, "Error", message)

    @Slot(int)
    def _on_hw_accel_changed(self, state):
        """Handle hardware acceleration checkbox change."""
        config = self.config_manager.config
        config.enable_hw_accel = state == Qt.Checked
        self.config_manager.save()

        if self.docker_manager.get_container_state() != ContainerState.NOT_FOUND:
            QMessageBox.information(
                self,
                "Container Update Required",
                "Hardware acceleration setting changed. Recreate the container for changes to take effect."
            )

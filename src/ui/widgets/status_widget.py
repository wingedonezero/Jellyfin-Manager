"""
Status display widget showing Docker and container state.
"""

import socket

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGroupBox
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont

from core.docker_manager import DockerStatus, DaemonState, ContainerState


def get_local_ip() -> str:
    """Get the local network IP address."""
    try:
        # Create a socket to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unknown"


class StatusIndicator(QFrame):
    """A colored dot indicator for status display."""

    COLORS = {
        'green': '#22c55e',
        'yellow': '#eab308',
        'red': '#ef4444',
        'gray': '#6b7280',
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._set_color('gray')

    def _set_color(self, color: str):
        """Set the indicator color."""
        hex_color = self.COLORS.get(color, self.COLORS['gray'])
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {hex_color};
                border-radius: 6px;
            }}
        """)

    def set_state(self, state: str):
        """
        Set indicator state.

        Args:
            state: One of 'running', 'stopped', 'warning', 'unknown'
        """
        color_map = {
            'running': 'green',
            'stopped': 'gray',
            'warning': 'yellow',
            'error': 'red',
            'unknown': 'gray',
        }
        self._set_color(color_map.get(state, 'gray'))


class StatusWidget(QWidget):
    """
    Widget displaying current Docker and container status.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Container status row
        container_row = QHBoxLayout()

        self.container_indicator = StatusIndicator()
        container_row.addWidget(self.container_indicator)

        container_label = QLabel("Container:")
        container_label.setFont(QFont("", -1, QFont.Bold))
        container_row.addWidget(container_label)

        self.container_status = QLabel("Unknown")
        container_row.addWidget(self.container_status)

        container_row.addStretch()

        self.container_id_label = QLabel("")
        self.container_id_label.setStyleSheet("color: #6b7280;")
        container_row.addWidget(self.container_id_label)

        layout.addLayout(container_row)

        # Docker daemon status row
        daemon_row = QHBoxLayout()

        self.daemon_indicator = StatusIndicator()
        daemon_row.addWidget(self.daemon_indicator)

        daemon_label = QLabel("Docker:")
        daemon_label.setFont(QFont("", -1, QFont.Bold))
        daemon_row.addWidget(daemon_label)

        self.daemon_status = QLabel("Unknown")
        daemon_row.addWidget(self.daemon_status)

        daemon_row.addStretch()

        self.autostart_label = QLabel("")
        self.autostart_label.setStyleSheet("color: #6b7280;")
        daemon_row.addWidget(self.autostart_label)

        layout.addLayout(daemon_row)

        # Web URL row (only visible when running)
        self.url_row = QHBoxLayout()
        url_label = QLabel("Web UI:")
        url_label.setFont(QFont("", -1, QFont.Bold))
        self.url_row.addWidget(url_label)

        self.url_value = QLabel("")
        self.url_value.setStyleSheet("color: #3b82f6;")
        self.url_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.url_row.addWidget(self.url_value)

        self.url_row.addStretch()

        layout.addLayout(self.url_row)

        # Network access info (for TV/Kodi/other devices)
        self.network_group = QGroupBox("Connect from Other Devices")
        network_layout = QVBoxLayout(self.network_group)
        network_layout.setSpacing(4)

        # LAN URL
        lan_row = QHBoxLayout()
        lan_label = QLabel("TV / Kodi / Phone:")
        lan_row.addWidget(lan_label)
        self.lan_url = QLabel("")
        self.lan_url.setStyleSheet("color: #3b82f6; font-weight: bold;")
        self.lan_url.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lan_row.addWidget(self.lan_url)
        lan_row.addStretch()
        network_layout.addLayout(lan_row)

        # Help text
        self.network_help = QLabel(
            "Use this address in Jellyfin apps on your TV, Kodi, phone, etc.\n"
            "Make sure your device is on the same network."
        )
        self.network_help.setStyleSheet("color: #6b7280; font-size: 11px;")
        self.network_help.setWordWrap(True)
        network_layout.addWidget(self.network_help)

        self.network_group.setVisible(False)  # Hidden until running
        layout.addWidget(self.network_group)

        # Image status
        image_row = QHBoxLayout()
        image_label = QLabel("Image:")
        image_label.setFont(QFont("", -1, QFont.Bold))
        image_row.addWidget(image_label)

        self.image_status = QLabel("Not pulled")
        image_row.addWidget(self.image_status)

        image_row.addStretch()
        layout.addLayout(image_row)

    @Slot(object)
    def update_status(self, status: DockerStatus):
        """
        Update the display with new status information.

        Args:
            status: DockerStatus object with current state
        """
        # Docker daemon status
        if status.daemon_state == DaemonState.NOT_INSTALLED:
            self.daemon_indicator.set_state('error')
            self.daemon_status.setText("Not Installed")
        elif status.daemon_state == DaemonState.STOPPED:
            self.daemon_indicator.set_state('stopped')
            self.daemon_status.setText("Stopped")
        else:
            self.daemon_indicator.set_state('running')
            self.daemon_status.setText("Running")

        # Autostart status
        if status.daemon_autostart:
            self.autostart_label.setText("(starts on boot)")
        else:
            self.autostart_label.setText("(manual start)")

        # Container status
        state_display = {
            ContainerState.NOT_FOUND: ("Not Created", "stopped"),
            ContainerState.CREATED: ("Created", "stopped"),
            ContainerState.RUNNING: ("Running", "running"),
            ContainerState.PAUSED: ("Paused", "warning"),
            ContainerState.RESTARTING: ("Restarting", "warning"),
            ContainerState.EXITED: ("Stopped", "stopped"),
            ContainerState.DEAD: ("Dead", "error"),
        }

        text, indicator_state = state_display.get(
            status.container_state,
            ("Unknown", "unknown")
        )
        self.container_status.setText(text)
        self.container_indicator.set_state(indicator_state)

        # Container ID
        if status.container_id:
            self.container_id_label.setText(f"ID: {status.container_id}")
        else:
            self.container_id_label.setText("")

        # Image status
        if status.image_pulled:
            self.image_status.setText("jellyfin/jellyfin:latest")
            self.image_status.setStyleSheet("color: #22c55e;")
        else:
            self.image_status.setText("Not pulled")
            self.image_status.setStyleSheet("color: #6b7280;")

    def set_web_url(self, url: str, port: int = 8096):
        """Set the web UI URL display and show network info."""
        self.url_value.setText(url)

        # Show LAN IP for other devices
        local_ip = get_local_ip()
        if local_ip != "unknown":
            lan_url = f"http://{local_ip}:{port}"
            self.lan_url.setText(lan_url)
            self.network_group.setVisible(True)
        else:
            self.network_group.setVisible(False)

    def clear_web_url(self):
        """Clear the web UI URL display and hide network info."""
        self.url_value.setText("")
        self.lan_url.setText("")
        self.network_group.setVisible(False)

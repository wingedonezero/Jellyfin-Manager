"""
Log viewer widget for displaying real-time container logs.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QPlainTextEdit, QLabel, QCheckBox
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat


class LogViewer(QWidget):
    """
    Widget for displaying and managing container logs.

    Features:
    - Real-time log streaming display
    - Auto-scroll with pause option
    - Clear functionality
    - Basic syntax highlighting for log levels
    """

    # Maximum number of log lines to keep
    MAX_LINES = 5000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._auto_scroll = True
        self._line_count = 0
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Header with controls
        header = QHBoxLayout()

        title = QLabel("Logs")
        title.setFont(QFont("", -1, QFont.Bold))
        header.addWidget(title)

        header.addStretch()

        self.auto_scroll_checkbox = QCheckBox("Auto-scroll")
        self.auto_scroll_checkbox.setChecked(True)
        header.addWidget(self.auto_scroll_checkbox)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedWidth(70)
        header.addWidget(self.clear_btn)

        layout.addLayout(header)

        # Log display area
        self.log_display = QPlainTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Monospace", 9))
        self.log_display.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log_display.setMaximumBlockCount(self.MAX_LINES)

        # Styling
        self.log_display.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
        """)

        layout.addWidget(self.log_display)

        # Status bar
        status_bar = QHBoxLayout()

        self.status_label = QLabel("Waiting for logs...")
        self.status_label.setStyleSheet("color: #6b7280;")
        status_bar.addWidget(self.status_label)

        status_bar.addStretch()

        self.line_count_label = QLabel("0 lines")
        self.line_count_label.setStyleSheet("color: #6b7280;")
        status_bar.addWidget(self.line_count_label)

        layout.addLayout(status_bar)

    def _connect_signals(self):
        """Connect widget signals."""
        self.clear_btn.clicked.connect(self.clear)
        self.auto_scroll_checkbox.stateChanged.connect(self._on_auto_scroll_changed)

    @Slot(str)
    def append_log(self, line: str):
        """
        Append a log line to the display.

        Args:
            line: The log line to append
        """
        # Apply syntax highlighting based on log level
        cursor = self.log_display.textCursor()
        cursor.movePosition(QTextCursor.End)

        # Determine color based on content
        format = QTextCharFormat()

        line_lower = line.lower()
        if '[err]' in line_lower or 'error' in line_lower or 'exception' in line_lower:
            format.setForeground(QColor('#f87171'))  # Red
        elif '[wrn]' in line_lower or 'warn' in line_lower:
            format.setForeground(QColor('#fbbf24'))  # Yellow
        elif '[inf]' in line_lower or 'info' in line_lower:
            format.setForeground(QColor('#60a5fa'))  # Blue
        elif '[dbg]' in line_lower or 'debug' in line_lower:
            format.setForeground(QColor('#9ca3af'))  # Gray
        else:
            format.setForeground(QColor('#d4d4d4'))  # Default

        cursor.insertText(line + '\n', format)

        self._line_count += 1
        self.line_count_label.setText(f"{self._line_count} lines")

        # Auto-scroll if enabled
        if self._auto_scroll:
            self.log_display.verticalScrollBar().setValue(
                self.log_display.verticalScrollBar().maximum()
            )

    @Slot()
    def clear(self):
        """Clear all logs from the display."""
        self.log_display.clear()
        self._line_count = 0
        self.line_count_label.setText("0 lines")
        self.status_label.setText("Logs cleared")

    @Slot(int)
    def _on_auto_scroll_changed(self, state):
        """Handle auto-scroll checkbox change."""
        self._auto_scroll = state == Qt.Checked
        if self._auto_scroll:
            # Scroll to bottom immediately
            self.log_display.verticalScrollBar().setValue(
                self.log_display.verticalScrollBar().maximum()
            )

    def set_status(self, message: str):
        """Set the status bar message."""
        self.status_label.setText(message)

    def set_streaming(self, streaming: bool):
        """Update UI to reflect streaming state."""
        if streaming:
            self.status_label.setText("Streaming logs...")
            self.status_label.setStyleSheet("color: #22c55e;")
        else:
            self.status_label.setText("Log streaming stopped")
            self.status_label.setStyleSheet("color: #6b7280;")

    def load_initial_logs(self, logs: str):
        """
        Load initial/historical logs.

        Args:
            logs: Multi-line string of historical logs
        """
        self.clear()
        for line in logs.split('\n'):
            if line.strip():
                self.append_log(line)
        self.status_label.setText("Historical logs loaded")

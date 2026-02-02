#!/usr/bin/env python3
"""
Jellyfin Manager - A PySide6 application for managing Jellyfin in Docker.

This application provides an easy-to-use interface for:
- Setting up and managing a Jellyfin Docker container
- Starting and stopping the container with one click
- Managing Docker daemon lifecycle
- Streaming container logs in real-time
- Configuring media paths and hardware acceleration
"""

import sys

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt


def check_dependencies() -> tuple[bool, str]:
    """
    Check if required dependencies are available.

    Returns:
        Tuple of (success, error_message)
    """
    # Check for docker Python package
    try:
        import docker
    except ImportError:
        return False, (
            "Python 'docker' package is not installed.\n\n"
            "Install it with: pip install docker"
        )

    # Check for Docker CLI
    import shutil
    if not shutil.which("docker"):
        return False, (
            "Docker is not installed on this system.\n\n"
            "Please install Docker first:\n"
            "  - Arch/EndeavourOS: sudo pacman -S docker\n"
            "  - Then add your user to docker group:\n"
            "    sudo usermod -aG docker $USER\n"
            "  - Log out and back in for group changes to take effect"
        )

    return True, ""


def main():
    """Main application entry point."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Jellyfin Manager")
    app.setOrganizationName("JellyfinManager")

    # Check dependencies before showing main window
    deps_ok, error_msg = check_dependencies()
    if not deps_ok:
        QMessageBox.critical(
            None,
            "Missing Dependencies",
            error_msg
        )
        return 1

    # Import here to avoid issues if PySide6 is missing
    from ui.main_window import MainWindow

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

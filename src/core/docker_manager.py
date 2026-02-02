"""
Docker management for Jellyfin container.

Handles all Docker operations including daemon management,
container lifecycle, and image management.
"""

import subprocess
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Generator

try:
    import docker
    from docker.errors import DockerException, NotFound, APIError
    DOCKER_SDK_AVAILABLE = True
except ImportError:
    DOCKER_SDK_AVAILABLE = False


class ContainerState(Enum):
    """Possible states of the Jellyfin container."""
    NOT_FOUND = "not_found"
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    EXITED = "exited"
    DEAD = "dead"


class DaemonState(Enum):
    """Possible states of the Docker daemon."""
    NOT_INSTALLED = "not_installed"
    STOPPED = "stopped"
    RUNNING = "running"


@dataclass
class DockerStatus:
    """Current status of Docker and container."""
    daemon_state: DaemonState
    daemon_autostart: bool
    container_state: ContainerState
    container_id: Optional[str] = None
    image_pulled: bool = False
    error_message: Optional[str] = None


class DockerManager:
    """Manages Docker daemon and Jellyfin container."""

    def __init__(self, config):
        """
        Initialize Docker manager.

        Args:
            config: AppConfig instance with container settings
        """
        self.config = config
        self._client: Optional['docker.DockerClient'] = None

    @property
    def client(self) -> Optional['docker.DockerClient']:
        """Get Docker client, creating if needed."""
        if not DOCKER_SDK_AVAILABLE:
            return None

        if self._client is None:
            try:
                self._client = docker.from_env()
                # Test connection
                self._client.ping()
            except DockerException:
                self._client = None

        return self._client

    def refresh_client(self) -> bool:
        """Refresh the Docker client connection. Returns True if successful."""
        self._client = None
        return self.client is not None

    # =========================================================================
    # Daemon Management
    # =========================================================================

    def is_docker_installed(self) -> bool:
        """Check if Docker is installed on the system."""
        return shutil.which("docker") is not None

    def is_daemon_running(self) -> bool:
        """Check if Docker daemon is currently running."""
        if not DOCKER_SDK_AVAILABLE:
            # Fallback to command line check
            try:
                result = subprocess.run(
                    ["docker", "info"],
                    capture_output=True,
                    timeout=5
                )
                return result.returncode == 0
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return False

        return self.client is not None

    def is_daemon_autostart_enabled(self) -> bool:
        """Check if Docker daemon is set to start on boot (systemd)."""
        try:
            result = subprocess.run(
                ["systemctl", "is-enabled", "docker"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip() == "enabled"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def set_daemon_autostart(self, enabled: bool) -> tuple[bool, str]:
        """
        Enable or disable Docker daemon autostart.

        Returns:
            Tuple of (success, message)
        """
        action = "enable" if enabled else "disable"
        try:
            result = subprocess.run(
                ["pkexec", "systemctl", action, "docker"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return True, f"Docker autostart {action}d successfully"
            else:
                return False, f"Failed to {action} autostart: {result.stderr}"
        except subprocess.TimeoutExpired:
            return False, "Operation timed out"
        except FileNotFoundError:
            return False, "systemctl not found"

    def start_daemon(self) -> tuple[bool, str]:
        """
        Start the Docker daemon.

        Returns:
            Tuple of (success, message)
        """
        if self.is_daemon_running():
            return True, "Docker daemon is already running"

        try:
            result = subprocess.run(
                ["pkexec", "systemctl", "start", "docker"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                # Wait a moment and refresh client
                import time
                time.sleep(1)
                self.refresh_client()
                return True, "Docker daemon started successfully"
            else:
                return False, f"Failed to start daemon: {result.stderr}"
        except subprocess.TimeoutExpired:
            return False, "Operation timed out"
        except FileNotFoundError:
            return False, "systemctl not found"

    def stop_daemon(self) -> tuple[bool, str]:
        """
        Stop the Docker daemon.

        Returns:
            Tuple of (success, message)
        """
        if not self.is_daemon_running():
            return True, "Docker daemon is already stopped"

        try:
            result = subprocess.run(
                ["pkexec", "systemctl", "stop", "docker", "docker.socket"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                self._client = None
                return True, "Docker daemon stopped successfully"
            else:
                return False, f"Failed to stop daemon: {result.stderr}"
        except subprocess.TimeoutExpired:
            return False, "Operation timed out"
        except FileNotFoundError:
            return False, "systemctl not found"

    # =========================================================================
    # Image Management
    # =========================================================================

    def is_image_pulled(self) -> bool:
        """Check if the Jellyfin image is available locally."""
        if self.client is None:
            return False

        try:
            self.client.images.get(self.config.container.image)
            return True
        except NotFound:
            return False
        except APIError:
            return False

    def pull_image(self) -> Generator[str, None, bool]:
        """
        Pull the Jellyfin Docker image.

        Yields:
            Progress messages

        Returns:
            True if successful
        """
        if self.client is None:
            yield "Error: Docker client not available"
            return False

        try:
            yield f"Pulling {self.config.container.image}..."

            # Pull with progress
            for line in self.client.api.pull(
                self.config.container.image,
                stream=True,
                decode=True
            ):
                if 'status' in line:
                    status = line['status']
                    if 'progress' in line:
                        yield f"{status}: {line['progress']}"
                    else:
                        yield status

            yield "Image pulled successfully!"
            return True

        except APIError as e:
            yield f"Error pulling image: {e}"
            return False

    # =========================================================================
    # Container Management
    # =========================================================================

    def get_container_state(self) -> ContainerState:
        """Get the current state of the Jellyfin container."""
        if self.client is None:
            return ContainerState.NOT_FOUND

        try:
            container = self.client.containers.get(self.config.container.container_name)
            status = container.status
            return ContainerState(status)
        except NotFound:
            return ContainerState.NOT_FOUND
        except APIError:
            return ContainerState.NOT_FOUND

    def get_full_status(self) -> DockerStatus:
        """Get complete status of Docker and container."""
        if not self.is_docker_installed():
            return DockerStatus(
                daemon_state=DaemonState.NOT_INSTALLED,
                daemon_autostart=False,
                container_state=ContainerState.NOT_FOUND,
                error_message="Docker is not installed"
            )

        daemon_running = self.is_daemon_running()

        if not daemon_running:
            return DockerStatus(
                daemon_state=DaemonState.STOPPED,
                daemon_autostart=self.is_daemon_autostart_enabled(),
                container_state=ContainerState.NOT_FOUND
            )

        container_state = self.get_container_state()
        container_id = None

        if container_state != ContainerState.NOT_FOUND:
            try:
                container = self.client.containers.get(self.config.container.container_name)
                container_id = container.short_id
            except (NotFound, APIError):
                pass

        return DockerStatus(
            daemon_state=DaemonState.RUNNING,
            daemon_autostart=self.is_daemon_autostart_enabled(),
            container_state=container_state,
            container_id=container_id,
            image_pulled=self.is_image_pulled()
        )

    def create_container(self) -> tuple[bool, str]:
        """
        Create the Jellyfin container with current configuration.

        Returns:
            Tuple of (success, message)
        """
        if self.client is None:
            return False, "Docker client not available"

        # Check if container already exists
        if self.get_container_state() != ContainerState.NOT_FOUND:
            return False, "Container already exists. Remove it first to recreate."

        # Build volume mounts
        volumes = {
            str(self.config.config_dir): {
                'bind': self.config.container.config_mount,
                'mode': 'rw'
            },
            str(self.config.cache_dir): {
                'bind': self.config.container.cache_mount,
                'mode': 'rw'
            },
        }

        # Mount media paths
        for i, media_path in enumerate(self.config.media_paths):
            mount_point = f"{self.config.container.media_mount_base}/{media_path.name}"
            # Handle duplicate folder names by adding index
            if mount_point in [v['bind'] for v in volumes.values()]:
                mount_point = f"{self.config.container.media_mount_base}/{media_path.name}_{i}"
            volumes[str(media_path)] = {
                'bind': mount_point,
                'mode': 'rw'
            }

        # Build environment and devices for hardware acceleration
        environment = {}
        devices = []

        if self.config.enable_hw_accel and self.config.hw_accel_type == "vaapi":
            # AMD/Intel VAAPI
            devices.append("/dev/dri:/dev/dri")

        try:
            container = self.client.containers.create(
                image=self.config.container.image,
                name=self.config.container.container_name,
                ports={f'{self.config.container.web_port}/tcp': self.config.container.web_port},
                volumes=volumes,
                environment=environment,
                devices=devices,
                restart_policy={"Name": "no"},  # We manage restarts ourselves
                detach=True
            )
            return True, f"Container created successfully (ID: {container.short_id})"

        except APIError as e:
            return False, f"Failed to create container: {e}"

    def start_container(self) -> tuple[bool, str]:
        """
        Start the Jellyfin container.

        Returns:
            Tuple of (success, message)
        """
        if self.client is None:
            return False, "Docker client not available"

        state = self.get_container_state()

        if state == ContainerState.NOT_FOUND:
            return False, "Container does not exist. Run setup first."

        if state == ContainerState.RUNNING:
            return True, "Container is already running"

        try:
            container = self.client.containers.get(self.config.container.container_name)
            container.start()
            return True, "Container started successfully"
        except APIError as e:
            return False, f"Failed to start container: {e}"

    def stop_container(self) -> tuple[bool, str]:
        """
        Stop the Jellyfin container.

        Returns:
            Tuple of (success, message)
        """
        if self.client is None:
            return False, "Docker client not available"

        state = self.get_container_state()

        if state == ContainerState.NOT_FOUND:
            return True, "Container does not exist"

        if state == ContainerState.EXITED:
            return True, "Container is already stopped"

        try:
            container = self.client.containers.get(self.config.container.container_name)
            container.stop(timeout=10)
            return True, "Container stopped successfully"
        except APIError as e:
            return False, f"Failed to stop container: {e}"

    def remove_container(self) -> tuple[bool, str]:
        """
        Remove the Jellyfin container (keeps data).

        Returns:
            Tuple of (success, message)
        """
        if self.client is None:
            return False, "Docker client not available"

        state = self.get_container_state()

        if state == ContainerState.NOT_FOUND:
            return True, "Container does not exist"

        # Stop first if running
        if state == ContainerState.RUNNING:
            success, msg = self.stop_container()
            if not success:
                return False, f"Failed to stop container before removal: {msg}"

        try:
            container = self.client.containers.get(self.config.container.container_name)
            container.remove()
            return True, "Container removed successfully (data preserved)"
        except APIError as e:
            return False, f"Failed to remove container: {e}"

    def get_logs(self, tail: int = 100) -> str:
        """
        Get recent container logs.

        Args:
            tail: Number of lines to retrieve

        Returns:
            Log content as string
        """
        if self.client is None:
            return "Docker client not available"

        try:
            container = self.client.containers.get(self.config.container.container_name)
            logs = container.logs(tail=tail, timestamps=True)
            return logs.decode('utf-8', errors='replace')
        except NotFound:
            return "Container not found"
        except APIError as e:
            return f"Error getting logs: {e}"

    def stream_logs(self) -> Generator[str, None, None]:
        """
        Stream container logs in real-time.

        Yields:
            Log lines as they come in
        """
        if self.client is None:
            yield "Docker client not available"
            return

        try:
            container = self.client.containers.get(self.config.container.container_name)
            for line in container.logs(stream=True, follow=True, timestamps=True):
                yield line.decode('utf-8', errors='replace').rstrip()
        except NotFound:
            yield "Container not found"
        except APIError as e:
            yield f"Error streaming logs: {e}"

    def get_web_url(self) -> str:
        """Get the URL to access Jellyfin web interface."""
        return f"http://localhost:{self.config.container.web_port}"

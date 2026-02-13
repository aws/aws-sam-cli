"""
Platform-specific configuration file readers for administrator settings.
"""

import logging
import os
import platform
import plistlib
from abc import ABC, abstractmethod
from typing import Optional

from samcli.local.docker.container_engine import ContainerEngine

LOG = logging.getLogger(__name__)


class PlatformHandler(ABC):
    """
    Abstract base class for platform-specific configuration file readers.
    """

    def read_config(self) -> Optional[str]:
        """
        Reads the configuration file and returns the administrator container preference.
        """
        container_preference = self._read_config()
        return container_preference.lower().strip() if container_preference else None

    @abstractmethod
    def _read_config(self) -> Optional[str]:
        """
        Reads the configuration file and returns the administrator container preference.
        """
        pass

    @abstractmethod
    def get_finch_socket_path(self) -> Optional[str]:
        """
        Returns the socket path for the platform.
        """
        pass

    @abstractmethod
    def supports_finch(self) -> bool:
        """
        Returns True if Finch is supported on this platform.
        """
        pass

    @abstractmethod
    def get_container_not_reachable_message(self) -> str:
        """
        Returns platform-specific error message when container runtime is not reachable.
        """
        pass


class MacOSHandler(PlatformHandler):
    """
    macOS specific configuration reader.
    """

    def _read_config(self) -> Optional[str]:
        """
        Reads the macOS configuration file to determine the administrator container preference.
        """
        plist_path = "/Library/Preferences/com.amazon.samcli.plist"

        if not os.path.exists(plist_path):
            LOG.debug("Administrator config file not found on macOS: %s.", plist_path)
            return None

        try:
            with open(plist_path, "rb") as plist_file:
                plist_data = plistlib.load(plist_file)
                container_runtime = plist_data.get("DefaultContainerRuntime")
                return str(container_runtime) if container_runtime is not None else None
        except (FileNotFoundError, OSError, plistlib.InvalidFileException) as e:
            LOG.debug("Error reading macOS administrator config: %s.", str(e))
            return None

    def get_finch_socket_path(self) -> Optional[str]:
        """
        Returns the socket path for the macOS.
        """
        return "unix:////Applications/Finch/lima/data/finch/sock/finch.sock"

    def supports_finch(self) -> bool:
        """
        Returns True if Finch is supported on macOS.
        """
        return True

    def get_container_not_reachable_message(self) -> str:
        """
        Returns macOS-specific error message when container runtime is not reachable.
        """
        admin_preference = self.read_config()

        if admin_preference:
            if admin_preference == ContainerEngine.FINCH.value:
                return "Running AWS SAM projects locally requires Finch. Do you have Finch installed and running?"
            elif admin_preference == ContainerEngine.DOCKER.value:
                return "Running AWS SAM projects locally requires Docker. Do you have Docker installed and running?"

        return (
            "Running AWS SAM projects locally requires a container runtime. "
            "Do you have Docker or Finch installed and running?"
        )


class LinuxHandler(PlatformHandler):
    """
    Linux specific configuration reader.
    """

    def _read_config(self) -> Optional[str]:
        """
        TODO: Reads the Linux configuration file to determine the administrator container preference.
        Placeholder for future implementation.
        """
        return None

    def get_finch_socket_path(self) -> Optional[str]:
        """
        Returns the socket path for Linux, checking multiple locations.

        On Linux, Finch can use either a Finch-specific socket or the underlying
        containerd socket via nerdctl.

        Priority order:
        1. XDG_RUNTIME_DIR/finch.sock (Finch-specific socket)
        2. ~/.finch/finch.sock (user home directory)
        3. /var/run/finch.sock (system-wide)
        4. XDG_RUNTIME_DIR/containerd/containerd.sock (rootless containerd fallback)

        Note: The containerd socket is checked last as a fallback since it may be
        shared by multiple container tools. Finch-specific sockets are preferred
        for accurate telemetry reporting.

        Returns:
            Optional[str]: Socket path if found, None otherwise
        """

        # Check XDG_RUNTIME_DIR for Finch-specific socket first
        xdg_runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
        if xdg_runtime_dir:
            # Finch-specific socket in XDG_RUNTIME_DIR
            finch_sock = os.path.join(xdg_runtime_dir, "finch.sock")
            if os.path.exists(finch_sock):
                LOG.debug(f"Found Finch socket at XDG_RUNTIME_DIR: {finch_sock}")
                return f"unix://{finch_sock}"

        # Check user home directory for Finch VM socket
        home_dir = os.path.expanduser("~")
        home_finch_sock = os.path.join(home_dir, ".finch", "finch.sock")
        if os.path.exists(home_finch_sock):
            LOG.debug(f"Found Finch socket in home directory: {home_finch_sock}")
            return f"unix://{home_finch_sock}"

        # System-wide socket
        system_sock = "/var/run/finch.sock"
        if os.path.exists(system_sock):
            LOG.debug(f"Found Finch socket at system location: {system_sock}")
            return f"unix://{system_sock}"

        # Fallback: Check for rootless containerd socket
        # This is checked last since containerd may be used by other tools
        if xdg_runtime_dir:
            containerd_sock = os.path.join(xdg_runtime_dir, "containerd", "containerd.sock")
            if os.path.exists(containerd_sock):
                LOG.debug(
                    f"Found containerd socket at XDG_RUNTIME_DIR (fallback): {containerd_sock}. "
                    "Note: This socket may be shared with other containerd-based tools."
                )
                return f"unix://{containerd_sock}"

        # No socket found - return None to enable future CLI fallback
        LOG.warn("No Finch socket found in standard locations")
        return None

    def supports_finch(self) -> bool:
        """
        Returns True if Finch is supported on Linux.
        """
        return True

    def get_container_not_reachable_message(self) -> str:
        """
        Returns Linux-specific error message when container runtime is not reachable.
        """
        admin_preference = self.read_config()

        if admin_preference:

            if admin_preference == ContainerEngine.FINCH.value:
                return "Running AWS SAM projects locally requires Finch. Do you have Finch installed and running?"
            elif admin_preference == ContainerEngine.DOCKER.value:
                return "Running AWS SAM projects locally requires Docker. Do you have Docker installed and running?"

        return (
            "Running AWS SAM projects locally requires a container runtime. "
            "Do you have Docker or Finch installed and running?"
        )


class WindowsHandler(PlatformHandler):
    """
    Windows specific configuration reader.
    """

    def _read_config(self) -> Optional[str]:
        """
        TODO: Reads the Windows configuration file to determine the administrator container preference.
        Placeholder for future implementation.
        """
        return None

    def get_finch_socket_path(self) -> Optional[str]:
        """Finch daemon not supported on Windows yet."""
        LOG.debug("Finch not supported on Windows yet.")
        return None

    def supports_finch(self) -> bool:
        """
        Returns False as Finch is not supported on Windows.
        """
        return False

    def get_container_not_reachable_message(self) -> str:
        """
        Returns Windows-specific error message when container runtime is not reachable.
        """
        return (
            "Running AWS SAM projects locally requires a container runtime. Do you have Docker installed and running?"
        )


_PLATFORM_HANDLERS = {
    "Darwin": lambda: MacOSHandler(),
    "Linux": lambda: LinuxHandler(),
    "Windows": lambda: WindowsHandler(),
}


def get_platform_handler() -> Optional[PlatformHandler]:
    """
    Get the appropriate platform handler for the current platform.
    """
    handler_factory = _PLATFORM_HANDLERS.get(platform.system())
    return handler_factory() if handler_factory else None


def get_finch_socket_path() -> Optional[str]:
    """
    Get Finch socket path for the current platform.

    This utility function provides a convenient way to get the Finch socket path
    without needing to manually handle platform detection and handler creation.

    Returns:
        Optional[str]: The Finch socket path if available on this platform, None otherwise
    """
    handler = get_platform_handler()
    if not handler or not handler.supports_finch():
        return None
    return handler.get_finch_socket_path()

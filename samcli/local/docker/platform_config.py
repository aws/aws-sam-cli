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
        LOG.debug("Linux administrator config reading not implemented yet.")
        return None

    def get_finch_socket_path(self) -> Optional[str]:
        """
        Returns the socket path for Linux.
        """

        # Default fallback to system socket
        return "unix:///var/run/finch.sock"

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
        LOG.debug("Windows administrator config reading not implemented yet.")
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

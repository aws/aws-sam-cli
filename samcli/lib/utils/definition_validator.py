"""DefinitionValidator for Validating YAML and JSON Files"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from samcli.yamlhelper import parse_yaml_file

LOG = logging.getLogger(__name__)


class DefinitionValidator:
    _path: Path
    _detect_change: bool
    _data: Optional[Dict[str, Any]]
    _st_size: Optional[int]
    _st_mtime: Optional[int]

    def __init__(self, path: Path, detect_change: bool = True, initialize_data: bool = True) -> None:
        """
        Validator for JSON and YAML files.
        Calling validate_change() will return True if the definition is valid and has changes.

        Parameters
        ----------
        path : Path
            Path to the definition file
        detect_change : bool, optional
            validation will only be successful if there are changes between current and previous data,
            by default True
        initialize_data : bool, optional
            Should initialize existing definition data before the first validate, by default True
            Used along with detect_change
        """
        super().__init__()
        self._path = path
        self._detect_change = detect_change
        self._data = None
        self._st_size = None
        self._st_mtime = None
        if initialize_data:
            self.validate_change()

    def validate_change(self, event=None) -> bool:
        """Validate change on json or yaml file.

        Returns
        -------
        bool
            True if it is valid, False otherwise.
            If detect_change is set, False will also be returned if there is
            no change compared to the previous validation.
        """
        # old_data = self._data
        old_size = self._st_size
        old_mtime = self._st_mtime

        if event and event.event_type == "opened":
            return False
        if event and event.event_type != "opened":
            LOG.info("validate on event: %s", event)
        if not self.validate_file(event):
            return False
        if event and event.event_type != "opened":
            LOG.info("detect_change: %s", self._detect_change)
            LOG.info("old: %s | %s", old_size, old_mtime)
            LOG.info("new: %s | %s", self._st_size, self._st_mtime)
        if (old_size != self._st_size or old_mtime != self._st_mtime):
            LOG.info("changed! (event: %s)", event)
            LOG.info("old: %s | %s", old_size, old_mtime)
            LOG.info("new: %s | %s", self._st_size, self._st_mtime)
        return (old_size != self._st_size or old_mtime != self._st_mtime) if self._detect_change else True

    def validate_file(self, event=None) -> bool:
        """Validate json or yaml file.

        Returns
        -------
        bool
            True if it is valid path and yaml file, False otherwise.
        """
        if event and event.event_type != "opened":
            LOG.info("path %s exists: %s", self._path, self._path.exists())
        try:
            stat = os.stat(self._path)
            self._st_size = stat.st_size
            self._st_mtime = stat.st_mtime
        except FileNotFoundError:
            LOG.debug(
                "File %s failed to validate due to file path does not exist. Please verify that the path is valid.",
                self._path,
            )
            return False

        return True

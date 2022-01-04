"""DefinitionValidator for Validating YAML and JSON Files"""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from samcli.yamlhelper import parse_yaml_file

LOG = logging.getLogger(__name__)


class DefinitionValidator:
    _path: Path
    _detect_change: bool
    _data: Optional[Dict[str, Any]]

    def __init__(self, path: Path, detect_change: bool = True, initialize_data: bool = True) -> None:
        """
        Validator for JSON and YAML files.
        Calling validate() will return True if the definition is valid and
        has changes.

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
        if initialize_data:
            self.validate()

    def validate(self) -> bool:
        """Validate json or yaml file.

        Returns
        -------
        bool
            True if it is valid, False otherwise.
            If detect_change is set, False will also be returned if there is
            no change compared to the previous validation.
        """
        if not self._path.exists():
            return False

        old_data = self._data
        try:
            self._data = parse_yaml_file(str(self._path))
            return old_data != self._data if self._detect_change else True
        except (ValueError, yaml.YAMLError) as e:
            LOG.debug("DefinitionValidator failed to validate.", exc_info=e)
            return False

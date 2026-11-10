"""Utility Class for Getting Function or Layer Manifest Dependency Hashes"""

import os
import pathlib
from typing import Any, List, Optional

from aws_lambda_builders.workflows.python_uv.utils import detect_uv_manifest

from samcli.lib.build.workflow_config import get_workflow_config
from samcli.lib.utils.hash import file_checksum, str_checksum

PYTHON_UV_BUILD_METHOD = "python-uv"


# TODO Expand this class to hash specific sections of the manifest
class DependencyHashGenerator:
    _code_uri: str
    _base_dir: str
    _code_dir: str
    _runtime: str
    _build_method: Optional[str]
    _manifest_path_override: Optional[str]
    _hash_generator: Any
    _calculated: bool
    _hash: Optional[str]

    def __init__(
        self,
        code_uri: str,
        base_dir: str,
        runtime: str,
        manifest_path_override: Optional[str] = None,
        hash_generator: Any = None,
        build_method: Optional[str] = None,
    ):
        """
        Parameters
        ----------
        code_uri : str
            Relative path specified in the function/layer resource
        base_dir : str
            Absolute path which the function/layer dir is located
        runtime : str
            Runtime of the function/layer
        manifest_path_override : Optional[str], optional
            Override default manifest path for each runtime, by default None
        hash_generator : Any, optional
            Hash generation function. Can be hashlib.md5(), hashlib.sha256(), etc, by default None
        build_method : Optional[str], optional
            BuildMethod from the resource metadata, by default None
        """
        self._code_uri = code_uri
        self._base_dir = base_dir
        self._code_dir = str(pathlib.Path(self._base_dir, self._code_uri).resolve())
        self._runtime = runtime
        self._manifest_path_override = manifest_path_override
        self._build_method = build_method
        self._hash_generator = hash_generator
        self._calculated = False
        self._hash = None

    def _calculate_dependency_hash(self) -> Optional[str]:
        """Calculate the manifest file hash

        Returns
        -------
        Optional[str]
            Returns manifest hash. If manifest does not exist or not supported, None will be returned.
        """
        if self._manifest_path_override:
            manifest_file = self._manifest_path_override
        elif PYTHON_UV_BUILD_METHOD in (self._build_method, self._runtime):
            return self._calculate_uv_dependency_hash()
        else:
            config = get_workflow_config(self._runtime, self._code_dir, self._base_dir)
            manifest_file = config.manifest_name

        if not manifest_file:
            return None

        manifest_path = pathlib.Path(self._code_dir, manifest_file).resolve()
        if not manifest_path.is_file():
            return None

        return file_checksum(str(manifest_path), hash_generator=self._hash_generator)

    def _calculate_uv_dependency_hash(self) -> Optional[str]:
        """Hash the manifest Lambda Builders detects and, for pyproject.toml, the nearest uv.lock"""
        manifest = detect_uv_manifest(self._code_dir)
        if not manifest:
            return None

        files: List[pathlib.Path] = [pathlib.Path(manifest).resolve()]
        if files[0].name == "pyproject.toml":
            lock = next(
                (d / "uv.lock" for d in (files[0].parent, *files[0].parent.parents) if (d / "uv.lock").is_file()),
                None,
            )
            if lock:
                files.append(lock)
                root_pyproject = lock.parent / "pyproject.toml"
                if root_pyproject != files[0] and root_pyproject.is_file():
                    files.append(root_pyproject)

        # relative paths keep the hash stable when the project directory moves
        checksums = "\n".join(f"{os.path.relpath(path, self._code_dir)}:{file_checksum(str(path))}" for path in files)
        return str_checksum(checksums, hash_generator=self._hash_generator)

    @property
    def hash(self) -> Optional[str]:
        """
        Returns
        -------
        Optional[str]
            Hash for dependencies in the manifest.
            If the manifest does not exist or not supported, this value will be None.
        """
        if not self._calculated:
            self._hash = self._calculate_dependency_hash()
            self._calculated = True
        return self._hash

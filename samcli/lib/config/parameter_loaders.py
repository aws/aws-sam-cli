"""
Parameter file loading utilities for SAM CLI configuration
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ruamel.yaml import YAML, YAMLError

from samcli.lib.config.exceptions import FileParseException

LOG = logging.getLogger(__name__)


class ParameterFileLoader:
    """
    Loads parameters from external parameter files.
    Supports JSON, YAML, and ENV file formats.
    Follows existing SAM CLI FileManager patterns.
    """

    @staticmethod
    def is_file_url(parameter_value: Optional[str]) -> bool:
        """
        Check if a parameter value is a file:// URL.
        
        Parameters
        ----------
        parameter_value : str, optional
            Parameter value to check
            
        Returns
        -------
        bool
            True if parameter_value is a file:// URL
        """
        if not isinstance(parameter_value, str):
            return False
        return parameter_value.startswith("file://")

    @staticmethod
    def parse_file_url(file_url: str) -> str:
        """
        Parse file:// URL and return the file path with environment variable expansion.
        
        Parameters
        ----------
        file_url : str
            File URL in format file://path/to/file.ext
            
        Returns
        -------
        str
            Expanded file path
            
        Raises
        ------
        ValueError
            If URL format is invalid
        """
        if not ParameterFileLoader.is_file_url(file_url):
            raise ValueError(f"Invalid file URL format: {file_url}")
        
        # Extract path by removing file:// prefix
        # Don't use urlparse because it doesn't handle env vars and relative paths correctly
        file_path = file_url[7:]  # Remove 'file://' prefix
        
        # Handle Windows paths (file:///C:/path/to/file)
        if os.name == 'nt' and file_path.startswith('/') and ':' in file_path[1:3]:
            file_path = file_path[1:]
            
        # Expand environment variables before returning
        expanded_path = os.path.expandvars(file_path)
        
        LOG.debug(f"Parsed file URL '{file_url}' to path '{expanded_path}'")
        return expanded_path

    @staticmethod
    def load_from_file(file_path: str) -> Dict:
        """
        Load parameters from a file based on its extension.
        
        Supported formats:
        - .json: JSON format
        - .yaml/.yml: YAML format  
        - .env: Environment variable format
        
        Parameters
        ----------
        file_path : str
            Path to the parameter file
            
        Returns
        -------
        Dict
            Dictionary of loaded parameters
            
        Raises
        ------
        FileNotFoundError
            If file doesn't exist
        FileParseException
            If file format is invalid or unsupported
        """
        path_obj = Path(file_path)
        
        if not path_obj.exists():
            raise FileNotFoundError(f"Parameter file not found: {file_path}")
            
        if not path_obj.is_file():
            raise FileParseException(f"Parameter path is not a file: {file_path}")
            
        extension = path_obj.suffix.lower()
        
        try:
            if extension == '.json':
                return ParameterFileLoader._load_json_file(path_obj)
            elif extension in ['.yaml', '.yml']:
                return ParameterFileLoader._load_yaml_file(path_obj)
            elif extension == '.env':
                return ParameterFileLoader._load_env_file(path_obj)
            else:
                raise FileParseException(
                    f"Unsupported parameter file format: {extension}. "
                    f"Supported formats: .json, .yaml, .yml, .env"
                )
        except Exception as e:
            if isinstance(e, (FileParseException, FileNotFoundError)):
                raise
            raise FileParseException(f"Failed to load parameter file '{file_path}': {str(e)}") from e

    @staticmethod
    def _load_json_file(file_path: Path) -> Dict:
        """
        Load parameters from JSON file.
        
        Parameters
        ----------
        file_path : Path
            Path to JSON file
            
        Returns
        -------
        Dict
            Dictionary of parameters
        """
        try:
            content = file_path.read_text(encoding='utf-8')
            params = json.loads(content)
            
            if not isinstance(params, dict):
                raise FileParseException(f"JSON parameter file must contain an object, got {type(params)}")
                
            LOG.debug(f"Loaded {len(params)} parameters from JSON file: {file_path}")
            return params
            
        except json.JSONDecodeError as e:
            raise FileParseException(f"Invalid JSON in parameter file '{file_path}': {str(e)}") from e

    @staticmethod
    def _load_yaml_file(file_path: Path) -> Dict:
        """
        Load parameters from YAML file.
        
        Parameters
        ----------
        file_path : Path
            Path to YAML file
            
        Returns
        -------
        Dict
            Dictionary of parameters
        """
        yaml = YAML(typ='safe', pure=True)
        
        try:
            content = file_path.read_text(encoding='utf-8')
            params = yaml.load(content)
            
            if params is None:
                return {}
                
            if not isinstance(params, dict):
                raise FileParseException(f"YAML parameter file must contain a mapping, got {type(params)}")
                
            LOG.debug(f"Loaded {len(params)} parameters from YAML file: {file_path}")
            return params
            
        except YAMLError as e:
            raise FileParseException(f"Invalid YAML in parameter file '{file_path}': {str(e)}") from e

    @staticmethod
    def _load_env_file(file_path: Path) -> Dict:
        """
        Load parameters from environment variable file.
        
        Format:
        KEY1=value1
        KEY2=value2
        # Comments are supported
        MULTILINE_KEY="line1
        line2
        line3"
        
        Parameters
        ----------
        file_path : Path
            Path to ENV file
            
        Returns
        -------
        Dict
            Dictionary of parameters
        """
        params: Dict[str, str] = {}
        
        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.splitlines()
            
            current_key: Optional[str] = None
            current_value: List[str] = []
            in_multiline = False
            
            for line_num, raw_line in enumerate(lines, 1):
                line = raw_line.rstrip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                    
                # Handle multiline values
                if in_multiline:
                    if line.endswith('"') and not line.endswith('\\"'):
                        # End of multiline value
                        current_value.append(line[:-1])  # Remove closing quote
                        if current_key is not None:
                            params[current_key] = '\n'.join(current_value)
                        current_key = None
                        current_value = []
                        in_multiline = False
                    else:
                        current_value.append(line)
                    continue
                
                # Parse key=value pairs
                if '=' not in line:
                    LOG.warning(f"Skipping invalid line {line_num} in {file_path}: {line}")
                    continue
                    
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Handle quoted values
                if value.startswith('"'):
                    if value.endswith('"') and len(value) > 1 and not value.endswith('\\"'):
                        # Single line quoted value
                        params[key] = value[1:-1]  # Remove quotes
                    else:
                        # Start of multiline value
                        current_key = key
                        current_value = [value[1:]]  # Remove opening quote
                        in_multiline = True
                else:
                    params[key] = value
                    
            if in_multiline:
                raise FileParseException(f"Unterminated quoted value for key '{current_key}' in {file_path}")
                
            LOG.debug(f"Loaded {len(params)} parameters from ENV file: {file_path}")
            return params
            
        except Exception as e:
            if isinstance(e, FileParseException):
                raise
            raise FileParseException(f"Failed to parse ENV file '{file_path}': {str(e)}") from e

    @staticmethod
    def resolve_parameter_files(parameter_overrides: Optional[str]) -> Tuple[Dict, Dict]:
        """
        Resolve parameter overrides that may contain file:// URLs.
        
        Parameters
        ----------
        parameter_overrides : str, optional
            Parameter overrides string that may contain file:// URLs
            
        Returns
        -------
        Tuple[Dict, Dict]
            Tuple of (direct_parameters, file_parameters)
            - direct_parameters: Parameters specified directly as Key=Value
            - file_parameters: Parameters loaded from files
        """
        if not parameter_overrides:
            return {}, {}
            
        direct_params = {}
        file_params = {}
        
        # Split parameter overrides by spaces, handling quoted values
        import shlex
        try:
            parts = shlex.split(parameter_overrides)
        except ValueError:
            # Fall back to simple split if shlex fails
            parts = parameter_overrides.split()
            
        for part in parts:
            if ParameterFileLoader.is_file_url(part):
                # Load parameters from file
                try:
                    file_path = ParameterFileLoader.parse_file_url(part)
                    loaded_params = ParameterFileLoader.load_from_file(file_path)
                    file_params.update(loaded_params)
                    LOG.info(f"Loaded {len(loaded_params)} parameters from file: {file_path}")
                except Exception as e:
                    LOG.error(f"Failed to load parameters from {part}: {str(e)}")
                    raise
            elif '=' in part:
                # Direct parameter specification
                key, value = part.split('=', 1)
                direct_params[key.strip()] = value.strip()
            else:
                LOG.warning(f"Skipping invalid parameter format: {part}")
                
        return direct_params, file_params

    @staticmethod
    def expand_environment_variables(params: Dict) -> Dict:
        """
        Expand environment variables in parameter values.
        
        Supports ${VAR_NAME} and $VAR_NAME syntax.
        
        Parameters
        ----------
        params : Dict
            Dictionary of parameters
            
        Returns
        -------
        Dict
            Dictionary with expanded environment variables
        """
        expanded = {}
        
        for key, value in params.items():
            if isinstance(value, str):
                expanded[key] = os.path.expandvars(value)
            else:
                expanded[key] = value
                
        return expanded
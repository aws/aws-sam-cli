from PyInstaller.utils import hooks
from .hidden_imports import SAM_CLI_HIDDEN_IMPORTS, SAM_CLI_COLLECT_DATA_PACKAGES

hiddenimports = SAM_CLI_HIDDEN_IMPORTS

datas = sum(hooks.collect_data_files(package) for package in SAM_CLI_COLLECT_DATA_PACKAGES)

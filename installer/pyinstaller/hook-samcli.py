from PyInstaller.utils import hooks
from installer.pyinstaller.hidden_imports import SAM_CLI_HIDDEN_IMPORTS

hiddenimports = SAM_CLI_HIDDEN_IMPORTS

datas = (
    hooks.collect_data_files("samcli")
    + hooks.collect_data_files("samtranslator")
    + hooks.collect_data_files("aws_lambda_builders")
    + hooks.collect_data_files("text_unidecode")
)

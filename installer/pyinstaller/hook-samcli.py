from PyInstaller.utils import hooks
from samcli.cli.hidden_imports import SAM_CLI_HIDDEN_IMPORTS

hiddenimports = SAM_CLI_HIDDEN_IMPORTS

datas = (
    # Collect data files, raw python files (if include_py_files=True) and package metadata directories.
    hooks.collect_all(
        "samcli", include_py_files=True, include_datas=[
            "hook_packages/terraform/copy_terraform_built_artifacts.py",
            "local/lambdafn/zip.py",
        ]
    )[0]
    + hooks.collect_all("jschema_to_python", include_py_files=False)[0]
    + hooks.collect_all("cfnlint", include_py_files=True)[0]
    # Collect ONLY data files.
    + hooks.collect_data_files("samcli")
    + hooks.collect_data_files("samtranslator")
    + hooks.collect_data_files("aws_lambda_builders")
    + hooks.collect_data_files("text_unidecode")
)

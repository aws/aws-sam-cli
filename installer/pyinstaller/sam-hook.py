from PyInstaller.utils import hooks

hiddenimports = [
    'cookiecutter.extensions',
    'samcli.commands.*',
    'jinja2_time',
    'samtranslator',
]

datas = hooks.collect_data_files('samcli') + hooks.collect_data_files('samtranslator')
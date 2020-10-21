from PyInstaller.utils import hooks
hiddenimports = [
    'cookiecutter.extensions',
    'jinja2_time',
    'samtranslator',
    'samcli.commands.init',
    'samcli.commands.validate.validate',
    'samcli.commands.build',
    'samcli.commands.local.local',
    'samcli.commands.package',
    'samcli.commands.deploy',
    'samcli.commands.logs',
    'samcli.commands.publish',
]
imports_for_aws_lambda_builders = (hooks.collect_submodules('aws_lambda_builders'))
hiddenimports += imports_for_aws_lambda_builders
datas = hooks.collect_data_files('samcli') + hooks.collect_data_files('samtranslator') + hooks.collect_data_files('aws_lambda_builders')
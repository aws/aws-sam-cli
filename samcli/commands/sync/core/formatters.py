from samcli.cli.formatters import RootCommandHelpTextFormatter


class SyncCommandHelpTextFormatter(RootCommandHelpTextFormatter):
    # TODO(sriram-mv): Solve this without magic, hate magic constants.
    ADDITIVE_JUSTIFICATION = 22

from unittest import TestCase
from mock import Mock, patch

from botocore.exceptions import NoCredentialsError

from samcli.commands.exceptions import UserException
from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException, InvalidSamTemplateException
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.commands.validate.validate import do_cli, _read_sam_file


class TestDestroyCli(TestCase):
    pass

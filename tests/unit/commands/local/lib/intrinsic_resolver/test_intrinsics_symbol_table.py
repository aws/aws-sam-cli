from unittest import TestCase

import mock
from mock import patch

from samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable


class TestIntrinsicsSymbolTablePseudoProperties(TestCase):
    def setUp(self):
        self.symbol_table = IntrinsicsSymbolTable()

    @patch('samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table.Popen')
    def test_handle_account_id_system(self, mock_subproc_popen):
        process_mock = mock.Mock()
        attrs = {'communicate.return_value': ('12312312312', 0)}
        process_mock.configure_mock(**attrs)
        mock_subproc_popen.return_value = process_mock

        result = self.symbol_table.handle_pseudo_account_id()
        self.assertEquals(result, '12312312312')

    @patch('samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table.Popen')
    @patch('samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table.randint')
    def test_handle_account_id_default(self, random_call, mock_subproc_popen):
        random_call.return_value = 1

        process_mock = mock.Mock()
        attrs = {'communicate.return_value': ('', 0)}
        process_mock.configure_mock(**attrs)
        mock_subproc_popen.return_value = process_mock

        result = self.symbol_table.handle_pseudo_account_id()
        self.assertEquals(result, '111111111111')

    def test_pseudo_partition(self):
        self.assertEquals(self.symbol_table.handle_pseudo_partition(), "aws")

    @patch('samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table.os')
    def test_pseudo_partition_gov(self, mock_os):
        mock_os.getenv.return_value = 'us-west-gov-1'
        self.assertEquals(self.symbol_table.handle_pseudo_partition(), "aws-us-gov")

    @patch('samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table.os')
    def test_pseudo_partition_china(self, mock_os):
        mock_os.getenv.return_value = 'cn-west-1'
        self.assertEquals(self.symbol_table.handle_pseudo_partition(), "aws-cn")

    @patch('samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table.os')
    def test_pseudo_region_environ(self, mock_os):
        mock_os.getenv.return_value = "mytemp"
        self.assertEquals(self.symbol_table.handle_pseudo_region(), "mytemp")

    @patch('samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table.os')
    def test_pseudo_default_region(self, mock_os):
        mock_os.getenv.return_value = None
        self.assertEquals(self.symbol_table.handle_pseudo_region(), "us-east-1")

    def test_pseudo_no_value(self):
        self.assertIsNone(self.symbol_table.handle_pseudo_no_value())

    def test_pseudo_url_prefix_default(self):
        self.assertEquals(self.symbol_table.handle_pseudo_url_prefix(), "amazonaws.com")

    @patch('samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table.os')
    def test_pseudo_url_prefix_china(self, mock_os):
        mock_os.getenv.return_value = "cn-west-1"
        self.assertEquals(self.symbol_table.handle_pseudo_url_prefix(), "amazonaws.com.cn")

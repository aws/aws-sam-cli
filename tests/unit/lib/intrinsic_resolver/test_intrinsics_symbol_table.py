from unittest import TestCase

from mock import patch

from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable


class TestIntrinsicsSymbolTablePseudoProperties(TestCase):
    def setUp(self):
        self.symbol_table = IntrinsicsSymbolTable(template={})

    def test_handle_account_id_default(self):
        self.assertEquals(self.symbol_table.handle_pseudo_account_id(), '123456789012')

    def test_pseudo_partition(self):
        self.assertEquals(self.symbol_table.handle_pseudo_partition(), "aws")

    @patch('samcli.lib.intrinsic_resolver.intrinsics_symbol_table.os')
    def test_pseudo_partition_gov(self, mock_os):
        mock_os.getenv.return_value = 'us-west-gov-1'
        self.assertEquals(self.symbol_table.handle_pseudo_partition(), "aws-us-gov")

    @patch('samcli.lib.intrinsic_resolver.intrinsics_symbol_table.os')
    def test_pseudo_partition_china(self, mock_os):
        mock_os.getenv.return_value = 'cn-west-1'
        self.assertEquals(self.symbol_table.handle_pseudo_partition(), "aws-cn")

    @patch('samcli.lib.intrinsic_resolver.intrinsics_symbol_table.os')
    def test_pseudo_region_environ(self, mock_os):
        mock_os.getenv.return_value = "mytemp"
        self.assertEquals(self.symbol_table.handle_pseudo_region(), "mytemp")

    @patch('samcli.lib.intrinsic_resolver.intrinsics_symbol_table.os')
    def test_pseudo_default_region(self, mock_os):
        mock_os.getenv.return_value = None
        self.assertEquals(self.symbol_table.handle_pseudo_region(), "us-east-1")

    def test_pseudo_no_value(self):
        self.assertIsNone(self.symbol_table.handle_pseudo_no_value())

    def test_pseudo_url_prefix_default(self):
        self.assertEquals(self.symbol_table.handle_pseudo_url_prefix(), "amazonaws.com")

    @patch('samcli.lib.intrinsic_resolver.intrinsics_symbol_table.os')
    def test_pseudo_url_prefix_china(self, mock_os):
        mock_os.getenv.return_value = "cn-west-1"
        self.assertEquals(self.symbol_table.handle_pseudo_url_prefix(), "amazonaws.com.cn")

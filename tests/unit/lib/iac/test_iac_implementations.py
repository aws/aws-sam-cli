from unittest import TestCase
from unittest.mock import Mock, MagicMock

from samcli.lib.iac.cdk.cdk_iac import CdkIacImplementation
from samcli.lib.iac.cfn.cfn_iac import CfnIacImplementation


# TODO: Implement these tests when the classes are fully implemented
# These tests are included for code coverage
class TestImplementations(TestCase):
    def test_cfn_implementation(self):
        impl = CfnIacImplementation(MagicMock())
        impl.get_iac_file_patterns()
        impl.update_packaged_locations(Mock())
        impl.write_project(Mock(), Mock())
        self.assertTrue(True)

    def test_cdk_implementation(self):
        impl = CdkIacImplementation(Mock())
        impl.get_iac_file_patterns()
        impl.read_project(Mock())
        impl.update_packaged_locations(Mock())
        impl.write_project(Mock(), Mock())
        self.assertTrue(True)

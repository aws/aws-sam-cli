from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.local.mount.mounted_file_provider import MountedFileProvider


class TestMountedFileProvider(TestCase):
    @patch("samcli.local.mount.mounted_file_provider.copyfile")
    @patch("os.chmod")
    @patch("os.stat")
    @patch("samcli.local.mount.mounted_file_provider.Path")
    def test_initialization(self, path_mock, stat_mock, chmod_mock, copyfile_mock):
        rapid_path_mock = Mock()
        path_mock.return_value = rapid_path_mock

        rapid_basedir = "/tmp/rapid-test"
        go_bootstrap_basedir = "/tmp/go-test"
        mfp = MountedFileProvider(rapid_basedir, go_bootstrap_basedir)

        rapid_path_mock.mkdir.assert_called_with(mode=0o700, parents=True, exist_ok=True)
        copyfile_mock.assert_any_call(MountedFileProvider._RAPID_SOURCE, "{}/init".format(rapid_basedir))
        copyfile_mock.assert_called_with(
            MountedFileProvider._GO_BOOTSTRAP_SOURCE, "{}/aws-lambda-go".format(go_bootstrap_basedir)
        )

        self.assertEqual(mfp.rapid_basedir, rapid_basedir)
        self.assertEqual(mfp.go_bootstrap_basedir, go_bootstrap_basedir)

"""
Unit test for EffectiveUser class
"""
from unittest import TestCase
from unittest.mock import patch

from samcli.local.docker.effective_user import EffectiveUser, ROOT_USER_ID


class TestEffectiveUser(TestCase):
    @patch("samcli.local.docker.effective_user.os.name.lower")
    @patch("samcli.local.docker.effective_user.os")
    def test_return_effective_user_if_posix(self, mock_os, mock_os_name):
        mock_os_name.return_value = "posix"
        mock_os.getuid.return_value = 1000
        mock_os.getgroups.return_value = [1000, 2000, 3000]

        result = EffectiveUser.get_current_effective_user()

        mock_os.getuid.assert_called_once()
        mock_os.getgroups.assert_called_once()
        self.assertEqual("1000", result.user_id)
        self.assertEqual("1000", result.group_id)

    @patch("samcli.local.docker.effective_user.os.name.lower")
    @patch("samcli.local.docker.effective_user.os")
    def test_return_none_if_non_posix(self, mock_os, mock_os_name):
        mock_os_name.return_value = "nt"
        mock_os.getuid.return_value = 1000
        mock_os.getgroups.return_value = [1000, 2000, 3000]

        result = EffectiveUser.get_current_effective_user()

        mock_os.getuid.assert_not_called()
        mock_os.getgroups.assert_not_called()
        self.assertIsNone(result.user_id)
        self.assertIsNone(result.group_id)

    @patch("samcli.local.docker.effective_user.os.name.lower")
    @patch("samcli.local.docker.effective_user.os")
    def test_to_effective_user_str(self, mock_os, mock_os_name):
        mock_os_name.return_value = "posix"
        mock_os.getuid.return_value = 1000
        mock_os.getgroups.return_value = [1000, 2000, 3000]

        result = EffectiveUser.get_current_effective_user().to_effective_user_str()

        self.assertEqual("1000:1000", result)

    @patch("samcli.local.docker.effective_user.os.name.lower")
    @patch("samcli.local.docker.effective_user.os")
    def test_to_effective_user_str_if_root(self, mock_os, mock_os_name):
        mock_os_name.return_value = "posix"
        # 0 means current user is root
        mock_os.getuid.return_value = 0
        mock_os.getgroups.return_value = [1000, 2000, 3000]

        result = EffectiveUser.get_current_effective_user().to_effective_user_str()

        self.assertEqual(ROOT_USER_ID, result)

    @patch("samcli.local.docker.effective_user.os.name.lower")
    @patch("samcli.local.docker.effective_user.os")
    def test_to_effective_user_str_if_no_group_id(self, mock_os, mock_os_name):
        mock_os_name.return_value = "posix"
        mock_os.getuid.return_value = 1000
        mock_os.getgroups.return_value = []

        result = EffectiveUser.get_current_effective_user().to_effective_user_str()

        self.assertEqual("1000", result)

    @patch("samcli.local.docker.effective_user.os.name.lower")
    @patch("samcli.local.docker.effective_user.os")
    def test_to_effective_user_str_if_non_posix(self, mock_os, mock_os_name):
        mock_os_name.return_value = "nt"
        mock_os.getuid.return_value = 1000
        mock_os.getgroups.return_value = [1000, 2000, 3000]

        result = EffectiveUser.get_current_effective_user().to_effective_user_str()

        self.assertIsNone(result)

from unittest import TestCase
from unittest.mock import patch

from samcli.lib.utils.profile import list_available_profiles


class TestProfileUtils(TestCase):
    @patch("samcli.lib.utils.profile.Session")
    def test_list_available_profiles(self, session_mock):
        session_mock.return_value.available_profiles = ["p1", "p2"]
        self.assertEqual(["p1", "p2"], list_available_profiles())

from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.lib.utils.progressbar import progressbar


class TestProgressBar(TestCase):
    @patch("samcli.lib.utils.progressbar.click")
    def test_creating_progressbar(self, click_patch):
        progressbar_mock = Mock()
        click_patch.progressbar.return_value = progressbar_mock

        actual = progressbar(100, "this is a label")

        self.assertEqual(actual, progressbar_mock)

        click_patch.progressbar.assert_called_with(length=100, label="this is a label", show_pos=True)

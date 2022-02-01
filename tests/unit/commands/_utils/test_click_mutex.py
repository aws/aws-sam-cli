from unittest import TestCase
from unittest.mock import MagicMock, patch
from samcli.commands._utils.click_mutex import ClickMutex


class TestClickMutex(TestCase):
    class TestException(Exception):
        def __init__(self, message):
            self.message = message

    def setUp(self):

        self.click_option_patch = patch("samcli.commands._utils.click_mutex.click.Option.__init__")
        self.click_option_mock = self.click_option_patch.start()
        self.addCleanup(self.click_option_patch.stop)

        self.click_option_mock.return_value = None

        self.click_patch = patch("samcli.commands._utils.click_mutex.click")
        self.click_mock = self.click_patch.start()
        self.addCleanup(self.click_patch.stop)

        self.click_mock.UsageError = TestClickMutex.TestException

        self.super_patch = patch("samcli.commands._utils.click_mutex.super")
        self.super_mock = self.super_patch.start()
        self.addCleanup(self.super_patch.stop)

        self.context = MagicMock()

        self.mutex = ClickMutex(
            required_param_lists=[["r11", "r12"], ["r21", "r22", "r23"]],
            required_params_hint="required hint",
            incompatible_params=["i1", "i2"],
            incompatible_params_hint="incompatible hint",
        )
        self.mutex.name = "o1"

    def test_handle_parse_result_valid(self):
        options = {"o1": None, "o2": 1, "r11": None, "r12": 2}
        self.mutex.handle_parse_result(self.context, options, MagicMock())

    def test_handle_parse_result_incompatible(self):
        options = {"o1": None, "o2": None, "r11": 1, "r21": 2, "i1": 3}
        with self.assertRaises(Exception) as context:
            self.mutex.handle_parse_result(self.context, options, MagicMock())
        self.assertIn("i1", context.exception.message)

    def test_handle_parse_result_required(self):
        options = {"o1": None, "o2": None, "r11": 1, "r21": 2, "r22": None}
        with self.assertRaises(Exception) as context:
            self.mutex.handle_parse_result(self.context, options, MagicMock())
        self.assertIn("r11", context.exception.message)
        self.assertIn("r12", context.exception.message)
        self.assertIn("r21", context.exception.message)
        self.assertIn("r22", context.exception.message)
        self.assertIn("r23", context.exception.message)

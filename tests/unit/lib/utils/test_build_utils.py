from unittest import TestCase
from samcli.lib.build.utils import valid_architecture, warn_on_invalid_architecture
from samcli.lib.utils.architecture import X86_64, ARM64
from unittest.mock import patch, MagicMock, ANY


class TestBuildUtils(TestCase):
    def test_valid_architecture(self):
        self.assertTrue(valid_architecture(X86_64))
        self.assertTrue(valid_architecture(ARM64))
        self.assertFalse(valid_architecture("fake"))

    @patch("samcli.lib.build.utils.LOG")
    def test_warn_on_invalid_architecture(self, patched_logger):
        good_layer_definition = MagicMock()
        good_layer_definition.architecture = X86_64
        good_layer_definition.layer = MagicMock()
        good_layer_definition.layer.layer_id = "foo"

        warn_on_invalid_architecture(good_layer_definition)
        patched_logger.warning.assert_not_called()

        bad_layer_definition = MagicMock()
        bad_layer_definition.architecture = "fake"
        bad_layer_definition.layer = MagicMock()
        bad_layer_definition.layer.layer_id = "foo"

        warn_on_invalid_architecture(bad_layer_definition)
        patched_logger.warning.assert_called_with(
            "WARNING: `%s` in Layer `%s` is not a valid architecture.", "fake", "foo"
        )

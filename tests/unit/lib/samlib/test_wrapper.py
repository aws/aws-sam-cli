from unittest import TestCase
from unittest.mock import patch, Mock

from parameterized import parameterized

from samcli.lib.samlib.wrapper import SamTranslatorWrapper


class TestLanguageExtensionsPatching(TestCase):
    @parameterized.expand(
        [
            ({"Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"]}, True),
            ({"Transform": ["AWS::LanguageExtensions"]}, True),
            ({"Transform": ["AWS::LanguageExtensions-extension"]}, True),
            ({"Transform": "AWS::LanguageExtensions"}, True),
            ({"Transform": "AWS::LanguageExtensions-extension"}, True),
            ({"Transform": "AWS::Serverless-2016-10-31"}, False),
            ({}, False),
        ]
    )
    def test_check_using_langauge_extension(self, template, expected):
        self.assertEqual(SamTranslatorWrapper._check_using_language_extension(template), expected)

    @patch("samcli.lib.samlib.wrapper.SamResource")
    def test_patch_language_extensions(self, patched_sam_resource):
        wrapper = SamTranslatorWrapper({"Transform": "AWS::LanguageExtensions"})
        wrapper._patch_language_extensions()
        self.assertEqual(patched_sam_resource.valid.__name__, "patched_func")

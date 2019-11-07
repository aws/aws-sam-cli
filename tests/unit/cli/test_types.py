from unittest import TestCase
from unittest.mock import Mock, ANY
from nose_parameterized import parameterized

from samcli.cli.types import CfnParameterOverridesType, CfnTags, CfnCapabilitiesType
from samcli.cli.types import CfnMetadataType


class TestCfnParameterOverridesType(TestCase):
    def setUp(self):
        self.param_type = CfnParameterOverridesType()

    @parameterized.expand(
        [
            (("some string"),),
            # Key must not contain spaces
            (('ParameterKey="Ke y",ParameterValue=Value'),),
            # No value
            (("ParameterKey=Key,ParameterValue="),),
            # No key
            (("ParameterKey=,ParameterValue=Value"),),
            # Case sensitive
            (("parameterkey=Key,ParameterValue=Value"),),
            # No space after comma
            (("ParameterKey=Key, ParameterValue=Value"),),
            # Bad separator
            (("ParameterKey:Key,ParameterValue:Value"),),
        ]
    )
    def test_must_fail_on_invalid_format(self, input):
        self.param_type.fail = Mock()
        self.param_type.convert(input, "param", "ctx")

        self.param_type.fail.assert_called_with(ANY, "param", "ctx")

    @parameterized.expand(
        [
            (
                ("ParameterKey=KeyPairName,ParameterValue=MyKey ParameterKey=InstanceType,ParameterValue=t1.micro",),
                {"KeyPairName": "MyKey", "InstanceType": "t1.micro"},
            ),
            (('ParameterKey="Key",ParameterValue=Val\\ ue',), {"Key": "Val ue"}),
            (('ParameterKey="Key",ParameterValue="Val\\"ue"',), {"Key": 'Val"ue'}),
            (("ParameterKey=Key,ParameterValue=Value",), {"Key": "Value"}),
            (('ParameterKey=Key,ParameterValue=""',), {"Key": ""}),
            (
                # Trailing and leading whitespaces
                ("  ParameterKey=Key,ParameterValue=Value   ParameterKey=Key2,ParameterValue=Value2     ",),
                {"Key": "Value", "Key2": "Value2"},
            ),
            (
                # Quotes at the end
                ('ParameterKey=Key,ParameterValue=Value\\"',),
                {"Key": 'Value"'},
            ),
            (
                # Quotes at the start
                ('ParameterKey=Key,ParameterValue=\\"Value',),
                {"Key": '"Value'},
            ),
            (
                # Value is spacial characters
                ("ParameterKey=Key,ParameterValue==-_)(*&^%$#@!`~:;,.    ParameterKey=Key2,ParameterValue=Value2",),
                {"Key": "=-_)(*&^%$#@!`~:;,.", "Key2": "Value2"},
            ),
            (('ParameterKey=Key1230,ParameterValue="{\\"a\\":\\"b\\"}"',), {"Key1230": '{"a":"b"}'}),
            (
                # Must ignore empty inputs
                ("",),
                {},
            ),
        ]
    )
    def test_successful_parsing(self, input, expected):
        result = self.param_type.convert(input, None, None)
        self.assertEqual(result, expected, msg="Failed with Input = " + str(input))


class TestCfnMetadataType(TestCase):
    def setUp(self):
        self.param_type = CfnMetadataType()

    @parameterized.expand(
        [
            # Just a string
            ("some string"),
            # Unfinished dict with just a key
            ("{'a'}"),
            # Unfinished dict just a key and :
            ("{'a'}:"),
            # Dict with nested dict:
            ("{'a':{'b':'c'}}"),
            # Dict with list value:
            ("{'a':['b':'c']}"),
            # Just a list:
            ("['b':'c']"),
            # Non-string
            ("{1:1}"),
            # Wrong notation
            ("a==b"),
            # Wrong multi-key notation
            ("a==b,c==d"),
        ]
    )
    def test_must_fail_on_invalid_format(self, input):
        self.param_type.fail = Mock()
        self.param_type.convert(input, "param", "ctx")

        self.param_type.fail.assert_called_with(ANY, "param", "ctx")

    @parameterized.expand(
        [
            ("a=b", {"a": "b"}),
            ("a=b,c=d", {"a": "b", "c": "d"}),
            ('{"a":"b"}', {"a": "b"}),
            ('{"a":"b", "c":"d"}', {"a": "b", "c": "d"}),
            ("", {}),
        ]
    )
    def test_successful_parsing(self, input, expected):
        result = self.param_type.convert(input, None, None)
        self.assertEqual(result, expected, msg="Failed with Input = " + input)


class TestCfnTags(TestCase):
    def setUp(self):
        self.param_type = CfnTags()

    @parameterized.expand(
        [
            # Just a string
            ("some string"),
            # Wrong notation
            ("a==b"),
            # Wrong multi-key notation
            ("a==b,c==d"),
        ]
    )
    def test_must_fail_on_invalid_format(self, input):
        self.param_type.fail = Mock()
        self.param_type.convert(input, "param", "ctx")

        self.param_type.fail.assert_called_with(ANY, "param", "ctx")

    @parameterized.expand([(("a=b",), {"a": "b"}), (("a=b", "c=d"), {"a": "b", "c": "d"}), (("",), {})])
    def test_successful_parsing(self, input, expected):
        result = self.param_type.convert(input, None, None)
        self.assertEqual(result, expected, msg="Failed with Input = " + str(input))


class TestCfnCapabilitiesType(TestCase):
    def setUp(self):
        self.param_type = CfnCapabilitiesType()

    @parameterized.expand(
        [
            # Just a string
            ("some string"),
            # tuple of string
            ("some string",),
            # non-tuple valid string
            "CAPABILITY_NAMED_IAM",
        ]
    )
    def test_must_fail_on_invalid_format(self, input):
        self.param_type.fail = Mock()
        self.param_type.convert(input, "param", "ctx")

        self.param_type.fail.assert_called_with(ANY, "param", "ctx")

    @parameterized.expand(
        [
            (("CAPABILITY_AUTO_EXPAND",), ("CAPABILITY_AUTO_EXPAND",)),
            (("CAPABILITY_AUTO_EXPAND", "CAPABILITY_NAMED_IAM"), ("CAPABILITY_AUTO_EXPAND", "CAPABILITY_NAMED_IAM")),
            (
                ("CAPABILITY_AUTO_EXPAND", "CAPABILITY_NAMED_IAM", "CAPABILITY_IAM"),
                ("CAPABILITY_AUTO_EXPAND", "CAPABILITY_NAMED_IAM", "CAPABILITY_IAM"),
            ),
        ]
    )
    def test_successful_parsing(self, input, expected):
        result = self.param_type.convert(input, None, None)
        self.assertEqual(result, expected, msg="Failed with Input = " + str(input))

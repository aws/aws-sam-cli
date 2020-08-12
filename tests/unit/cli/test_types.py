from unittest import TestCase
from unittest.mock import Mock, ANY
from parameterized import parameterized

from samcli.cli.types import CfnParameterOverridesType, CfnTags
from samcli.cli.types import CfnMetadataType


class TestCfnParameterOverridesType(TestCase):
    def setUp(self):
        self.param_type = CfnParameterOverridesType()

    @parameterized.expand(
        [
            # Random string
            ("some string",),
            # Only commas
            (",,",),
            # Bad separator
            ("ParameterKey:Key,ParameterValue:Value",),
        ]
    )
    def test_must_fail_on_invalid_format(self, input):
        self.param_type.fail = Mock()
        self.param_type.convert(input, "param", "ctx")

        self.param_type.fail.assert_called_with(ANY, "param", "ctx")

    @parameterized.expand(
        [
            # No enclosing quotes and non escaped quotes in values.
            (
                (
                    "DeployStackName=new-stack "
                    'DeployParameterOverrides="{"bucketName":"production","bucketRegion":"eu-west-1"}" '
                    'DeployParameterBucketOverrides="{"bucketName":"myownbucket"}"'
                ),
                {
                    "DeployStackName": "new-stack",
                    "DeployParameterOverrides": "{",
                    "DeployParameterBucketOverrides": "{",
                },
            )
        ]
    )
    def test_unsupported_formats(self, input, expected):
        result = self.param_type.convert(input, None, None)
        self.assertEqual(result, expected, msg="Failed with Input = " + str(input))

    @parameterized.expand(
        [
            (
                ("ParameterKey=KeyPairName,ParameterValue=MyKey ParameterKey=InstanceType,ParameterValue=t1.micro",),
                {"KeyPairName": "MyKey", "InstanceType": "t1.micro"},
            ),
            (("KeyPairName=MyKey InstanceType=t1.micro",), {"KeyPairName": "MyKey", "InstanceType": "t1.micro"}),
            (("KeyPairName=MyKey, InstanceType=t1.micro,",), {"KeyPairName": "MyKey,", "InstanceType": "t1.micro,"}),
            (('ParameterKey="Ke y",ParameterValue=Value',), {"ParameterKey": "Ke y"}),
            (("ParameterKey='Ke y',ParameterValue=Value",), {"ParameterKey": "Ke y"}),
            ((("ParameterKey=Key,ParameterValue="),), {"ParameterKey": "Key,ParameterValue="}),
            (('ParameterKey="Key",ParameterValue=Val\\ ue',), {"Key": "Val ue"}),
            (('ParameterKey="Key",ParameterValue="Val\\"ue"',), {"Key": 'Val"ue'}),
            (("ParameterKey='Key',ParameterValue='Val ue'",), {"Key": "Val ue"}),
            (('ParameterKey="Key",ParameterValue=Val\'ue',), {"Key": "Val'ue"}),
            (("ParameterKey='Key',ParameterValue='Val\"ue'",), {"Key": 'Val"ue'}),
            (("""ParameterKey='Key',ParameterValue='Val"ue'""",), {"Key": 'Val"ue'}),
            (("ParameterKey=Key,ParameterValue=Value",), {"Key": "Value"}),
            (('ParameterKey=Key,ParameterValue=""',), {"Key": ""}),
            (
                # Trailing and leading whitespaces
                ("  ParameterKey=Key,ParameterValue=Value   ParameterKey=Key2,ParameterValue=Value2     ",),
                {"Key": "Value", "Key2": "Value2"},
            ),
            (
                # Double quotes at the end
                ('ParameterKey=Key,ParameterValue=Value\\"',),
                {"Key": 'Value"'},
            ),
            (
                # Single quotes at the end
                ("ParameterKey=Key,ParameterValue=Value'",),
                {"Key": "Value'"},
            ),
            (
                # Double quotes at the start
                ('ParameterKey=Key,ParameterValue=\\"Value',),
                {"Key": '"Value'},
            ),
            (
                # Single quotes at the start
                ("ParameterKey=Key,ParameterValue='Value",),
                {"Key": "'Value"},
            ),
            (
                # Value is spacial characters
                ("ParameterKey=Key,ParameterValue==-_)(*&^%$#@!`~:;,.    ParameterKey=Key2,ParameterValue=Value2",),
                {"Key": "=-_)(*&^%$#@!`~:;,.", "Key2": "Value2"},
            ),
            (('ParameterKey=Key1230,ParameterValue="{\\"a\\":\\"b\\"}"',), {"Key1230": '{"a":"b"}'}),
            (('Key=Key1230 Value="{\\"a\\":\\"b\\"}"',), {"Key": "Key1230", "Value": '{"a":"b"}'}),
            (("""Key=Key1230 Value='{"a":"b"}'""",), {"Key": "Key1230", "Value": '{"a":"b"}'}),
            (
                (
                    'Key=Key1230 Value="{\\"a\\":\\"b\\"}" '
                    'Key1=Key1230 Value1="{\\"a\\":\\"b\\"}" '
                    'Key2=Key1230 Value2="{\\"a\\":\\"b\\"}"',
                ),
                {
                    "Key": "Key1230",
                    "Value": '{"a":"b"}',
                    "Key1": "Key1230",
                    "Value1": '{"a":"b"}',
                    "Key2": "Key1230",
                    "Value2": '{"a":"b"}',
                },
            ),
            (
                (
                    "DeployStackName=new-stack "
                    'DeployParameterOverrides="{\\"bucketName\\":\\"production\\",\\"bucketRegion\\":\\"eu-west-1\\"}" '
                    'DeployParameterBucketOverrides="{\\"bucketName\\":\\"myownbucket\\"}"'
                ),
                {
                    "DeployStackName": "new-stack",
                    "DeployParameterOverrides": '{"bucketName":"production","bucketRegion":"eu-west-1"}',
                    "DeployParameterBucketOverrides": '{"bucketName":"myownbucket"}',
                },
            ),
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
            # ("a==b"),
            # Wrong multi-key notation
            # ("a==b,c==d"),
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
            # ("a==b"),
            # Wrong multi-key notation
            # ("a==b,c==d"),
        ]
    )
    def test_must_fail_on_invalid_format(self, input):
        self.param_type.fail = Mock()
        self.param_type.convert(input, "param", "ctx")

        self.param_type.fail.assert_called_with(ANY, "param", "ctx")

    @parameterized.expand(
        [
            (("a=b",), {"a": "b"}),
            (("a=b", "c=d"), {"a": "b", "c": "d"}),
            (('"a+-=._:/@"="b+-=._:/@" "--c="="=d/"',), {"a+-=._:/@": "b+-=._:/@", "--c=": "=d/"}),
            (('owner:name="son of anton"',), {"owner:name": "son of anton"}),
            (("a=012345678901234567890123456789",), {"a": "012345678901234567890123456789"}),
            (
                ("a=012345678901234567890123456789 name=this-is-a-very-long-tag-value-now-it-should-not-fail"),
                {"a": "012345678901234567890123456789", "name": "this-is-a-very-long-tag-value-now-it-should-not-fail"},
            ),
            (
                ("a=012345678901234567890123456789", "c=012345678901234567890123456789"),
                {"a": "012345678901234567890123456789", "c": "012345678901234567890123456789"},
            ),
            (("",), {}),
        ]
    )
    def test_successful_parsing(self, input, expected):
        result = self.param_type.convert(input, None, None)
        self.assertEqual(result, expected, msg="Failed with Input = " + str(input))

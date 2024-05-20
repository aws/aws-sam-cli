from unittest import TestCase
from unittest.mock import MagicMock, Mock, ANY, patch

from click import BadParameter
from parameterized import parameterized

from samcli.cli.types import (
    CfnParameterOverridesType,
    CfnTags,
    SigningProfilesOptionType,
    ImageRepositoryType,
    ImageRepositoriesType,
    RemoteInvokeBotoApiParameterType,
    RemoteInvokeOutputFormatType,
    SyncWatchExcludeType,
)
from samcli.cli.types import CfnMetadataType
from samcli.lib.remote_invoke.remote_invoke_executors import RemoteInvokeOutputFormat


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
            # list as input
            ([], {}),
            (
                ["stage=int", "company:application=awesome-service", "company:department=engineering"],
                {"stage": "int", "company:application": "awesome-service", "company:department": "engineering"},
            ),
        ]
    )
    def test_successful_parsing(self, input, expected):
        result = self.param_type.convert(input, None, None)
        self.assertEqual(result, expected, msg="Failed with Input = " + str(input))

    @parameterized.expand(
        [
            (
                ["stage=int", "company:application=awesome-service", "company:department=engineering"],
                {"stage": "int", "company:application": "awesome-service", "company:department": "engineering"},
            ),
            (
                ['owner:name="son of anton"', "company:application=awesome-service", "company:department=engineering"],
                {
                    "owner:name": "son of anton",
                    "company:application": "awesome-service",
                    "company:department": "engineering",
                },
            ),
        ]
    )
    @patch("re.findall")
    def test_no_regex_parsing_if_input_is_list(self, input, expected, regex_mock):
        result = self.param_type.convert(input, None, None)
        self.assertEqual(result, expected, msg="Failed with Input = " + str(input))
        regex_mock.assert_not_called()


class TestCfnTagsMultipleValues(TestCase):
    """
    Tests for the CfnTags parameter allowing multiple values per key.
    """

    def setUp(self):
        self.param_type = CfnTags(multiple_values_per_key=True)

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
            (("a=b",), {"a": ["b"]}),
            (("a=b", "c=d"), {"a": ["b"], "c": ["d"]}),
            (('"a+-=._:/@"="b+-=._:/@" "--c="="=d/"',), {"a+-=._:/@": ["b+-=._:/@"], "--c=": ["=d/"]}),
            (('owner:name="son of anton"',), {"owner:name": ["son of anton"]}),
            (("a=012345678901234567890123456789",), {"a": ["012345678901234567890123456789"]}),
            (
                ("a=012345678901234567890123456789 name=this-is-a-very-long-tag-value-now-it-should-not-fail"),
                {
                    "a": ["012345678901234567890123456789"],
                    "name": ["this-is-a-very-long-tag-value-now-it-should-not-fail"],
                },
            ),
            (
                ("a=012345678901234567890123456789", "c=012345678901234567890123456789"),
                {"a": ["012345678901234567890123456789"], "c": ["012345678901234567890123456789"]},
            ),
            (("",), {}),
            # list as input
            ([], {}),
            (
                ["stage=int", "company:application=awesome-service", "company:department=engineering"],
                {"stage": ["int"], "company:application": ["awesome-service"], "company:department": ["engineering"]},
            ),
            (("a=b", "a=d"), {"a": ["b", "d"]}),
            (("stage=alpha", "stage=beta", "stage=gamma", "stage=prod"), {"stage": ["alpha", "beta", "gamma", "prod"]}),
        ]
    )
    def test_successful_parsing(self, input, expected):
        result = self.param_type.convert(input, None, None)
        self.assertEqual(result, expected, msg="Failed with Input = " + str(input))


class TestCodeSignOptionType(TestCase):
    def setUp(self):
        self.param_type = SigningProfilesOptionType()

    @parameterized.expand(
        [
            # Just a string
            ("some string"),
            # Wrong notation
            ("a=b::"),
            ("ab::"),
            ("a=b::c"),
            ("=b"),
            ("=b:c"),
            ("a=:c"),
        ]
    )
    def test_must_fail_on_invalid_format(self, input):
        self.param_type.fail = Mock()
        self.param_type.convert(input, "param", "ctx")

        self.param_type.fail.assert_called_with(ANY, "param", "ctx")

    @parameterized.expand(
        [
            (("a=b",), {"a": {"profile_name": "b", "profile_owner": ""}}),
            (
                ("a=b", "c=d"),
                {"a": {"profile_name": "b", "profile_owner": ""}, "c": {"profile_name": "d", "profile_owner": ""}},
            ),
            (("a=b:",), {"a": {"profile_name": "b", "profile_owner": ""}}),
            (("a=b:c",), {"a": {"profile_name": "b", "profile_owner": "c"}}),
            (
                ("a=b:c", "d=e:f"),
                {"a": {"profile_name": "b", "profile_owner": "c"}, "d": {"profile_name": "e", "profile_owner": "f"}},
            ),
            (
                ("a=b:c", "d=e"),
                {"a": {"profile_name": "b", "profile_owner": "c"}, "d": {"profile_name": "e", "profile_owner": ""}},
            ),
            (
                ("a=b:", "d=e"),
                {"a": {"profile_name": "b", "profile_owner": ""}, "d": {"profile_name": "e", "profile_owner": ""}},
            ),
            (
                "a=b:c d=e",
                {"a": {"profile_name": "b", "profile_owner": "c"}, "d": {"profile_name": "e", "profile_owner": ""}},
            ),
            (
                'a="b:c" d="e"',
                {"a": {"profile_name": "b", "profile_owner": "c"}, "d": {"profile_name": "e", "profile_owner": ""}},
            ),
            (("",), {}),
        ]
    )
    def test_successful_parsing(self, input, expected):
        result = self.param_type.convert(input, None, None)
        self.assertEqual(result, expected, msg="Failed with Input = " + str(input))


class TestImageRepositoryType(TestCase):
    def setUp(self):
        self.param_type = ImageRepositoryType()
        self.mock_param = Mock(opts=["--image-repository"])

    @parameterized.expand(
        [
            # Just a string
            ("some string"),
            # Almost an URI, but no dkr
            ("123456789012.us-east-1.amazonaws.com/test1"),
            # Almost an URI, but no repo-name
            ("123456789012.us-east-1.amazonaws.com/"),
            # Almost an URI, but no region name
            ("123456789012.dkr.ecr.amazonaws.com/test1"),
            # Almost an URI, but no service name
            ("123456789012.dkr.amazonaws.com/test1"),
        ]
    )
    def test_must_fail_on_invalid_format(self, input):
        self.param_type.fail = Mock()
        with self.assertRaises(BadParameter):
            self.param_type.convert(input, self.mock_param, Mock())

    @parameterized.expand(
        [
            (
                "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
                "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            ),
            (
                "123456789012.dkr.ecr.cn-north-1.amazonaws.com.cn/test1",
                "123456789012.dkr.ecr.cn-north-1.amazonaws.com.cn/test1",
            ),
        ]
    )
    def test_successful_parsing(self, input, expected):
        result = self.param_type.convert(input, self.mock_param, Mock())
        self.assertEqual(result, expected, msg="Failed with Input = " + str(input))


class TestImageRepositoriesType(TestCase):
    def setUp(self):
        self.param_type = ImageRepositoriesType()
        self.mock_param = Mock(opts=["--image-repositories"])

    @parameterized.expand(
        [
            # Just a string
            ("some string"),
            # Too many equals
            ("a=b=c=d"),
            # Almost an URI, but no dkr
            ("Hello=123456789012.us-east-1.amazonaws.com/test1"),
            # Almost an URI, but no repo-name
            ("Hello=123456789012.us-east-1.amazonaws.com/"),
            # Almost an URI, but no region name
            ("Hello=123456789012.dkr.ecr.amazonaws.com/test1"),
            # Almost an URI, but no service name
            ("Hello=123456789012.dkr.amazonaws.com/test1"),
        ]
    )
    def test_must_fail_on_invalid_format(self, input):
        self.param_type.fail = Mock()
        with self.assertRaises(BadParameter):
            self.param_type.convert(input, self.mock_param, Mock())

    @parameterized.expand(
        [
            (
                "HelloWorld=123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
                {"HelloWorld": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
            ),
            (
                "HelloWorld=123456789012.dkr.ecr.cn-north-1.amazonaws.com.cn/test1",
                {"HelloWorld": "123456789012.dkr.ecr.cn-north-1.amazonaws.com.cn/test1"},
            ),
        ]
    )
    def test_successful_parsing(self, input, expected):
        result = self.param_type.convert(input, self.mock_param, Mock())
        self.assertEqual(result, expected, msg="Failed with Input = " + str(input))


class TestRemoteInvokeBotoApiParameterType(TestCase):
    def setUp(self):
        self.param_type = RemoteInvokeBotoApiParameterType()
        self.mock_param = Mock(opts=["--parameter"])

    @parameterized.expand(
        [
            # Just a string
            ("some string"),
            # no parameter value
            ("no-value"),
        ]
    )
    def test_must_fail_on_invalid_format(self, input):
        self.param_type.fail = Mock()
        with self.assertRaises(BadParameter):
            self.param_type.convert(input, self.mock_param, Mock())

    @parameterized.expand(
        [
            (
                "Parameter1=Value1",
                {"Parameter1": "Value1"},
            ),
            (
                'Parameter1=\'{"a":54, "b": 28}\'',
                {"Parameter1": '\'{"a":54, "b": 28}\''},
            ),
            (
                "Parameter1=base-64-encoded==",
                {"Parameter1": "base-64-encoded=="},
            ),
        ]
    )
    def test_successful_parsing(self, input, expected):
        result = self.param_type.convert(input, self.mock_param, Mock())
        self.assertEqual(result, expected)


class TestRemoteInvokeOutputFormatParameterType(TestCase):
    def setUp(self):
        self.param_type = RemoteInvokeOutputFormatType(enum=RemoteInvokeOutputFormat)
        self.mock_param = Mock(opts=["--output-format"])

    @parameterized.expand(
        [
            ("string"),
            ("some string"),
            ("non-default"),
        ]
    )
    def test_must_fail_on_invalid_values(self, input):
        with self.assertRaises(BadParameter):
            self.param_type.convert(input, self.mock_param, None)

    @parameterized.expand(
        [
            (
                "text",
                RemoteInvokeOutputFormat.TEXT,
            ),
            (
                "json",
                RemoteInvokeOutputFormat.JSON,
            ),
        ]
    )
    def test_successful_parsing(self, input, expected):
        result = self.param_type.convert(input, self.mock_param, None)
        self.assertEqual(result, expected)


class TestSyncWatchExcludeType(TestCase):
    def setUp(self):
        self.exclude_type = SyncWatchExcludeType()

    @parameterized.expand(
        [
            ("HelloWorldFunction=file.txt", {"HelloWorldFunction": ["file.txt"]}),
            ({"HelloWorldFunction": ["file.txt"]}, {"HelloWorldFunction": ["file.txt"]}),
        ]
    )
    def test_convert_parses_input(self, input, expected):
        result = self.exclude_type.convert(input, MagicMock(), MagicMock())

        self.assertEqual(result, expected)

    @parameterized.expand(
        [
            ("not a key value pair",),
            ("",),
            ("key=",),
            ("=value",),
            ("key=value=foo=bar",),
        ]
    )
    def test_convert_fails_parse_input(self, input):
        with self.assertRaises(BadParameter):
            self.exclude_type.convert(input, MagicMock(), MagicMock())

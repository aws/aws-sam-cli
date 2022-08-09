from unittest import TestCase

from parameterized import parameterized

from samcli.commands.exceptions import FailedArnParseException
from samcli.lib.test_runner.generate_env_vars import FargateRunnerArnMapGenerator
from samcli.yamlhelper import yaml_parse


class Test_GenEnvVars(TestCase):
    def setUp(self):
        self.arn_map_generator = FargateRunnerArnMapGenerator()

    lambda_arn = "arn:aws:lambda:us-east-1:123456789123:function:lambda-sample-SampleLambda-KWsMLA204T0i"
    queue_arn = "arn:aws:sqs:us-east-2:444455556666:queue1"
    bucket_arn = "arn:aws:s3:::my-very-big-s3-bucket"
    ddb_arn = "arn:aws:dynamodb:us-east-1:123456789012:table/Books"
    sm_arn = "arn:aws:states:us-east-1:123456789012:stateMachine:stateMachineName"
    lg_arn = "arn:aws:logs:us-west-1:123456789012:log-group:/mystack-testgroup-12ABC1AB12A1:*"
    rest_api_arn = "arn:aws-us-gov:apigateway:us-west-1::/restapis/r3st4p1"
    api_arn = "arn:aws-us-gov:apigateway:us-west-1::/apis/4p1000"

    @parameterized.expand(
        [
            [lambda_arn, "_LAMBDA_SAMPLE_SAMPLELAMBDA_KWSMLA204T0I"],
            [queue_arn, "_QUEUE1"],
            [bucket_arn, "_MY_VERY_BIG_S3_BUCKET"],
            [ddb_arn, "_BOOKS"],
            [sm_arn, "_STATEMACHINENAME"],
            [lg_arn, "_MYSTACK_TESTGROUP_12ABC1AB12A1"],
            [rest_api_arn, "_R3ST4P1"],
            [api_arn, "_4P1000"],
        ]
    )
    def test_get_env_var_name(self, arn, expected_name):
        expected_object = {expected_name: arn}
        output_yaml = self.arn_map_generator.generate_env_vars_yaml_string([arn])
        self.assertEqual(yaml_parse(output_yaml), expected_object)

    def test_bad_arn(self):
        bad_arn = "arn:aws:resource:bad"
        with self.assertRaises(FailedArnParseException):
            self.arn_map_generator.generate_env_vars_yaml_string([bad_arn])

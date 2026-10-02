import pytest
from parameterized import parameterized

from tests.regression.package.regression_package_base import PackageRegressionBase

# These tests require AWS credentials; they are gated by the requires_credential marker.


# Only tested cases where the output template file changes, adding metadata or kms keys does not change the output.


@pytest.mark.requires_credential
class TestPackageRegression(PackageRegressionBase):
    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    @parameterized.expand(
        [
            ("aws-serverless-api.yaml", True),
            ("aws-appsync-graphqlschema.yaml", True),
            ("aws-appsync-resolver.yaml", True),
            ("aws-appsync-functionconfiguration.yaml", True),
            ("aws-apigateway-restapi.yaml", True),
            ("aws-elasticbeanstalk-applicationversion.yaml", True),
            ("aws-cloudformation-stack-regression.yaml", False),
            ("aws-cloudformation-stack-regression.yaml", False),
        ]
    )
    def test_package_with_output_template_file(self, template_file, skip_sam_metadata=False):
        arguments = {"s3_bucket": self.s3_bucket.name, "template_file": self.test_data_path.joinpath(template_file)}

        self.regression_check(arguments, skip_sam_metadata)

    @parameterized.expand(
        [
            ("aws-serverless-api.yaml", True),
            ("aws-appsync-graphqlschema.yaml", True),
            ("aws-appsync-resolver.yaml", True),
            ("aws-appsync-functionconfiguration.yaml", True),
            ("aws-apigateway-restapi.yaml", True),
            ("aws-elasticbeanstalk-applicationversion.yaml", True),
            ("aws-cloudformation-stack-regression.yaml", False),
            ("aws-cloudformation-stack-regression.yaml", False),
        ]
    )
    def test_package_with_output_template_file_and_prefix(self, template_file, skip_sam_metadata=False):
        arguments = {
            "s3_bucket": self.s3_bucket.name,
            "template_file": self.test_data_path.joinpath(template_file),
            "s3_prefix": "regression/tests",
        }

        self.regression_check(arguments, skip_sam_metadata)

    @parameterized.expand(
        [
            ("aws-serverless-api.yaml", True),
            ("aws-appsync-graphqlschema.yaml", True),
            ("aws-appsync-resolver.yaml", True),
            ("aws-appsync-functionconfiguration.yaml", True),
            ("aws-apigateway-restapi.yaml", True),
            ("aws-elasticbeanstalk-applicationversion.yaml", True),
            ("aws-cloudformation-stack-regression.yaml", False),
            ("aws-cloudformation-stack-regression.yaml", False),
        ]
    )
    def test_package_with_output_template_file_json_and_prefix(self, template_file, skip_sam_metadata=False):
        arguments = {
            "s3_bucket": self.s3_bucket.name,
            "template_file": self.test_data_path.joinpath(template_file),
            "s3_prefix": "regression/tests",
            "use_json": True,
        }

        self.regression_check(arguments, skip_sam_metadata)

import os

from parameterized.parameterized import parameterized
from tests.integration.check.check_integ_base import CheckIntegBase

from tests.testing_utils import run_command_with_input

CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")


class TestCheck(CheckIntegBase):
    @classmethod
    def setUpClass(cls):
        CheckIntegBase.setUpClass()

    def setUp(self):
        super().setUp()

    @parameterized.expand(
        [
            "single_lambda_function.yaml",
        ]
    )
    def test_single_lambda_function(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        check_command_list = self.get_minimal_check_command_list(template_path)

        check_process_execute = run_command_with_input(
            check_command_list, "{}\n1\n954\n789\n2500000\n789\n5.432:GB\nn\n".format(stack_name).encode()
        )

        stdout = check_process_execute.stdout.strip()
        self.assertIn(bytes("* AWS Lambda: $172.81/month", encoding="utf-8"), stdout)
        self.assertIn(bytes("789ms duration", encoding="utf-8"), stdout)
        self.assertIn(bytes("954TPS arrival rate", encoding="utf-8"), stdout)
        self.assertIn(bytes("75%", encoding="utf-8"), stdout)

        self.assertEqual(check_process_execute.process.returncode, 0)

    @parameterized.expand(
        [
            "lambda_and_api_gateway.yaml",
        ]
    )
    def test_lambda_and_api_gateways(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        check_command_list = self.get_minimal_check_command_list(template_path)

        check_process_execute = run_command_with_input(
            check_command_list, "{}\n1\n1900\n1234\n300000\n1234\n815:MB\nn\n".format(stack_name).encode()
        )

        stdout = check_process_execute.stdout.strip()
        self.assertIn(bytes("* AWS Lambda: $0.00/month", encoding="utf-8"), stdout)
        self.assertIn(bytes("1234ms duration", encoding="utf-8"), stdout)
        self.assertIn(bytes("1900TPS arrival rate", encoding="utf-8"), stdout)
        self.assertIn(bytes("234% of the allowed concurrency", encoding="utf-8"), stdout)
        self.assertIn(bytes(" 78% of the available burst concurrency.", encoding="utf-8"), stdout)

        self.assertEqual(check_process_execute.process.returncode, 0)

    @parameterized.expand(
        [
            "lambda_and_dynamo.yaml",
        ]
    )
    def test_lambda_and_dynamo(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        check_command_list = self.get_minimal_check_command_list(template_path)

        check_process_execute = run_command_with_input(
            check_command_list, "{}\n1\n300\n700\n8000000\n700\n8:GB\nn\n".format(stack_name).encode()
        )

        stdout = check_process_execute.stdout.strip()
        self.assertIn(bytes("* AWS Lambda: $744.20/month", encoding="utf-8"), stdout)
        self.assertIn(
            bytes(
                "For the lambda function [HelloWorldFunction2], following the path [DynamoDBTable1], "
                "you will not be close to its soft limit of 1000 concurrent executions.",
                encoding="utf-8",
            ),
            stdout,
        )

        self.assertEqual(check_process_execute.process.returncode, 0)

    @parameterized.expand(
        [
            "external_dynamo_table.yaml",
        ]
    )
    def test_external_dynamo_table(self, template_file):
        """
        In this tests a dynamo table is referenced in the table, but not defined in it.
        An actual dynamoDB table does not need to be generated for this test.
        """
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        check_command_list = self.get_minimal_check_command_list(template_path)

        check_process_execute = run_command_with_input(
            check_command_list, "{}\n1\n1\n1111\n1111\n1\n1\n1:GB\n2222\n2222\nn\n".format(stack_name).encode()
        )

        self.assertEqual(check_process_execute.process.returncode, 0)

    @parameterized.expand(
        [
            "complex_template.yaml",
        ]
    )
    def test_complex_template(self, template_file):
        """
        This template will generate a graph where nodes ahve multiple parents and children of different
        resource (event source) types
        """
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        check_command_list = self.get_minimal_check_command_list(template_path)

        check_process_execute = run_command_with_input(
            check_command_list,
            "{}\n1:2\n1\n1200\n750\n4000000\n1400\n888:MB\n1200\n900\n900\n800\n100"
            "1\n1\n800\n963\n800\n456\n753\n888\n1101\n1\n1400\n702\nn\n".format(stack_name).encode(),
        )

        stdout = check_process_execute.stdout.strip()
        self.assertIn(bytes("* AWS Lambda: $76.07/month", encoding="utf-8"), stdout)
        self.assertIn(
            bytes(
                "[HelloWorldFunction2], following the path [ApiGatewayApi2 --> HelloWorldFunction1 --> DynamoDBTable1"
                "], you will not be close to its soft limit of 1000 concurrent executions.",
                encoding="utf-8",
            ),
            stdout,
        )
        self.assertIn(
            bytes(
                "[HelloWorldFunction3], following the path [ApiGatewayApi2 --> HelloWorldFunction1 --> DynamoDBTable2"
                "], you will not be close to its soft limit of 1000 concurrent executions.",
                encoding="utf-8",
            ),
            stdout,
        )
        self.assertIn(
            bytes(
                "[HelloWorldFunction3], following the path [ApiGatewayApi1 --> HelloWorldFunction1 --> DynamoDBTable2"
                "], the 800ms duration and 900TPS arrival rate is using 72%",
                encoding="utf-8",
            ),
            stdout,
        )
        self.assertIn(
            bytes(
                "[HelloWorldFunction1], following the path [ApiGatewayApi2], the 963ms duration and 800TPS arrival"
                " rate is using 77%",
                encoding="utf-8",
            ),
            stdout,
        )
        self.assertIn(
            bytes(
                "[HelloWorldFunction4], following the path [ApiGatewayApi2 --> HelloWorldFunction1 --> "
                "DynamoDBTable2], the 1101ms duration and 753TPS arrival rate is using 83%",
                encoding="utf-8",
            ),
            stdout,
        )
        self.assertIn(
            bytes(
                "[HelloWorldFunction1], following the path [ApiGatewayApi1], the 750ms duration and 1200TPS "
                "arrival rate is using 90%",
                encoding="utf-8",
            ),
            stdout,
        )
        self.assertIn(
            bytes(
                "[HelloWorldFunction4], following the path [ApiGatewayApi1 --> HelloWorldFunction1 --> "
                "DynamoDBTable2], the 1001ms duration and 900TPS arrival rate is using 90%",
                encoding="utf-8",
            ),
            stdout,
        )
        self.assertIn(
            bytes(
                "[HelloWorldFunction2], following the path [ApiGatewayApi3], the 702ms duration and 1400TPS "
                "arrival rate is using 98%",
                encoding="utf-8",
            ),
            stdout,
        )
        self.assertIn(
            bytes(
                "[HelloWorldFunction2], following the path [ApiGatewayApi1 --> HelloWorldFunction1 --> "
                "DynamoDBTable1], the 900ms duration and 1200TPS arrival rate is using 108% of the allowed "
                "concurrency on AWS Lambda. It exceeds the limits of the lambda function. It will use 36%",
                encoding="utf-8",
            ),
            stdout,
        )

        self.assertEqual(check_process_execute.process.returncode, 0)

    @parameterized.expand(
        [
            "bad_user_input.yaml",
        ]
    )
    def test_bad_input(self, template_file):
        """
        This will test sam check at various points to ensure that it never accepts
        bad input from the cli and that the correct message is displayed.
        At the end it will choose an incorrect option when asked to save the data,
        causing sam check to never complete.
        """
        template_path = self.test_data_path.joinpath(template_file)

        stack_name = self._method_to_stack_name(self.id())

        check_command_list = self.get_minimal_check_command_list(template_path)

        check_process_execute = run_command_with_input(
            check_command_list,
            "{}\n1:2\n1\n-4\n1\n-3\nfive\n1234\n0\n1111\n0\n42\n900001\n300000"
            "\n4\n8:KB\nnine:GB\n128:GB\n4.8:GB\n-2\n2300\nfour\n555\nno\n".format(stack_name).encode(),
        )

        stdout = check_process_execute.stdout.strip()

        self.assertIn(bytes("Incorrect value entered. Please enter a valid input", encoding="utf-8"), stdout)
        self.assertIn(
            bytes("Numbers out of range. Please select values within the list range.", encoding="utf-8"), stdout
        )
        self.assertIn(bytes("Please enter a number within the range", encoding="utf-8"), stdout)
        self.assertIn(bytes("Error: five is not a valid integer", encoding="utf-8"), stdout)
        self.assertIn(bytes("Please enter a valid input.", encoding="utf-8"), stdout)
        self.assertIn(bytes("Please enter a valid memory unit.", encoding="utf-8"), stdout)
        self.assertIn(bytes("Please enter a valid amount of memory.", encoding="utf-8"), stdout)
        self.assertIn(bytes("Please enter a valid amount of memory within the range.", encoding="utf-8"), stdout)
        self.assertIn(bytes("is not a valid integer", encoding="utf-8"), stdout)
        self.assertIn(bytes("Please enter a valid responce.", encoding="utf-8"), stdout)

        self.assertEqual(check_process_execute.process.returncode, 1)

    def _method_to_stack_name(self, method_name):
        """Method expects method name which can be a full path. Eg: test.integration.test_deploy_command.method_name"""
        method_name = method_name.split(".")[-1]
        return f"{method_name.replace('_', '-')}-{CFN_PYTHON_VERSION_SUFFIX}"

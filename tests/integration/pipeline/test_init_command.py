from pathlib import Path

from tests.integration.pipeline.base import InitIntegBase
from tests.testing_utils import run_command_with_inputs

QUICK_START_JENKINS_INPUTS = [
    "1",  # quick start
    "1",  # jenkins, this depends on the template repo.
    "credential-id",
    "main",
    "template.yaml",
    "test",
    "test-stack",
    "test-pipeline-execution-role",
    "test-cfn-execution-role",
    "test-bucket",
    "test-ecr",
    "us-east-2",
    "prod",
    "prod-stack",
    "prod-pipeline-execution-role",
    "prod-cfn-execution-role",
    "prod-bucket",
    "prod-ecr",
    "us-west-2",
]


class TestInit(InitIntegBase):
    """
    Here we use Jenkins template for testing
    """

    def test_quick_start(self):
        generated_jenkinsfile_path = Path("Jenkinsfile")
        self.generated_files.append(generated_jenkinsfile_path)

        init_command_list = self.get_init_command_list()
        init_process_execute = run_command_with_inputs(init_command_list, QUICK_START_JENKINS_INPUTS)

        self.assertEqual(init_process_execute.process.returncode, 0)
        self.assertTrue(Path("Jenkinsfile").exists())

        expected_file_path = Path(__file__).parent.parent.joinpath(Path("testdata", "pipeline", "expected_jenkinsfile"))
        with open(expected_file_path, "r") as expected, open(generated_jenkinsfile_path, "r") as output:
            self.assertEqual(expected.read(), output.read())

    def test_failed_when_generated_file_already_exist(self):
        generated_jenkinsfile_path = Path("Jenkinsfile")
        generated_jenkinsfile_path.touch()  # the file now pre-exists
        self.generated_files.append(generated_jenkinsfile_path)

        init_command_list = self.get_init_command_list()
        init_process_execute = run_command_with_inputs(init_command_list, QUICK_START_JENKINS_INPUTS)

        self.assertEqual(init_process_execute.process.returncode, 1)
        stderr = init_process_execute.stderr.decode()
        self.assertIn(
            'Pipeline file "Jenkinsfile" already exists in project root directory, please remove it first.', stderr
        )

    def test_custom_template(self):
        generated_file = Path("weather")
        self.generated_files.append(generated_file)

        custom_template_path = Path(__file__).parent.parent.joinpath(Path("testdata", "pipeline", "custom_template"))
        inputs = ["2", str(custom_template_path), "Rainy"]  # custom template

        init_command_list = self.get_init_command_list()
        init_process_execute = run_command_with_inputs(init_command_list, inputs)

        self.assertEqual(init_process_execute.process.returncode, 0)

        self.assertTrue(generated_file.exists())

        with open(generated_file, "r") as f:
            self.assertEqual("Rainy\n", f.read())

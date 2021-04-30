from pathlib import Path

from tests.integration.pipeline.init_integ_base import InitIntegBase
from tests.testing_utils import run_command_with_input

QUICK_START_JENKINS_INPUTS = [
    "1",  # quick start
    "1",  # jenkins, this depends on the template repo.
    "1",  # two stage pipeline, this depends on the template repo.
    "credential-id",
    "main",
    "template.yaml",
    "test-stack",
    "test-pipeline-execution-role",
    "test-cfn-execution-role",
    "test-bucket",
    "",  # no ecr
    "",  # default region, us-east-2
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
        init_process_execute = run_command_with_input(
            init_command_list, ("\n".join(QUICK_START_JENKINS_INPUTS) + "\n").encode()
        )

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
        init_process_execute = run_command_with_input(
            init_command_list, ("\n".join(QUICK_START_JENKINS_INPUTS) + "\n").encode()
        )

        self.assertEqual(init_process_execute.process.returncode, 1)
        stderr = init_process_execute.stderr.decode()
        self.assertIn("Exception: Jenkinsfile already exists in project root directory. Please remove it first", stderr)

    def test_custom_template(self):
        generated_directory = Path("aws-sam-pipeline")
        self.generated_files.append(generated_directory)

        custom_template_path = Path(__file__).parent.parent.joinpath(Path("testdata", "pipeline", "custom_template"))
        inputs = ["2", str(custom_template_path), "Rainy"]  # custom template

        init_command_list = self.get_init_command_list()
        init_process_execute = run_command_with_input(init_command_list, ("\n".join(inputs) + "\n").encode())

        self.assertEqual(init_process_execute.process.returncode, 0)

        generated_file = Path(generated_directory, "weather")
        self.assertTrue(generated_file.exists())

        with open(generated_file, "r") as f:
            self.assertEqual("Rainy\n", f.read())

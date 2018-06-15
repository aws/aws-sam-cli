import os
import tempfile

from subprocess import Popen, PIPE, call
from nose_parameterized import parameterized, param

from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase


class TestWithDifferentLambdaRuntimeZips(InvokeIntegBase):

    def setUp(self):

        self.template_path = os.path.join(self.test_data_path, "invoke", "runtimes", "template.yaml")

        self.events_file = tempfile.NamedTemporaryFile()
        self.events_file.write('"yolo"')  # Just empty event
        self.events_file.flush()

        self.events_file_path = self.events_file.name

        self.saved_path = os.getcwd()
        self.new_path = os.path.join(self.test_data_path, "invoke", "runtimes", "java8")
        os.chdir(self.new_path)
        maven_cmd_path = os.path.join(os.getcwd(), "mvnw")
        call([maven_cmd_path, 'clean', 'package', 'shade:shade'])
        os.chdir(self.saved_path)

    def tearDown(self):
        self.events_file.close()

    @parameterized.expand([
        param("Go1xFunction"),
        param("Java8Function")
    ])
    def test_runtime_zip(self, function_name):
        command_list = self.get_command_list(function_name,
                                             template_path=self.template_path,
                                             event_path=self.events_file_path)

        process = Popen(command_list, stdout=PIPE)
        return_code = process.wait()

        self.assertEquals(return_code, 0)
        process_stdout = b"".join(process.stdout.readlines()).strip()
        self.assertEquals(process_stdout.decode('utf-8'), '"Hello World"')

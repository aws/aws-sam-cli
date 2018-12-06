"""
Functional test to ensure Lambda runtime Docker containers can be created, run and managed
"""
import os
import io
import random
import shutil
import docker

from contextlib import contextmanager
from unittest import TestCase

from samcli.commands.local.lib.debug_context import DebugContext
from tests.functional.function_code import nodejs_lambda
from samcli.local.docker.lambda_container import LambdaContainer
from samcli.local.docker.manager import ContainerManager
from samcli.local.docker.lambda_image import LambdaImage
from samcli.local.layers.layer_downloader import LayerDownloader


class TestLambdaContainer(TestCase):
    """
    Verify that the Lambda runtime Docker container is setup properly. It focuses on functionality that are
    non-trivial to unit test such as connecting container to correct network, mounting folder properly, or
    setting up debug port forwarding. These operations might also exhibit differences across Operating Systems, hence
    necessary to tests them here.
    """
    IMAGE_NAME = "lambci/lambda:nodejs4.3"

    HELLO_WORLD_CODE = """
    exports.handler = function(event, context, callback){
    
        console.log("**This string is printed from Lambda function**"); 
        callback(null, {"a": "b"})
    }
    """

    @classmethod
    def setUpClass(cls):

        manager = ContainerManager()
        if not manager.has_image(cls.IMAGE_NAME):
            manager.pull_image(cls.IMAGE_NAME)

    def setUp(self):
        random.seed()

        self.runtime = "nodejs4.3"
        self.expected_docker_image = self.IMAGE_NAME
        self.handler = "index.handler"
        self.layers = []
        self.debug_port = _rand_port()
        self.debug_context = DebugContext(debug_port=self.debug_port,
                                          debugger_path=None,
                                          debug_args=None)
        self.code_dir = nodejs_lambda(self.HELLO_WORLD_CODE)
        self.network_prefix = "sam_cli_test_network"

        self.docker_client = docker.from_env()

    def testDown(self):

        # Delete the code path if it exists
        if os.path.exists(self.code_dir):
            shutil.rmtree(self.code_dir)

    def test_basic_creation(self):
        """
        A docker container must be successfully created
        """
        layer_downloader = LayerDownloader("./", "./")
        image_builder = LambdaImage(layer_downloader, False, False)
        container = LambdaContainer(self.runtime, self.handler, self.code_dir, self.layers, image_builder)

        self.assertIsNone(container.id, "Container must not have ID before creation")

        # Create the container and verify its properties
        with self._create(container):
            self.assertIsNotNone(container.id, "Container must have an ID")

            # Call Docker API to make sure container indeed exists
            actual_container = self.docker_client.containers.get(container.id)
            self.assertEquals(actual_container.status, "created")
            self.assertTrue(self.expected_docker_image in actual_container.image.tags,
                            "Image name of the container must be " + self.expected_docker_image)

    def test_debug_port_is_created_on_host(self):

        layer_downloader = LayerDownloader("./", "./")
        image_builder = LambdaImage(layer_downloader, False, False)
        container = LambdaContainer(self.runtime, self.handler, self.code_dir, self.layers, image_builder, debug_options=self.debug_context)

        with self._create(container):

            container.start()

            # After container is started, query the container to make sure it is bound to the right ports
            port_binding = self.docker_client.api.port(container.id, self.debug_port)
            self.assertIsNotNone(port_binding, "Container must be bound to a port on host machine")
            self.assertEquals(1, len(port_binding), "Only one port must be bound to the container")
            self.assertEquals(port_binding[0]["HostPort"], str(self.debug_port))

    def test_container_is_attached_to_network(self):
        layer_downloader = LayerDownloader("./", "./")
        image_builder = LambdaImage(layer_downloader, False, False)
        container = LambdaContainer(self.runtime, self.handler, self.code_dir, self.layers, image_builder)

        with self._network_create() as network:

            # Ask the container to attach to the network
            container.network_id = network.id
            with self._create(container):

                container.start()

                # Now that the container has been created, it would be connected to the network
                # Fetch the latest information about this network from server
                network.reload()

                self.assertEquals(1, len(network.containers))
                self.assertEquals(container.id, network.containers[0].id)

    def test_function_result_is_available_in_stdout_and_logs_in_stderr(self):

        # This is the JSON result from Lambda function
        # Convert to proper binary type to be compatible with Python 2 & 3
        expected_output = b'{"a":"b"}'
        expected_stderr = b"**This string is printed from Lambda function**"

        layer_downloader = LayerDownloader("./", "./")
        image_builder = LambdaImage(layer_downloader, False, False)
        container = LambdaContainer(self.runtime, self.handler, self.code_dir, self.layers, image_builder)
        stdout_stream = io.BytesIO()
        stderr_stream = io.BytesIO()

        with self._create(container):

            container.start()
            container.wait_for_logs(stdout=stdout_stream, stderr=stderr_stream)

            function_output = stdout_stream.getvalue()
            function_stderr = stderr_stream.getvalue()

            self.assertEquals(function_output.strip(), expected_output)
            self.assertIn(expected_stderr, function_stderr)

    @contextmanager
    def _create(self, container):
        """
        Create a container and delete it when execute leaves the given context

        :param samcli.local.docker.container.Container container: Container to create
        :yield: ID of the created container
        """

        id = None
        try:
            id = container.create()
            yield id
        finally:
            if id:
                container.delete()

    @contextmanager
    def _network_create(self):

        name = "{}_{}".format(self.network_prefix, random.randint(1, 100))
        network = None

        try:
            network = self.docker_client.networks.create(name)
            yield network
        finally:
            if network:
                network.remove()

def _rand_port():
    return random.randint(30000, 40000)


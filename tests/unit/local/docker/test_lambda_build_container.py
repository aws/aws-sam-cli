"""
Unit test for Lambda Build Container management
"""

import json

from unittest import TestCase
from mock import patch

from samcli.local.docker.lambda_build_container import LambdaBuildContainer


class TestLambdaBuildContainer_init(TestCase):

    @patch.object(LambdaBuildContainer, "_make_request")
    @patch.object(LambdaBuildContainer, "_get_image")
    @patch.object(LambdaBuildContainer, "_get_entrypoint")
    @patch.object(LambdaBuildContainer, "_get_container_dirs")
    def test_must_init_class(self,
                             get_container_dirs_mock,
                             get_entrypoint_mock,
                             get_image_mock,
                             make_request_mock):

        request = make_request_mock.return_value = "somerequest"
        entry = get_entrypoint_mock.return_value = "entrypoint"
        image = get_image_mock.return_value = "imagename"
        container_dirs = get_container_dirs_mock.return_value = {
            "source_dir": "/mysource",
            "manifest_dir": "/mymanifest",
            "artifacts_dir": "/myartifacts",
            "scratch_dir": "/myscratch",
        }

        container = LambdaBuildContainer("protocol",
                                         "language",
                                         "dependency",
                                         "application",
                                         "/foo/source",
                                         "/bar/manifest.txt",
                                         "runtime",
                                         optimizations="optimizations",
                                         options="options",
                                         log_level="log-level")

        self.assertEquals(container.image, image)
        self.assertEquals(container.executable_name, "lambda-builders")
        self.assertEquals(container._entrypoint, entry)
        self.assertEquals(container._cmd, [])
        self.assertEquals(container._working_dir, container_dirs["source_dir"])
        self.assertEquals(container._host_dir, "/foo/source")
        self.assertEquals(container._env_vars, {"LAMBDA_BUILDERS_LOG_LEVEL": "log-level"})
        self.assertEquals(container._additional_volumes, {
            "/bar": {
                "bind": container_dirs["manifest_dir"],
                "mode": "ro"
            }
        })

        self.assertEquals(container._exposed_ports, None)
        self.assertEquals(container._memory_limit_mb, None)
        self.assertEquals(container._network_id, None)
        self.assertEquals(container._container_opts, None)

        make_request_mock.assert_called_once()
        get_entrypoint_mock.assert_called_once_with(request)
        get_image_mock.assert_called_once_with("runtime")
        get_container_dirs_mock.assert_called_once_with("/foo/source", "/bar")


class TestLambdaBuildContainer_make_request(TestCase):

    def test_must_make_request_object_string(self):

        container_dirs = {
            "source_dir": "source_dir",
            "artifacts_dir": "artifacts_dir",
            "scratch_dir": "scratch_dir",
            "manifest_dir": "manifest_dir"
        }

        result = LambdaBuildContainer._make_request("protocol",
                                                    "language",
                                                    "dependency",
                                                    "application",
                                                    container_dirs,
                                                    "manifest_file_name",
                                                    "runtime",
                                                    "optimizations",
                                                    "options")

        self.maxDiff = None  # Print whole json diff
        self.assertEqual(json.loads(result), {
            "jsonschema": "2.0",
            "id": 1,
            "method": "LambdaBuilder.build",
            "params": {
                "__protocol_version": "protocol",
                "capability": {
                    "language": "language",
                    "dependency_manager": "dependency",
                    "application_framework": "application"
                },
                "source_dir": "source_dir",
                "artifacts_dir": "artifacts_dir",
                "scratch_dir": "scratch_dir",
                "manifest_path": "manifest_dir/manifest_file_name",
                "runtime": "runtime",
                "optimizations": "optimizations",
                "options": "options"
            }
        })


class TestLambdaBuildContainer_get_container_dirs(TestCase):

    def test_must_return_dirs(self):
        source_dir = "source"
        manifest_dir = "manifest"

        result = LambdaBuildContainer._get_container_dirs(source_dir, manifest_dir)

        self.assertEquals(result, {
            "source_dir": "/tmp/samcli/source",
            "manifest_dir": "/tmp/samcli/manifest",
            "artifacts_dir": "/tmp/samcli/artifacts",
            "scratch_dir": "/tmp/samcli/scratch",
        })

    def test_must_override_manifest_if_equal_to_source(self):
        source_dir = "/home/source"
        manifest_dir = "/home/source"

        result = LambdaBuildContainer._get_container_dirs(source_dir, manifest_dir)

        self.assertEquals(result, {

            # When source & manifest directories are the same, manifest_dir must be equal to source
            "source_dir": "/tmp/samcli/source",
            "manifest_dir": "/tmp/samcli/source",

            "artifacts_dir": "/tmp/samcli/artifacts",
            "scratch_dir": "/tmp/samcli/scratch",
        })


class TestLambdaBuildContainer_get_image(TestCase):

    def test_must_get_image_name(self):
        self.assertEquals("lambci/lambda:build-myruntime", LambdaBuildContainer._get_image("myruntime"))


class TestLambdaBuildContainer_get_entrypoint(TestCase):

    def test_must_get_entrypoint(self):
        self.assertEquals(["lambda-builders", "requestjson"],
                          LambdaBuildContainer._get_entrypoint("requestjson"))

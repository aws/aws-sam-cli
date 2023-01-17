"""
Unit test for Lambda Build Container management
"""
import itertools
import json
import pathlib

from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from samcli.lib.utils.architecture import X86_64, ARM64
from samcli.local.docker.lambda_build_container import LambdaBuildContainer


class TestLambdaBuildContainer_init(TestCase):
    @patch.object(LambdaBuildContainer, "_make_request")
    @patch.object(LambdaBuildContainer, "_get_image")
    @patch.object(LambdaBuildContainer, "_get_entrypoint")
    @patch.object(LambdaBuildContainer, "get_container_dirs")
    def test_must_init_class(self, get_container_dirs_mock, get_entrypoint_mock, get_image_mock, make_request_mock):

        request = make_request_mock.return_value = "somerequest"
        entry = get_entrypoint_mock.return_value = "entrypoint"
        image = get_image_mock.return_value = "imagename"
        container_dirs = get_container_dirs_mock.return_value = {
            "source_dir": "/mysource",
            "manifest_dir": "/mymanifest",
            "artifacts_dir": "/myartifacts",
            "scratch_dir": "/myscratch",
        }

        container = LambdaBuildContainer(
            "protocol",
            "language",
            "dependency",
            "application",
            "/foo/source",
            "/bar/manifest.txt",
            "runtime",
            optimizations="optimizations",
            options="options",
            log_level="log-level",
            mode="mode",
            architecture="arm64",
        )

        self.assertEqual(container.image, image)
        self.assertEqual(container.executable_name, "lambda-builders")
        self.assertEqual(container._entrypoint, entry)
        self.assertEqual(container._cmd, [])
        self.assertEqual(container._working_dir, container_dirs["source_dir"])
        self.assertEqual(container._host_dir, str(pathlib.Path("/foo/source").resolve()))
        self.assertEqual(container._env_vars, {"LAMBDA_BUILDERS_LOG_LEVEL": "log-level"})
        self.assertEqual(
            container._additional_volumes,
            {str(pathlib.Path("/bar").resolve()): {"bind": container_dirs["manifest_dir"], "mode": "ro"}},
        )

        self.assertEqual(container._exposed_ports, None)
        self.assertEqual(container._memory_limit_mb, None)
        self.assertEqual(container._network_id, None)
        self.assertEqual(container._container_opts, None)

        make_request_mock.assert_called_once()
        get_entrypoint_mock.assert_called_once_with(request)
        get_image_mock.assert_called_once_with("runtime", "arm64")
        get_container_dirs_mock.assert_called_once_with(
            str(pathlib.Path("/foo/source").resolve()), str(pathlib.Path("/bar").resolve())
        )


class TestLambdaBuildContainer_make_request(TestCase):
    @parameterized.expand(itertools.product([True, False], [[], ["exp1", "exp2"]]))
    @patch("samcli.local.docker.lambda_build_container.get_enabled_experimental_flags")
    def test_must_make_request_object_string(self, is_building_layer, experimental_flags, patched_experimental_flags):
        patched_experimental_flags.return_value = experimental_flags

        container_dirs = {
            "source_dir": "source_dir",
            "artifacts_dir": "artifacts_dir",
            "scratch_dir": "scratch_dir",
            "manifest_dir": "manifest_dir",
        }

        result = LambdaBuildContainer._make_request(
            "protocol",
            "language",
            "dependency",
            "application",
            container_dirs,
            "manifest_file_name",
            "runtime",
            "optimizations",
            "options",
            "executable_search_paths",
            "mode",
            "architecture",
            is_building_layer,
            build_in_source=False,
        )

        self.maxDiff = None  # Print whole json diff
        self.assertEqual(
            json.loads(result),
            {
                "jsonschema": "2.0",
                "id": 1,
                "method": "LambdaBuilder.build",
                "params": {
                    "__protocol_version": "protocol",
                    "capability": {
                        "language": "language",
                        "dependency_manager": "dependency",
                        "application_framework": "application",
                    },
                    "source_dir": "source_dir",
                    "artifacts_dir": "artifacts_dir",
                    "scratch_dir": "scratch_dir",
                    "manifest_path": "manifest_dir/manifest_file_name",
                    "runtime": "runtime",
                    "optimizations": "optimizations",
                    "options": "options",
                    "executable_search_paths": "executable_search_paths",
                    "mode": "mode",
                    "architecture": "architecture",
                    "is_building_layer": is_building_layer,
                    "experimental_flags": experimental_flags,
                    "build_in_source": False,
                },
            },
        )


class TestLambdaBuildContainer_get_container_dirs(TestCase):
    def test_must_return_dirs(self):
        source_dir = "source"
        manifest_dir = "manifest"

        result = LambdaBuildContainer.get_container_dirs(source_dir, manifest_dir)

        self.assertEqual(
            result,
            {
                "source_dir": "/tmp/samcli/source",
                "manifest_dir": "/tmp/samcli/manifest",
                "artifacts_dir": "/tmp/samcli/artifacts",
                "scratch_dir": "/tmp/samcli/scratch",
            },
        )

    def test_must_override_manifest_if_equal_to_source(self):
        source_dir = "/home/source"
        manifest_dir = "/home/source"

        result = LambdaBuildContainer.get_container_dirs(source_dir, manifest_dir)

        self.assertEqual(
            result,
            {
                # When source & manifest directories are the same, manifest_dir must be equal to source
                "source_dir": "/tmp/samcli/source",
                "manifest_dir": "/tmp/samcli/source",
                "artifacts_dir": "/tmp/samcli/artifacts",
                "scratch_dir": "/tmp/samcli/scratch",
            },
        )


class TestLambdaBuildContainer_get_image(TestCase):
    @parameterized.expand(
        [
            ("myruntime", ARM64, "public.ecr.aws/sam/build-myruntime:latest-arm64"),
            ("nodejs14.x", X86_64, "public.ecr.aws/sam/build-nodejs14.x:latest-x86_64"),
        ]
    )
    def test_must_get_image_name(self, runtime, architecture, expected_image_name):
        self.assertEqual(expected_image_name, LambdaBuildContainer._get_image(runtime, architecture))


class TestLambdaBuildContainer_get_image_tag(TestCase):
    @parameterized.expand(
        [
            (ARM64, "latest-arm64"),
            (X86_64, "latest-x86_64"),
        ]
    )
    def test_must_get_image_tag(self, architecture, expected_image_tag):
        self.assertEqual(expected_image_tag, LambdaBuildContainer.get_image_tag(architecture))


class TestLambdaBuildContainer_get_entrypoint(TestCase):
    def test_must_get_entrypoint(self):
        self.assertEqual(["lambda-builders", "requestjson"], LambdaBuildContainer._get_entrypoint("requestjson"))


class TestLambdaBuildContainer_convert_to_container_dirs(TestCase):
    def test_must_work_on_abs_and_relative_paths(self):

        input = [".", "../foo", "/some/abs/path"]
        mapping = {str(pathlib.Path(".").resolve()): "/first", "../foo": "/second", "/some/abs/path": "/third"}

        expected = ["/first", "/second", "/third"]
        result = LambdaBuildContainer._convert_to_container_dirs(input, mapping)

        self.assertEqual(result, expected)

    def test_must_skip_unknown_paths(self):

        input = ["/known/path", "/unknown/path"]
        mapping = {"/known/path": "/first"}

        expected = ["/first", "/unknown/path"]
        result = LambdaBuildContainer._convert_to_container_dirs(input, mapping)

        self.assertEqual(result, expected)

    def test_must_skip_on_empty_input(self):

        input = None
        mapping = {"/known/path": "/first"}

        expected = None
        result = LambdaBuildContainer._convert_to_container_dirs(input, mapping)

        self.assertEqual(result, expected)

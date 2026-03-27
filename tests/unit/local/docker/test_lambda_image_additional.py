"""
Additional tests for LambdaImage functionality to improve coverage
"""

import os
import platform
import tempfile
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch, call

import docker
from parameterized import parameterized

from samcli.lib.utils.architecture import ARM64, X86_64
from samcli.lib.utils.packagetype import ZIP, IMAGE
from samcli.local.docker.lambda_image import LambdaImage, Runtime, TEST_RUNTIMES
from samcli.local.common.file_lock import DEFAULT_LOCK_TIMEOUT


class TestLambdaImageAdditional(TestCase):
    def setUp(self):
        self.layer_cache_dir = tempfile.gettempdir()

    def test_runtime_has_value_true(self):
        """Test Runtime.has_value returns True for valid runtime"""
        self.assertTrue(Runtime.has_value("python3.12"))
        self.assertTrue(Runtime.has_value("nodejs20.x"))

    def test_runtime_has_value_false(self):
        """Test Runtime.has_value returns False for invalid runtime"""
        self.assertFalse(Runtime.has_value("invalid-runtime"))
        self.assertFalse(Runtime.has_value("python4.0"))

    @parameterized.expand(
        [
            ("python3.12", X86_64, True, "python:3.12-preview-x86_64"),
            ("nodejs20.x", ARM64, True, "nodejs:20-preview-arm64"),
            ("go1.x", X86_64, True, "go:1-preview"),
        ]
    )
    def test_get_image_name_tag_with_preview(self, runtime, architecture, is_preview, expected):
        """Test Runtime.get_image_name_tag with preview flag"""
        result = Runtime.get_image_name_tag(runtime, architecture, is_preview)
        self.assertEqual(result, expected)

    def test_lambda_image_initialization_with_invoke_images(self):
        """Test LambdaImage initialization with invoke_images parameter"""
        invoke_images = {"func1": "custom-image:latest"}
        lambda_image = LambdaImage(
            "layer_downloader", False, False, docker_client="docker_client", invoke_images=invoke_images
        )
        self.assertEqual(lambda_image.invoke_images, invoke_images)

    @patch("samcli.local.docker.lambda_image.cleanup_stale_locks")
    def test_lambda_image_initialization_calls_cleanup(self, mock_cleanup):
        """Test that LambdaImage initialization calls cleanup of old lock files"""
        LambdaImage("layer_downloader", False, False)
        mock_cleanup.assert_called_once_with(Path(tempfile.gettempdir()), "building")

    def test_docker_client_lazy_initialization(self):
        """Test that docker_client is lazily initialized"""
        with patch("samcli.local.docker.lambda_image.get_validated_container_client") as mock_get_client:
            mock_client = Mock()
            mock_get_client.return_value = mock_client

            lambda_image = LambdaImage("layer_downloader", False, False)

            # get_validated_container_client should not be called yet
            mock_get_client.assert_not_called()

            # Access docker_client property
            client = lambda_image.docker_client

            # Now it should be called
            mock_get_client.assert_called_once()
            self.assertEqual(client, mock_client)

            # Second access should return cached client
            client2 = lambda_image.docker_client
            self.assertEqual(client2, mock_client)
            mock_get_client.assert_called_once()  # Still only called once

    @patch("samcli.local.docker.lambda_image.platform.system")
    def test_build_with_windows_go_runtime_fallback(self, mock_system):
        """Test build with Windows and go1.x runtime uses fallback image"""
        mock_system.return_value = "Windows"

        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir
        docker_client_mock.images.get.side_effect = docker.errors.ImageNotFound("not found")
        docker_client_mock.images.list.return_value = []

        with patch("samcli.local.docker.lambda_image.LambdaImage._build_image") as mock_build:
            lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)
            lambda_image.build("go1.x", ZIP, None, [], X86_64)

            # Should use the fallback image with version tag
            mock_build.assert_called_once()
            args = mock_build.call_args[0]
            base_image = args[0]
            self.assertTrue(base_image.endswith(".2023.08.02.10"))

    def test_get_config_success(self):
        """Test get_config returns image config successfully"""
        docker_client_mock = Mock()
        image_mock = Mock()
        image_mock.attrs = {"Config": {"Env": ["TEST=value"]}}
        docker_client_mock.images.get.return_value = image_mock

        lambda_image = LambdaImage("layer_downloader", False, False, docker_client=docker_client_mock)
        config = lambda_image.get_config("test-image:latest")

        self.assertEqual(config, {"Env": ["TEST=value"]})
        docker_client_mock.images.get.assert_called_once_with("test-image:latest")

    def test_get_config_image_not_found(self):
        """Test get_config returns empty dict when image not found"""
        docker_client_mock = Mock()
        docker_client_mock.images.get.side_effect = docker.errors.ImageNotFound("not found")

        lambda_image = LambdaImage("layer_downloader", False, False, docker_client=docker_client_mock)
        config = lambda_image.get_config("test-image:latest")

        self.assertEqual(config, {})

    @patch("samcli.local.docker.lambda_image.platform.system")
    def test_build_image_windows_tar_filter(self, mock_system):
        """Test _build_image uses tar filter on Windows"""
        mock_system.return_value = "Windows"

        docker_client_mock = Mock()
        docker_client_mock.api.build.return_value = [{"stream": "Step 1/1 : FROM base"}]

        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir

        layer_mock = Mock()
        layer_mock.codeuri = "/path/to/layer"
        layer_mock.name = "test-layer"

        with patch("samcli.local.docker.lambda_image.create_tarball") as mock_tarball:
            with patch("samcli.local.docker.lambda_image.uuid.uuid4", return_value="test-uuid"):
                with patch("samcli.local.docker.lambda_image.Path") as mock_path:
                    mock_dockerfile = Mock()
                    mock_dockerfile.exists.return_value = True
                    mock_path.return_value = mock_dockerfile

                    with patch("builtins.open", create=True):
                        lambda_image = LambdaImage(
                            layer_downloader_mock, False, False, docker_client=docker_client_mock
                        )
                        lambda_image._build_image("base-image", "test-tag", [layer_mock], X86_64)

                        # Verify tar filter was used (not None)
                        mock_tarball.assert_called_once()
                        call_args = mock_tarball.call_args
                        self.assertIsNotNone(call_args[1].get("tar_filter"))

    @patch("samcli.local.docker.lambda_image.platform.system")
    def test_build_image_non_windows_no_tar_filter(self, mock_system):
        """Test _build_image doesn't use tar filter on non-Windows"""
        mock_system.return_value = "Linux"

        docker_client_mock = Mock()
        docker_client_mock.api.build.return_value = [{"stream": "Step 1/1 : FROM base"}]

        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir

        layer_mock = Mock()
        layer_mock.codeuri = "/path/to/layer"
        layer_mock.name = "test-layer"

        with patch("samcli.local.docker.lambda_image.create_tarball") as mock_tarball:
            with patch("samcli.local.docker.lambda_image.uuid.uuid4", return_value="test-uuid"):
                with patch("samcli.local.docker.lambda_image.Path") as mock_path:
                    mock_dockerfile = Mock()
                    mock_dockerfile.exists.return_value = True
                    mock_path.return_value = mock_dockerfile

                    with patch("builtins.open", create=True):
                        lambda_image = LambdaImage(
                            layer_downloader_mock, False, False, docker_client=docker_client_mock
                        )
                        lambda_image._build_image("base-image", "test-tag", [layer_mock], X86_64)

                        # Verify tar filter was None
                        mock_tarball.assert_called_once()
                        call_args = mock_tarball.call_args
                        self.assertIsNone(call_args[1].get("tar_filter"))

    def test_build_image_finch_already_exists_in_stream(self):
        """Test _build_image handles Finch 'already exists' in stream messages"""
        docker_client_mock = Mock()
        docker_client_mock.api.build.return_value = [
            {"stream": "Step 1/1 : FROM base"},
            {"stream": "Image already exists"},
            {"stream": "Successfully built abc123"},
        ]

        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir

        with patch("samcli.local.docker.lambda_image.create_tarball"):
            with patch("samcli.local.docker.lambda_image.uuid.uuid4", return_value="test-uuid"):
                with patch("samcli.local.docker.lambda_image.Path") as mock_path:
                    mock_dockerfile = Mock()
                    mock_dockerfile.exists.return_value = True
                    mock_path.return_value = mock_dockerfile

                    with patch("builtins.open", create=True):
                        with patch("samcli.local.docker.lambda_image.LOG") as mock_log:
                            lambda_image = LambdaImage(
                                layer_downloader_mock, False, False, docker_client=docker_client_mock
                            )
                            lambda_image._build_image("base-image", "test-tag", [], X86_64)

                            # Should log the Finch success message
                            mock_log.info.assert_called_with(
                                "Finch reported image already exists - treating as successful build"
                            )

    def test_build_image_finch_already_exists_in_error(self):
        """Test _build_image handles Finch 'already exists' in error messages"""
        docker_client_mock = Mock()
        docker_client_mock.api.build.return_value = [
            {"error": "Image already exists"},
        ]

        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir

        with patch("samcli.local.docker.lambda_image.create_tarball"):
            with patch("samcli.local.docker.lambda_image.uuid.uuid4", return_value="test-uuid"):
                with patch("samcli.local.docker.lambda_image.Path") as mock_path:
                    mock_dockerfile = Mock()
                    mock_dockerfile.exists.return_value = True
                    mock_path.return_value = mock_dockerfile

                    with patch("builtins.open", create=True):
                        with patch("samcli.local.docker.lambda_image.LOG") as mock_log:
                            lambda_image = LambdaImage(
                                layer_downloader_mock, False, False, docker_client=docker_client_mock
                            )
                            lambda_image._build_image("base-image", "test-tag", [], X86_64)

                            # Should log the Finch success message
                            mock_log.info.assert_called_with(
                                "Finch reported image already exists - treating as successful build"
                            )

    def test_build_image_handles_status_and_progress_logs(self):
        """Test _build_image handles status and progress log messages"""
        docker_client_mock = Mock()
        docker_client_mock.api.build.return_value = [
            {"status": "Pulling from library/python"},
            {"progress": "50%"},
            {"stream": "Successfully built abc123"},
        ]

        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir

        with patch("samcli.local.docker.lambda_image.create_tarball"):
            with patch("samcli.local.docker.lambda_image.uuid.uuid4", return_value="test-uuid"):
                with patch("samcli.local.docker.lambda_image.Path") as mock_path:
                    mock_dockerfile = Mock()
                    mock_dockerfile.exists.return_value = True
                    mock_path.return_value = mock_dockerfile

                    with patch("builtins.open", create=True):
                        with patch("samcli.local.docker.lambda_image.LOG") as mock_log:
                            lambda_image = LambdaImage(
                                layer_downloader_mock, False, False, docker_client=docker_client_mock
                            )
                            lambda_image._build_image("base-image", "test-tag", [], X86_64)

                            # Should log debug messages for status and progress
                            mock_log.debug.assert_any_call("Build status: Pulling from library/python")
                            mock_log.debug.assert_any_call("Build progress: 50%")

    def test_build_image_handles_non_dict_logs(self):
        """Test _build_image handles non-dict log messages"""
        docker_client_mock = Mock()
        docker_client_mock.api.build.return_value = ["string log message", {"stream": "Successfully built abc123"}]

        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir

        with patch("samcli.local.docker.lambda_image.create_tarball"):
            with patch("samcli.local.docker.lambda_image.uuid.uuid4", return_value="test-uuid"):
                with patch("samcli.local.docker.lambda_image.Path") as mock_path:
                    mock_dockerfile = Mock()
                    mock_dockerfile.exists.return_value = True
                    mock_path.return_value = mock_dockerfile

                    with patch("builtins.open", create=True):
                        with patch("samcli.local.docker.lambda_image.LOG") as mock_log:
                            lambda_image = LambdaImage(
                                layer_downloader_mock, False, False, docker_client=docker_client_mock
                            )
                            lambda_image._build_image("base-image", "test-tag", [], X86_64)

                            # Should log debug message for non-dict log
                            mock_log.debug.assert_any_call("Non-dict build log: string log message")

    def test_build_image_handles_none_logs(self):
        """Test _build_image handles None log messages"""
        docker_client_mock = Mock()
        docker_client_mock.api.build.return_value = [None, {"stream": "Successfully built abc123"}]

        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir

        with patch("samcli.local.docker.lambda_image.create_tarball"):
            with patch("samcli.local.docker.lambda_image.uuid.uuid4", return_value="test-uuid"):
                with patch("samcli.local.docker.lambda_image.Path") as mock_path:
                    mock_dockerfile = Mock()
                    mock_dockerfile.exists.return_value = True
                    mock_path.return_value = mock_dockerfile

                    with patch("builtins.open", create=True):
                        lambda_image = LambdaImage(
                            layer_downloader_mock, False, False, docker_client=docker_client_mock
                        )
                        # Should not raise exception
                        lambda_image._build_image("base-image", "test-tag", [], X86_64)

    def test_remove_rapid_images_api_error_on_list(self):
        """Test _remove_rapid_images handles API error when listing images"""
        docker_client_mock = Mock()
        docker_client_mock.images.list.side_effect = docker.errors.APIError("API error")

        with patch("samcli.local.docker.lambda_image.LOG") as mock_log:
            lambda_image = LambdaImage("layer_downloader", False, False, docker_client=docker_client_mock)
            lambda_image._remove_rapid_images("test-repo")

            mock_log.warning.assert_called_once()

    def test_remove_rapid_images_api_error_on_remove(self):
        """Test _remove_rapid_images handles API error when removing images"""
        image_mock = Mock()
        image_mock.id = "image123"
        image_mock.tags = ["test-repo:rapid-x86_64"]

        docker_client_mock = Mock()
        docker_client_mock.images.list.return_value = [image_mock]
        docker_client_mock.images.remove.side_effect = docker.errors.APIError("Remove error")

        with patch("samcli.local.docker.lambda_image.LOG") as mock_log:
            lambda_image = LambdaImage("layer_downloader", False, False, docker_client=docker_client_mock)
            lambda_image._remove_rapid_images("test-repo")

            mock_log.warning.assert_called()

    def test_build_with_test_runtime_preview(self):
        """Test build with runtime in TEST_RUNTIMES uses preview image"""
        # Add a runtime to TEST_RUNTIMES for this test
        original_test_runtimes = TEST_RUNTIMES.copy()
        TEST_RUNTIMES.append("python3.12")

        try:
            docker_client_mock = Mock()
            layer_downloader_mock = Mock()
            layer_downloader_mock.layer_cache = self.layer_cache_dir
            docker_client_mock.images.get.side_effect = docker.errors.ImageNotFound("not found")
            docker_client_mock.images.list.return_value = []

            with patch("samcli.local.docker.lambda_image.LambdaImage._build_image") as mock_build:
                lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)
                lambda_image.build("python3.12", ZIP, None, [], X86_64)

                # Should use preview image
                mock_build.assert_called_once()
                args = mock_build.call_args[0]
                base_image = args[0]
                self.assertIn("preview", base_image)
        finally:
            # Restore original TEST_RUNTIMES
            TEST_RUNTIMES.clear()
            TEST_RUNTIMES.extend(original_test_runtimes)

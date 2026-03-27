"""
Tests for concurrent build functionality in LambdaImage
"""

import tempfile
from unittest import TestCase
from unittest.mock import Mock, patch, call
from pathlib import Path

import docker

from samcli.lib.utils.architecture import X86_64
from samcli.lib.utils.packagetype import ZIP
from samcli.local.docker.lambda_image import LambdaImage
from samcli.local.common.file_lock import FileLock


class TestLambdaImageConcurrentBuild(TestCase):
    def setUp(self):
        self.layer_cache_dir = tempfile.gettempdir()

    @patch("samcli.local.docker.lambda_image.FileLock")
    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    def test_build_with_lock_acquired_success(self, mock_build_image, mock_lock_class):
        """Test build when lock is acquired successfully"""
        # Setup mocks
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock
        mock_lock.acquire_lock.return_value = True

        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir
        docker_client_mock.images.get.side_effect = docker.errors.ImageNotFound("not found")
        docker_client_mock.images.list.return_value = []

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        with patch("samcli.local.docker.lambda_image.StreamWriter") as mock_stream_writer:
            mock_stream = Mock()
            mock_stream_writer.return_value = mock_stream

            result = lambda_image.build("python3.12", ZIP, None, [], X86_64)

            # Verify lock was acquired and build was called
            mock_lock.acquire_lock.assert_called_once()
            mock_build_image.assert_called_once()
            mock_lock.release_lock.assert_called_once_with(success=True)
            mock_stream.write_str.assert_any_call("Building image...")

    @patch("samcli.local.docker.lambda_image.FileLock")
    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    def test_build_with_lock_acquired_exception(self, mock_build_image, mock_lock_class):
        """Test build when lock is acquired but build fails"""
        # Setup mocks
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock
        mock_lock.acquire_lock.return_value = True
        mock_build_image.side_effect = Exception("Build failed")

        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir
        docker_client_mock.images.get.side_effect = docker.errors.ImageNotFound("not found")
        docker_client_mock.images.list.return_value = []

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        with patch("samcli.local.docker.lambda_image.StreamWriter"):
            with self.assertRaises(Exception):
                lambda_image.build("python3.12", ZIP, None, [], X86_64)

            # Verify lock was released with failure
            mock_lock.release_lock.assert_called_once_with(success=False)

    @patch("samcli.local.docker.lambda_image.FileLock")
    def test_build_wait_for_concurrent_build_success(self, mock_lock_class):
        """Test build waits for concurrent build that succeeds"""
        # Setup mocks
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock
        mock_lock.acquire_lock.return_value = False  # Another process has lock
        mock_lock.wait_for_operation.return_value = True  # Build succeeds

        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir
        docker_client_mock.images.get.side_effect = [
            docker.errors.ImageNotFound("not found"),  # Initial check
            Mock(),  # Image exists after concurrent build
        ]
        docker_client_mock.images.list.return_value = []

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        with patch("samcli.local.docker.lambda_image.StreamWriter") as mock_stream_writer:
            mock_stream = Mock()
            mock_stream_writer.return_value = mock_stream

            result = lambda_image.build("python3.12", ZIP, None, [], X86_64)

            # Verify waiting messages
            mock_stream.write_str.assert_any_call("Another process is building the same image, waiting...")
            mock_stream.write_str.assert_any_call("Image build completed by another process.")
            mock_lock.wait_for_operation.assert_called_once()

    @patch("samcli.local.docker.lambda_image.FileLock")
    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    def test_build_wait_for_concurrent_build_image_not_found(self, mock_build_image, mock_lock_class):
        """Test build when concurrent build succeeds but image not found"""
        # Setup mocks
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock
        mock_lock.acquire_lock.return_value = False
        mock_lock.wait_for_operation.return_value = True

        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir
        docker_client_mock.images.get.side_effect = docker.errors.ImageNotFound("not found")
        docker_client_mock.images.list.return_value = []

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        with patch("samcli.local.docker.lambda_image.StreamWriter") as mock_stream_writer:
            mock_stream = Mock()
            mock_stream_writer.return_value = mock_stream

            with patch("samcli.local.docker.lambda_image.LOG") as mock_log:
                result = lambda_image.build("python3.12", ZIP, None, [], X86_64)

                # Should fallback to building ourselves
                mock_log.warning.assert_called_with(
                    "Expected image not found after concurrent build, building ourselves"
                )
                mock_build_image.assert_called_once()

    @patch("samcli.local.docker.lambda_image.FileLock")
    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    def test_build_wait_for_concurrent_build_failed(self, mock_build_image, mock_lock_class):
        """Test build when concurrent build fails or times out"""
        # Setup mocks
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock
        mock_lock.acquire_lock.return_value = False
        mock_lock.wait_for_operation.return_value = False  # Build failed/timed out

        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir
        docker_client_mock.images.get.side_effect = docker.errors.ImageNotFound("not found")
        docker_client_mock.images.list.return_value = []

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        with patch("samcli.local.docker.lambda_image.StreamWriter") as mock_stream_writer:
            mock_stream = Mock()
            mock_stream_writer.return_value = mock_stream

            with patch("samcli.local.docker.lambda_image.LOG") as mock_log:
                result = lambda_image.build("python3.12", ZIP, None, [], X86_64)

                # Should fallback to building ourselves
                mock_log.warning.assert_called_with("Concurrent build failed or timed out, building ourselves")
                mock_build_image.assert_called_once()

    @patch("samcli.local.docker.lambda_image.FileLock")
    def test_build_lock_initialization_with_correct_parameters(self, mock_lock_class):
        """Test that ImageBuildLock is initialized with correct parameters"""
        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = "/tmp/cache"
        docker_client_mock.images.get.side_effect = docker.errors.ImageNotFound("not found")
        docker_client_mock.images.list.return_value = []

        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock
        mock_lock.acquire_lock.return_value = True

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        with patch("samcli.local.docker.lambda_image.LambdaImage._build_image"):
            lambda_image.build("python3.12", ZIP, None, [], X86_64)

            # Verify FileLock was initialized with correct parameters
            # Should use system temp directory instead of layer cache directory
            mock_lock_class.assert_called_once_with(
                Path(tempfile.gettempdir()), "public.ecr.aws/lambda/python:3.12-rapid-x86_64", "building"
            )

    def test_build_with_layers_uses_different_image_name(self):
        """Test that build with layers uses different rapid image name format"""
        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir
        layer_downloader_mock.download_all.return_value = [Mock(name="layer1", is_defined_within_template=False)]
        docker_client_mock.images.get.side_effect = docker.errors.ImageNotFound("not found")
        docker_client_mock.images.list.return_value = []

        with patch("samcli.local.docker.lambda_image.FileLock") as mock_lock_class:
            mock_lock = Mock()
            mock_lock_class.return_value = mock_lock
            mock_lock.acquire_lock.return_value = True

            with patch("samcli.local.docker.lambda_image.LambdaImage._build_image"):
                with patch(
                    "samcli.local.docker.lambda_image.LambdaImage._generate_docker_image_version",
                    return_value="test-version",
                ):
                    lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)
                    result = lambda_image.build("python3.12", ZIP, None, [Mock()], X86_64)

                    # Should use samcli/lambda format for layered images
                    self.assertEqual(result, "samcli/lambda-test-version")

                    # Lock should be initialized with the layered image name
                    mock_lock_class.assert_called_once_with(
                        Path(tempfile.gettempdir()), "samcli/lambda-test-version", "building"
                    )

    @patch("samcli.local.docker.lambda_image.FileLock")
    def test_build_no_lock_when_not_building(self, mock_lock_class):
        """Test that no lock is used when image already exists and no build needed"""
        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir
        docker_client_mock.images.get.return_value = Mock()  # Image exists

        with patch("samcli.local.docker.lambda_image.LambdaImage.is_base_image_current", return_value=True):
            lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)
            result = lambda_image.build("python3.12", ZIP, None, [], X86_64)

            # No lock should be created since no build is needed
            mock_lock_class.assert_not_called()

    @patch("samcli.local.docker.lambda_image.FileLock")
    def test_build_with_force_build_uses_lock(self, mock_lock_class):
        """Test that force build uses lock even when image exists"""
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock
        mock_lock.acquire_lock.return_value = True

        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir
        docker_client_mock.images.get.return_value = Mock()  # Image exists
        docker_client_mock.images.list.return_value = []

        lambda_image = LambdaImage(
            layer_downloader_mock, False, True, docker_client=docker_client_mock
        )  # force_image_build=True

        with patch("samcli.local.docker.lambda_image.LambdaImage._build_image"):
            result = lambda_image.build("python3.12", ZIP, None, [], X86_64)

            # Lock should be used for force build
            mock_lock_class.assert_called_once()
            mock_lock.acquire_lock.assert_called_once()

    @patch("samcli.local.docker.lambda_image.FileLock")
    def test_build_with_template_defined_layers_uses_lock(self, mock_lock_class):
        """Test that build with template-defined layers uses lock"""
        mock_lock = Mock()
        mock_lock_class.return_value = mock_lock
        mock_lock.acquire_lock.return_value = True

        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = self.layer_cache_dir

        # Create a layer that is defined within template
        layer_mock = Mock()
        layer_mock.is_defined_within_template = True
        layer_mock.name = "template-layer"
        layer_downloader_mock.download_all.return_value = [layer_mock]

        # Mock image with proper attrs structure
        mock_image = Mock()
        mock_image.attrs = {"RepoDigests": ["repo@sha256:abc123"]}
        docker_client_mock.images.get.return_value = mock_image
        docker_client_mock.images.list.return_value = []

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        with patch("samcli.local.docker.lambda_image.LambdaImage._build_image"):
            with patch(
                "samcli.local.docker.lambda_image.LambdaImage._generate_docker_image_version",
                return_value="test-version",
            ):
                with patch(
                    "samcli.local.docker.lambda_image.LambdaImage.get_remote_image_digest", return_value="sha256:abc123"
                ):
                    result = lambda_image.build("python3.12", ZIP, None, [layer_mock], X86_64)

                    # Lock should be used for template-defined layers
                    mock_lock_class.assert_called_once()
                    mock_lock.acquire_lock.assert_called_once()

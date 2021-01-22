import io
import tempfile

from unittest import TestCase
from unittest.mock import patch, Mock, mock_open, ANY

from docker.errors import ImageNotFound, BuildError, APIError

from samcli.commands.local.lib.exceptions import InvalidIntermediateImageError
from samcli.lib.utils.packagetype import ZIP, IMAGE
from samcli.local.docker.lambda_image import LambdaImage
from samcli.commands.local.cli_common.user_exceptions import ImageBuildException
from samcli import __version__ as version


class TestLambdaImage(TestCase):
    def setUp(self):
        self.layer_cache_dir = tempfile.gettempdir()

    def test_initialization_without_defaults(self):
        lambda_image = LambdaImage("layer_downloader", False, False, docker_client="docker_client")

        self.assertEqual(lambda_image.layer_downloader, "layer_downloader")
        self.assertFalse(lambda_image.skip_pull_image)
        self.assertFalse(lambda_image.force_image_build)
        self.assertEqual(lambda_image.docker_client, "docker_client")

    @patch("samcli.local.docker.lambda_image.docker")
    def test_initialization_with_defaults(self, docker_patch):
        docker_client_mock = Mock()
        docker_patch.from_env.return_value = docker_client_mock

        lambda_image = LambdaImage("layer_downloader", False, False)

        self.assertEqual(lambda_image.layer_downloader, "layer_downloader")
        self.assertFalse(lambda_image.skip_pull_image)
        self.assertFalse(lambda_image.force_image_build)
        self.assertEqual(lambda_image.docker_client, docker_client_mock)

    def test_building_image_with_no_runtime_only_image(self):
        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        setattr(layer_downloader_mock, "layer_cache", self.layer_cache_dir)
        docker_client_mock.api.build.return_value = ["mock"]

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        self.assertEqual(
            lambda_image.build(None, IMAGE, "mylambdaimage:v1", [], False),
            f"mylambdaimage:rapid-{version}",
        )

    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    @patch("samcli.local.docker.lambda_image.LambdaImage._generate_docker_image_version")
    def test_building_image_with_no_runtime_only_image_always_build(
        self, generate_docker_image_version_patch, build_image_patch
    ):
        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        setattr(layer_downloader_mock, "layer_cache", self.layer_cache_dir)
        docker_client_mock.api.build.return_value = ["mock"]
        generate_docker_image_version_patch.return_value = "image-version"

        docker_client_mock = Mock()
        docker_client_mock.images.get.return_value = Mock()

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        self.assertEqual(
            lambda_image.build(None, IMAGE, "mylambdaimage:v1", ["mylayer"], False),
            f"mylambdaimage:rapid-{version}",
        )

        # No layers are added, because runtime is not defined.
        build_image_patch.assert_called_once_with(
            "mylambdaimage:v1", f"mylambdaimage:rapid-{version}", [], False, stream=ANY
        )
        # No Layers are added.
        layer_downloader_mock.assert_not_called()

    def test_building_image_with_non_accpeted_package_type(self):
        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        setattr(layer_downloader_mock, "layer_cache", self.layer_cache_dir)
        docker_client_mock.api.build.return_value = ["mock"]

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)
        with self.assertRaises(InvalidIntermediateImageError):
            lambda_image.build("python3.6", "Non-accepted-packagetype", None, [], False)
        with self.assertRaises(InvalidIntermediateImageError):
            lambda_image.build("python3.6", None, None, [], False)

    def test_building_image_with_no_layers(self):
        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        setattr(layer_downloader_mock, "layer_cache", self.layer_cache_dir)
        docker_client_mock.api.build.return_value = ["mock"]

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        self.assertEqual(
            lambda_image.build("python3.6", ZIP, None, [], False),
            f"amazon/aws-sam-cli-emulation-image-python3.6:rapid-{version}",
        )

    def test_building_image_with_go_debug(self):
        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        setattr(layer_downloader_mock, "layer_cache", self.layer_cache_dir)
        docker_client_mock.api.build.return_value = ["mock"]
        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        self.assertEqual(
            lambda_image.build("go1.x", ZIP, None, [], True),
            f"amazon/aws-sam-cli-emulation-image-go1.x:debug-{version}",
        )

    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    @patch("samcli.local.docker.lambda_image.LambdaImage._generate_docker_image_version")
    def test_not_building_image_that_already_exists(self, generate_docker_image_version_patch, build_image_patch):
        layer_downloader_mock = Mock()
        layer_mock = Mock()
        layer_mock.name = "layers1"
        layer_mock.is_defined_within_template = False
        layer_downloader_mock.download_all.return_value = [layer_mock]

        generate_docker_image_version_patch.return_value = "image-version"

        docker_client_mock = Mock()
        docker_client_mock.images.get.return_value = Mock()

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)
        actual_image_id = lambda_image.build("python3.6", ZIP, None, [layer_mock], False)

        self.assertEqual(actual_image_id, "samcli/lambda:image-version")

        layer_downloader_mock.download_all.assert_called_once_with([layer_mock], False)
        generate_docker_image_version_patch.assert_called_once_with([layer_mock], "python3.6")
        docker_client_mock.images.get.assert_called_once_with("samcli/lambda:image-version")
        build_image_patch.assert_not_called()

    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    @patch("samcli.local.docker.lambda_image.LambdaImage._generate_docker_image_version")
    def test_force_building_image_that_doesnt_already_exists(
        self, generate_docker_image_version_patch, build_image_patch
    ):
        layer_downloader_mock = Mock()
        layer_downloader_mock.download_all.return_value = ["layers1"]

        generate_docker_image_version_patch.return_value = "image-version"

        docker_client_mock = Mock()
        docker_client_mock.images.get.side_effect = ImageNotFound("image not found")

        stream = io.StringIO()

        lambda_image = LambdaImage(layer_downloader_mock, False, True, docker_client=docker_client_mock)
        actual_image_id = lambda_image.build("python3.6", ZIP, None, ["layers1"], False, stream=stream)

        self.assertEqual(actual_image_id, "samcli/lambda:image-version")

        layer_downloader_mock.download_all.assert_called_once_with(["layers1"], True)
        generate_docker_image_version_patch.assert_called_once_with(["layers1"], "python3.6")
        docker_client_mock.images.get.assert_called_once_with("samcli/lambda:image-version")
        build_image_patch.assert_called_once_with(
            "amazon/aws-sam-cli-emulation-image-python3.6:latest",
            "samcli/lambda:image-version",
            ["layers1"],
            False,
            stream=stream,
        )

    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    @patch("samcli.local.docker.lambda_image.LambdaImage._generate_docker_image_version")
    def test_not_force_building_image_that_doesnt_already_exists(
        self, generate_docker_image_version_patch, build_image_patch
    ):
        layer_downloader_mock = Mock()
        layer_downloader_mock.download_all.return_value = ["layers1"]

        generate_docker_image_version_patch.return_value = "image-version"

        docker_client_mock = Mock()
        docker_client_mock.images.get.side_effect = ImageNotFound("image not found")

        stream = io.StringIO()

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)
        actual_image_id = lambda_image.build("python3.6", ZIP, None, ["layers1"], False, stream=stream)

        self.assertEqual(actual_image_id, "samcli/lambda:image-version")

        layer_downloader_mock.download_all.assert_called_once_with(["layers1"], False)
        generate_docker_image_version_patch.assert_called_once_with(["layers1"], "python3.6")
        docker_client_mock.images.get.assert_called_once_with("samcli/lambda:image-version")
        build_image_patch.assert_called_once_with(
            "amazon/aws-sam-cli-emulation-image-python3.6:latest",
            "samcli/lambda:image-version",
            ["layers1"],
            False,
            stream=stream,
        )

    @patch("samcli.local.docker.lambda_image.hashlib")
    def test_generate_docker_image_version(self, hashlib_patch):
        haslib_sha256_mock = Mock()
        hashlib_patch.sha256.return_value = haslib_sha256_mock
        haslib_sha256_mock.hexdigest.return_value = "thisisahexdigestofshahash"

        layer_mock = Mock()
        layer_mock.name = "layer1"

        image_version = LambdaImage._generate_docker_image_version([layer_mock], "runtime")

        self.assertEqual(image_version, "runtime-thisisahexdigestofshahash")

        hashlib_patch.sha256.assert_called_once_with(b"layer1")

    @patch("samcli.local.docker.lambda_image.docker")
    def test_generate_dockerfile(self, docker_patch):
        docker_client_mock = Mock()
        docker_patch.from_env.return_value = docker_client_mock

        expected_docker_file = (
            "FROM python\nADD aws-lambda-rie /var/rapid\nRUN chmod +x /var/rapid/aws-lambda-rie\nADD layer1 /opt\n"
        )

        layer_mock = Mock()
        layer_mock.name = "layer1"

        self.assertEqual(LambdaImage._generate_dockerfile("python", [layer_mock], False), expected_docker_file)

    @patch("samcli.local.docker.lambda_image.docker")
    def test_generate_dockerfile_with_go_debug(self, docker_patch):
        docker_client_mock = Mock()
        docker_patch.from_env.return_value = docker_client_mock

        expected_docker_file = "FROM python\nADD aws-lambda-rie /var/rapid\nRUN chmod +x /var/rapid/aws-lambda-rie\nADD aws-lambda-go /var/runtime\nRUN chmod +x /var/runtime/aws-lambda-go\nADD layer1 /opt\n"

        layer_mock = Mock()
        layer_mock.name = "layer1"

        self.assertEqual(LambdaImage._generate_dockerfile("python", [layer_mock], True), expected_docker_file)

    @patch("samcli.local.docker.lambda_image.create_tarball")
    @patch("samcli.local.docker.lambda_image.uuid")
    @patch("samcli.local.docker.lambda_image.Path")
    @patch("samcli.local.docker.lambda_image.LambdaImage._generate_dockerfile")
    def test_build_image(self, generate_dockerfile_patch, path_patch, uuid_patch, create_tarball_patch):
        uuid_patch.uuid4.return_value = "uuid"
        generate_dockerfile_patch.return_value = "Dockerfile content"

        docker_full_path_mock = Mock()
        docker_full_path_mock.exists.return_value = True
        path_patch.return_value = docker_full_path_mock

        docker_client_mock = Mock()
        docker_client_mock.api.build.return_value = ["Done"]
        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = "cached layers"

        tarball_fileobj = Mock()
        create_tarball_patch.return_value.__enter__.return_value = tarball_fileobj

        layer_version1 = Mock()
        layer_version1.codeuri = "somevalue"
        layer_version1.name = "name"

        dockerfile_mock = Mock()
        m = mock_open(dockerfile_mock)
        with patch("samcli.local.docker.lambda_image.open", m):
            LambdaImage(layer_downloader_mock, True, False, docker_client=docker_client_mock)._build_image(
                "base_image", "docker_tag", [layer_version1], True
            )

        handle = m()
        handle.write.assert_called_with("Dockerfile content")
        path_patch.assert_called_once_with("cached layers", "dockerfile_uuid")
        docker_client_mock.api.build.assert_called_once_with(
            fileobj=tarball_fileobj, rm=True, tag="docker_tag", pull=False, custom_context=True
        )

        docker_full_path_mock.unlink.assert_called_once()

    @patch("samcli.local.docker.lambda_image.create_tarball")
    @patch("samcli.local.docker.lambda_image.uuid")
    @patch("samcli.local.docker.lambda_image.Path")
    @patch("samcli.local.docker.lambda_image.LambdaImage._generate_dockerfile")
    def test_build_image_fails_with_BuildError(
        self, generate_dockerfile_patch, path_patch, uuid_patch, create_tarball_patch
    ):
        uuid_patch.uuid4.return_value = "uuid"
        generate_dockerfile_patch.return_value = "Dockerfile content"

        docker_full_path_mock = Mock()
        docker_full_path_mock.exists.return_value = False
        path_patch.return_value = docker_full_path_mock

        docker_client_mock = Mock()
        docker_client_mock.api.build.side_effect = BuildError("buildError", "buildlog")
        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = "cached layers"

        tarball_fileobj = Mock()
        create_tarball_patch.return_value.__enter__.return_value = tarball_fileobj

        layer_version1 = Mock()
        layer_version1.codeuri = "somevalue"
        layer_version1.name = "name"

        dockerfile_mock = Mock()
        m = mock_open(dockerfile_mock)
        with patch("samcli.local.docker.lambda_image.open", m):
            with self.assertRaises(ImageBuildException):
                LambdaImage(layer_downloader_mock, True, False, docker_client=docker_client_mock)._build_image(
                    "base_image", "docker_tag", [layer_version1], True
                )

        handle = m()
        handle.write.assert_called_with("Dockerfile content")
        path_patch.assert_called_once_with("cached layers", "dockerfile_uuid")
        docker_client_mock.api.build.assert_called_once_with(
            fileobj=tarball_fileobj, rm=True, tag="docker_tag", pull=False, custom_context=True
        )

        docker_full_path_mock.unlink.assert_not_called()

    @patch("samcli.local.docker.lambda_image.create_tarball")
    @patch("samcli.local.docker.lambda_image.uuid")
    @patch("samcli.local.docker.lambda_image.Path")
    @patch("samcli.local.docker.lambda_image.LambdaImage._generate_dockerfile")
    def test_build_image_fails_with_ApiError(
        self, generate_dockerfile_patch, path_patch, uuid_patch, create_tarball_patch
    ):
        uuid_patch.uuid4.return_value = "uuid"
        generate_dockerfile_patch.return_value = "Dockerfile content"

        docker_full_path_mock = Mock()
        path_patch.return_value = docker_full_path_mock

        docker_client_mock = Mock()
        docker_client_mock.api.build.side_effect = APIError("apiError")
        layer_downloader_mock = Mock()
        layer_downloader_mock.layer_cache = "cached layers"

        tarball_fileobj = Mock()
        create_tarball_patch.return_value.__enter__.return_value = tarball_fileobj

        layer_version1 = Mock()
        layer_version1.codeuri = "somevalue"
        layer_version1.name = "name"

        dockerfile_mock = Mock()
        m = mock_open(dockerfile_mock)
        with patch("samcli.local.docker.lambda_image.open", m):
            with self.assertRaises(ImageBuildException):
                LambdaImage(layer_downloader_mock, True, False, docker_client=docker_client_mock)._build_image(
                    "base_image", "docker_tag", [layer_version1], True
                )

        handle = m()
        handle.write.assert_called_with("Dockerfile content")
        path_patch.assert_called_once_with("cached layers", "dockerfile_uuid")
        docker_client_mock.api.build.assert_called_once_with(
            fileobj=tarball_fileobj, rm=True, tag="docker_tag", pull=False, custom_context=True
        )
        docker_full_path_mock.unlink.assert_called_once()

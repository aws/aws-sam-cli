import io
import tempfile

from unittest import TestCase
from unittest.mock import patch, Mock, mock_open, ANY, call
from parameterized import parameterized

from docker.errors import ImageNotFound, BuildError, APIError
from parameterized import parameterized

from samcli.commands.local.lib.exceptions import InvalidIntermediateImageError
from samcli.lib.utils.packagetype import ZIP, IMAGE
from samcli.lib.utils.architecture import ARM64, X86_64
from samcli.local.docker.lambda_image import LambdaImage, RAPID_IMAGE_TAG_PREFIX, Runtime
from samcli.commands.local.cli_common.user_exceptions import ImageBuildException
from samcli import __version__ as version


class TestRuntime(TestCase):
    @parameterized.expand(
        [
            ("nodejs12.x", "nodejs:12-x86_64"),
            ("nodejs14.x", "nodejs:14-x86_64"),
            ("nodejs16.x", "nodejs:16-x86_64"),
            ("python2.7", "python:2.7"),
            ("python3.7", "python:3.7"),
            ("python3.8", "python:3.8-x86_64"),
            ("python3.9", "python:3.9-x86_64"),
            ("ruby2.7", "ruby:2.7-x86_64"),
            ("java8", "java:8"),
            ("java8.al2", "java:8.al2-x86_64"),
            ("java11", "java:11-x86_64"),
            ("go1.x", "go:1"),
            ("dotnet6", "dotnet:6-x86_64"),
            ("dotnetcore3.1", "dotnet:core3.1-x86_64"),
            ("provided", "provided:alami"),
            ("provided.al2", "provided:al2-x86_64"),
        ]
    )
    def test_image_name_tag(self, runtime, image_tag):
        self.assertEqual(Runtime.get_image_name_tag(runtime, "x86_64"), image_tag)


class TestLambdaImage(TestCase):
    def setUp(self):
        self.layer_cache_dir = tempfile.gettempdir()

    def test_initialization_without_defaults(self):
        lambda_image = LambdaImage("layer_downloader", False, False, docker_client="docker_client")

        self.assertEqual(lambda_image.layer_downloader, "layer_downloader")
        self.assertFalse(lambda_image.skip_pull_image)
        self.assertFalse(lambda_image.force_image_build)
        self.assertEqual(lambda_image.docker_client, "docker_client")
        self.assertIsNone(lambda_image.invoke_images)

    @patch("samcli.local.docker.lambda_image.docker")
    def test_initialization_with_defaults(self, docker_patch):
        docker_client_mock = Mock()
        docker_patch.from_env.return_value = docker_client_mock

        lambda_image = LambdaImage("layer_downloader", False, False)

        self.assertEqual(lambda_image.layer_downloader, "layer_downloader")
        self.assertFalse(lambda_image.skip_pull_image)
        self.assertFalse(lambda_image.force_image_build)
        self.assertEqual(lambda_image.docker_client, docker_client_mock)
        self.assertIsNone(lambda_image.invoke_images)

    def test_building_image_with_no_runtime_only_image(self):
        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        setattr(layer_downloader_mock, "layer_cache", self.layer_cache_dir)
        docker_client_mock.api.build.return_value = ["mock"]
        docker_client_mock.images.list.return_value = []

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        self.assertEqual(
            lambda_image.build(None, IMAGE, "mylambdaimage:v1", [], X86_64),
            f"mylambdaimage:{RAPID_IMAGE_TAG_PREFIX}-{X86_64}",
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
        docker_client_mock.images.list.return_value = []

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        self.assertEqual(
            lambda_image.build(None, IMAGE, "mylambdaimage:v1", ["mylayer"], X86_64, function_name="function"),
            f"mylambdaimage:{RAPID_IMAGE_TAG_PREFIX}-x86_64",
        )

        # No layers are added, because runtime is not defined.
        build_image_patch.assert_called_once_with(
            "mylambdaimage:v1",
            f"mylambdaimage:{RAPID_IMAGE_TAG_PREFIX}-x86_64",
            [],
            X86_64,
            stream=ANY,
        )
        # No Layers are added.
        layer_downloader_mock.assert_not_called()

    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    @patch("samcli.local.docker.lambda_image.LambdaImage._generate_docker_image_version")
    def test_building_image_with_different_architecture_are_not_the_same(
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
        image_1 = lambda_image.build(
            "dummy_runtime", IMAGE, "mylambdaimage:v1", ["mylayer"], X86_64, function_name="function"
        )
        image_2 = lambda_image.build(
            "dummy_runtime", IMAGE, "mylambdaimage:v1", ["mylayer"], ARM64, function_name="function"
        )
        self.assertNotEqual(image_1, image_2)

    def test_building_image_with_non_accepted_package_type(self):
        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        setattr(layer_downloader_mock, "layer_cache", self.layer_cache_dir)
        docker_client_mock.api.build.return_value = ["mock"]

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)
        with self.assertRaises(InvalidIntermediateImageError):
            lambda_image.build("python3.9", "Non-accepted-packagetype", None, [], X86_64, function_name="function")
        with self.assertRaises(InvalidIntermediateImageError):
            lambda_image.build("python3.9", None, None, [], X86_64, function_name="function")

    @patch("samcli.local.docker.lambda_image.LambdaImage.is_base_image_current")
    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    def test_building_image_with_no_layers(self, build_image_patch, is_base_image_current_patch):
        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        stream = Mock()
        docker_client_mock.api.build.return_value = ["mock"]

        is_base_image_current_patch.return_value = False

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        self.assertEqual(
            lambda_image.build("python3.7", ZIP, None, [], ARM64, stream=stream),
            f"public.ecr.aws/lambda/python:3.7-{RAPID_IMAGE_TAG_PREFIX}-arm64",
        )

        build_image_patch.assert_called_once_with(
            "public.ecr.aws/lambda/python:3.7",
            f"public.ecr.aws/lambda/python:3.7-{RAPID_IMAGE_TAG_PREFIX}-arm64",
            [],
            ARM64,
            stream=stream,
        )

    @patch("samcli.local.docker.lambda_image.LambdaImage.is_base_image_current")
    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    def test_not_building_image_with_no_layers_if_up_to_date(self, build_image_patch, is_base_image_current_patch):
        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        setattr(layer_downloader_mock, "layer_cache", self.layer_cache_dir)
        docker_client_mock.api.build.return_value = ["mock"]

        is_base_image_current_patch.return_value = True

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        self.assertEqual(
            lambda_image.build("python3.9", ZIP, None, [], ARM64, function_name="function"),
            f"public.ecr.aws/lambda/python:3.9-{RAPID_IMAGE_TAG_PREFIX}-{ARM64}",
        )

    @patch("samcli.local.docker.lambda_image.LambdaImage.is_base_image_current")
    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    def test_building_image_with_custom_image_uri(self, build_image_patch, is_base_image_current_patch):
        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        setattr(layer_downloader_mock, "layer_cache", self.layer_cache_dir)
        docker_client_mock.api.build.return_value = ["mock"]
        is_base_image_current_patch.return_value = True

        lambda_image = LambdaImage(
            layer_downloader_mock,
            False,
            False,
            docker_client=docker_client_mock,
            invoke_images={
                None: "amazon/aws-sam-cli-emulation-image-python3.9",
                "Function1": "amazon/aws-sam-cli-emulation-image2-python3.9",
            },
        )
        self.assertEqual(
            lambda_image.build("python3.9", ZIP, None, [], X86_64, function_name="Function1"),
            f"amazon/aws-sam-cli-emulation-image2-python3.9:{RAPID_IMAGE_TAG_PREFIX}-x86_64",
        )
        self.assertEqual(
            lambda_image.build("python3.9", ZIP, None, [], X86_64, function_name="Function2"),
            f"amazon/aws-sam-cli-emulation-image-python3.9:{RAPID_IMAGE_TAG_PREFIX}-x86_64",
        )
        build_image_patch.assert_not_called()

    @patch("samcli.local.docker.lambda_image.LambdaImage.is_base_image_current")
    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    @patch("samcli.local.docker.lambda_image.LambdaImage._generate_docker_image_version")
    def test_not_building_image_that_is_up_to_date(
        self, generate_docker_image_version_patch, build_image_patch, is_base_image_current_patch
    ):
        layer_downloader_mock = Mock()
        layer_mock = Mock()
        layer_mock.name = "layers1"
        layer_mock.is_defined_within_template = False
        layer_downloader_mock.download_all.return_value = [layer_mock]

        generate_docker_image_version_patch.return_value = "runtime:image-version"
        is_base_image_current_patch.return_value = True

        docker_client_mock = Mock()
        docker_client_mock.images.get.return_value = Mock()

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)
        actual_image_id = lambda_image.build("python3.7", ZIP, None, [layer_mock], X86_64, function_name="function")

        self.assertEqual(actual_image_id, "samcli/lambda-runtime:image-version")

        layer_downloader_mock.download_all.assert_called_once_with([layer_mock], False)
        generate_docker_image_version_patch.assert_called_once_with([layer_mock], "python:3.7")
        docker_client_mock.images.get.assert_called_once_with("samcli/lambda-runtime:image-version")
        build_image_patch.assert_not_called()

    @parameterized.expand(
        [
            ("python3.7", "python:3.7", "public.ecr.aws/lambda/python:3.7"),
            ("python3.8", "python:3.8-x86_64", "public.ecr.aws/lambda/python:3.8-x86_64"),
        ]
    )
    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    @patch("samcli.local.docker.lambda_image.LambdaImage._generate_docker_image_version")
    def test_force_building_image_that_doesnt_already_exists(
        self, runtime, image_suffix, image_name, generate_docker_image_version_patch, build_image_patch
    ):
        layer_downloader_mock = Mock()
        layer_downloader_mock.download_all.return_value = ["layers1"]

        generate_docker_image_version_patch.return_value = "runtime:image-version"

        docker_client_mock = Mock()
        docker_client_mock.images.get.side_effect = ImageNotFound("image not found")
        docker_client_mock.images.list.return_value = []

        stream = io.StringIO()

        lambda_image = LambdaImage(layer_downloader_mock, False, True, docker_client=docker_client_mock)
        actual_image_id = lambda_image.build(
            runtime, ZIP, None, ["layers1"], X86_64, stream=stream, function_name="function"
        )

        self.assertEqual(actual_image_id, "samcli/lambda-runtime:image-version")

        layer_downloader_mock.download_all.assert_called_once_with(["layers1"], True)
        generate_docker_image_version_patch.assert_called_once_with(["layers1"], f"{image_suffix}")
        docker_client_mock.images.get.assert_called_once_with("samcli/lambda-runtime:image-version")
        build_image_patch.assert_called_once_with(
            image_name,
            "samcli/lambda-runtime:image-version",
            ["layers1"],
            X86_64,
            stream=stream,
        )

    @parameterized.expand(
        [
            ("python3.7", "python:3.7", "public.ecr.aws/lambda/python:3.7"),
            ("python3.8", "python:3.8-arm64", "public.ecr.aws/lambda/python:3.8-arm64"),
        ]
    )
    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    @patch("samcli.local.docker.lambda_image.LambdaImage._generate_docker_image_version")
    def test_not_force_building_image_that_doesnt_already_exists(
        self, runtime, image_suffix, image_name, generate_docker_image_version_patch, build_image_patch
    ):
        layer_downloader_mock = Mock()
        layer_downloader_mock.download_all.return_value = ["layers1"]

        generate_docker_image_version_patch.return_value = "runtime:image-version"

        docker_client_mock = Mock()
        docker_client_mock.images.get.side_effect = ImageNotFound("image not found")
        docker_client_mock.images.list.return_value = []

        stream = io.StringIO()

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)
        actual_image_id = lambda_image.build(
            runtime, ZIP, None, ["layers1"], ARM64, stream=stream, function_name="function"
        )

        self.assertEqual(actual_image_id, "samcli/lambda-runtime:image-version")

        layer_downloader_mock.download_all.assert_called_once_with(["layers1"], False)
        generate_docker_image_version_patch.assert_called_once_with(["layers1"], f"{image_suffix}")
        docker_client_mock.images.get.assert_called_once_with("samcli/lambda-runtime:image-version")
        build_image_patch.assert_called_once_with(
            image_name,
            "samcli/lambda-runtime:image-version",
            ["layers1"],
            ARM64,
            stream=stream,
        )

    @patch("samcli.local.docker.lambda_image.hashlib")
    def test_generate_docker_image_version(self, hashlib_patch):
        haslib_sha256_mock = Mock()
        hashlib_patch.sha256.return_value = haslib_sha256_mock
        haslib_sha256_mock.hexdigest.return_value = "thisisahexdigestofshahash"

        layer_mock = Mock()
        layer_mock.name = "layer1"

        image_version = LambdaImage._generate_docker_image_version([layer_mock], "runtime:1-arm64")

        self.assertEqual(image_version, "runtime:1-arm64-thisisahexdigestofshahash")

        hashlib_patch.sha256.assert_called_once_with(b"layer1")

    @patch("samcli.local.docker.lambda_image.docker")
    def test_generate_dockerfile(self, docker_patch):
        docker_client_mock = Mock()
        docker_patch.from_env.return_value = docker_client_mock

        expected_docker_file = "FROM python\nADD aws-lambda-rie-x86_64 /var/rapid/\nRUN mv /var/rapid/aws-lambda-rie-x86_64 /var/rapid/aws-lambda-rie && chmod +x /var/rapid/aws-lambda-rie\nADD layer1 /opt\n"

        layer_mock = Mock()
        layer_mock.name = "layer1"

        self.assertEqual(LambdaImage._generate_dockerfile("python", [layer_mock], X86_64), expected_docker_file)

    @patch("samcli.local.docker.lambda_image.docker")
    def test_generate_dockerfile_with_arm64(self, docker_patch):
        docker_client_mock = Mock()
        docker_patch.from_env.return_value = docker_client_mock

        expected_docker_file = "FROM python\nADD aws-lambda-rie-arm64 /var/rapid/\nRUN mv /var/rapid/aws-lambda-rie-arm64 /var/rapid/aws-lambda-rie && chmod +x /var/rapid/aws-lambda-rie\nADD layer1 /opt\n"

        layer_mock = Mock()
        layer_mock.name = "layer1"

        self.assertEqual(LambdaImage._generate_dockerfile("python", [layer_mock], ARM64), expected_docker_file)

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
                "base_image", "docker_tag", [layer_version1], "arm64"
            )

        handle = m()
        handle.write.assert_called_with("Dockerfile content")
        path_patch.assert_called_once_with("cached layers", "dockerfile_uuid")
        docker_client_mock.api.build.assert_called_once_with(
            fileobj=tarball_fileobj,
            rm=True,
            tag="docker_tag",
            pull=False,
            custom_context=True,
            decode=True,
            platform="linux/arm64",
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
                    "base_image", "docker_tag", [layer_version1], ARM64
                )

        handle = m()
        handle.write.assert_called_with("Dockerfile content")
        path_patch.assert_called_once_with("cached layers", "dockerfile_uuid")
        docker_client_mock.api.build.assert_called_once_with(
            fileobj=tarball_fileobj,
            rm=True,
            tag="docker_tag",
            pull=False,
            custom_context=True,
            decode=True,
            platform="linux/arm64",
        )

        docker_full_path_mock.unlink.assert_not_called()

    @patch("samcli.local.docker.lambda_image.create_tarball")
    @patch("samcli.local.docker.lambda_image.uuid")
    @patch("samcli.local.docker.lambda_image.Path")
    @patch("samcli.local.docker.lambda_image.LambdaImage._generate_dockerfile")
    def test_build_image_fails_with_BuildError_from_output(
        self, generate_dockerfile_patch, path_patch, uuid_patch, create_tarball_patch
    ):
        uuid_patch.uuid4.return_value = "uuid"
        generate_dockerfile_patch.return_value = "Dockerfile content"

        docker_full_path_mock = Mock()
        docker_full_path_mock.exists.return_value = False
        path_patch.return_value = docker_full_path_mock

        docker_client_mock = Mock()
        docker_client_mock.api.build.return_value = [{"stream": "Some text"}, {"error": "Problem in the build!"}]
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
            with self.assertRaisesRegex(ImageBuildException, "Problem in the build!"):
                LambdaImage(layer_downloader_mock, True, False, docker_client=docker_client_mock)._build_image(
                    "base_image", "docker_tag", [layer_version1], X86_64
                )

        handle = m()
        handle.write.assert_called_with("Dockerfile content")
        path_patch.assert_called_once_with("cached layers", "dockerfile_uuid")
        docker_client_mock.api.build.assert_called_once_with(
            fileobj=tarball_fileobj,
            rm=True,
            tag="docker_tag",
            pull=False,
            custom_context=True,
            decode=True,
            platform="linux/amd64",
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
                    "base_image", "docker_tag", [layer_version1], X86_64
                )

        handle = m()
        handle.write.assert_called_with("Dockerfile content")
        path_patch.assert_called_once_with("cached layers", "dockerfile_uuid")
        docker_client_mock.api.build.assert_called_once_with(
            fileobj=tarball_fileobj,
            rm=True,
            tag="docker_tag",
            pull=False,
            custom_context=True,
            decode=True,
            platform="linux/amd64",
        )
        docker_full_path_mock.unlink.assert_called_once()

    def test_building_new_rapid_image_removes_old_rapid_images(self):
        old_repo = "public.ecr.aws/sam/emulation-python3.8"
        repo = "public.ecr.aws/lambda/python:3.8"
        docker_client_mock = Mock()
        docker_client_mock.api.build.return_value = ["mock"]
        docker_client_mock.images.get.side_effect = ImageNotFound("image not found")
        docker_client_mock.images.list.return_value = [
            Mock(id="old1", tags=[f"{old_repo}:{RAPID_IMAGE_TAG_PREFIX}-0.00.01"]),
            Mock(id="old2", tags=[f"{old_repo}:{RAPID_IMAGE_TAG_PREFIX}-0.00.02-arm64"]),
            Mock(id="old3", tags=[f"{old_repo}:{RAPID_IMAGE_TAG_PREFIX}-0.00.03-arm64"]),
            Mock(
                id="old4",
                tags=[f"{old_repo}:{RAPID_IMAGE_TAG_PREFIX}-0.00.04-arm64"],
            ),
        ]

        layer_downloader_mock = Mock()
        setattr(layer_downloader_mock, "layer_cache", self.layer_cache_dir)

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        self.assertEqual(
            lambda_image.build("python3.8", ZIP, None, [], X86_64, function_name="function"),
            f"{repo}-{RAPID_IMAGE_TAG_PREFIX}-x86_64",
        )

        docker_client_mock.images.remove.assert_has_calls(
            [
                call("old1"),
                call("old2"),
                call("old3"),
                call("old4"),
            ]
        )

    def test_building_new_rapid_image_removes_old_rapid_images_for_image_function(self):
        image_name = "custom_image_name"
        docker_client_mock = Mock()
        docker_client_mock.api.build.return_value = ["mock"]
        docker_client_mock.images.get.side_effect = ImageNotFound("image not found")
        docker_client_mock.images.list.return_value = [
            Mock(id="old1", tags=[f"{image_name}:{RAPID_IMAGE_TAG_PREFIX}-0.00.01"]),
            Mock(id="old2", tags=[f"{image_name}:{RAPID_IMAGE_TAG_PREFIX}-0.00.02-x86_64"]),
            Mock(id="old3", tags=[f"{image_name}:{RAPID_IMAGE_TAG_PREFIX}-{version}-x86_64"]),
        ]

        layer_downloader_mock = Mock()
        setattr(layer_downloader_mock, "layer_cache", self.layer_cache_dir)

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        self.assertEqual(
            lambda_image.build(None, IMAGE, f"{image_name}:image-tag", [], X86_64),
            f"{image_name}:{RAPID_IMAGE_TAG_PREFIX}-x86_64",
        )

        docker_client_mock.images.list.assert_called_once()
        docker_client_mock.images.remove.assert_has_calls(
            [
                call("old1"),
                call("old2"),
                call("old3"),
            ]
        )

    def test_building_existing_rapid_image_does_not_remove_old_rapid_images(self):
        old_repo = "public.ecr.aws/sam/emulation-python3.8"
        repo = "public.ecr.aws/lambda/python:3.8"
        docker_client_mock = Mock()
        docker_client_mock.api.build.return_value = ["mock"]
        docker_client_mock.images.list.return_value = [
            Mock(id="old1", tags=[f"{old_repo}:{RAPID_IMAGE_TAG_PREFIX}-0.00.01-x86_64"]),
            Mock(id="old1", tags=[f"{old_repo}:{RAPID_IMAGE_TAG_PREFIX}-0.00.02-arm64"]),
        ]

        layer_downloader_mock = Mock()
        setattr(layer_downloader_mock, "layer_cache", self.layer_cache_dir)

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)
        lambda_image.is_base_image_current = Mock(return_value=True)

        self.assertEqual(
            lambda_image.build("python3.8", ZIP, None, [], X86_64, function_name="function"),
            f"{repo}-{RAPID_IMAGE_TAG_PREFIX}-x86_64",
        )

        docker_client_mock.images.remove.assert_not_called()

    @parameterized.expand(
        [
            (None, False),
            ("", False),
            ("my_repo", False),
            ("my_repo:tag", False),
            ("my_repo:rapid-1.29beta", True),
            ("public.ecr.aws/lambda/python:3.9", False),
            ("public.ecr.aws/sam/emulation-python3.9:latest", False),
            ("public.ecr.aws/sam/emulation-python3.9:rapid", False),
            ("public.ecr.aws/sam/emulation-python3.9:rapid-1.29.0", True),
            ("public.ecr.aws/lambda/python:3.9-rapid-arm64", True),
            ("public.ecr.aws/lambda/python:3.8.v1-rapid-x86_64", True),
            ("public.ecr.aws/lambda/java:11-rapid-x86_64", True),
            ("public.ecr.aws/lambda/python:3.8", False),
            ("public.ecr.aws/lambda/latest", False),
        ]
    )
    def test_is_rapid_image(self, image_name, is_rapid):
        self.assertEqual(LambdaImage.is_rapid_image(image_name), is_rapid)

    @parameterized.expand(
        [
            (f"my_repo:rapid-{version}", False),
            (f"my_repo:rapid-{version}beta", False),
            (f"my_repo:rapid-{version}-x86_64", False),
            (f"public.ecr.aws/sam/emulation-python3.7:{RAPID_IMAGE_TAG_PREFIX}", False),
            (f"public.ecr.aws/lambda/python:3.9-{RAPID_IMAGE_TAG_PREFIX}-x86_64", True),
            ("my_repo:rapid-1.230.0", False),
            ("my_repo:rapid-1.204.0beta", False),
            ("my_repo:rapid-0.00.02-x86_64", False),
            (f"public.ecr.aws/sam/emulation-python3.7:{RAPID_IMAGE_TAG_PREFIX}-0.01.01.01", False),
        ]
    )
    def test_is_rapid_image_current(self, image_name, is_current):
        self.assertEqual(LambdaImage.is_rapid_image_current(image_name), is_current)

    def test_get_remote_image_digest(self):
        docker_client_mock = Mock()
        registry_data = Mock(
            attrs={
                "Descriptor": {"digest": "sha256:remote-digest"},
            },
        )
        docker_client_mock.images.get_registry_data.return_value = registry_data
        lambda_image = LambdaImage("layer_downloader", False, False, docker_client=docker_client_mock)
        self.assertEqual("sha256:remote-digest", lambda_image.get_remote_image_digest("image_name"))

    def test_get_local_image_digest(self):
        docker_client_mock = Mock()
        local_image_data = Mock(
            attrs={
                "RepoDigests": ["image_name@sha256:local-digest"],
            },
        )
        docker_client_mock.images.get.return_value = local_image_data
        lambda_image = LambdaImage("layer_downloader", False, False, docker_client=docker_client_mock)
        self.assertEqual("sha256:local-digest", lambda_image.get_local_image_digest("image_name"))

    @parameterized.expand(
        [
            ("same-digest", "same-digest", True),
            ("one-digest", "another-digest", False),
        ]
    )
    def test_is_base_image_current(self, local_digest, remote_digest, expected_image_current):
        lambda_image = LambdaImage("layer_downloader", False, False, docker_client=Mock())
        lambda_image.get_local_image_digest = Mock(return_value=local_digest)
        lambda_image.get_remote_image_digest = Mock(return_value=remote_digest)
        self.assertEqual(lambda_image.is_base_image_current("image_name"), expected_image_current)

    @parameterized.expand(
        [
            (True, True, False),  # It's up-to-date => skip_pull_image: True
            (False, False, True),  # It needs to be updated => force_image_build: True
        ]
    )
    def test_check_base_image_is_current(
        self,
        is_base_image_current,
        expected_skip_pull_image,
        expected_force_image_build,
    ):
        lambda_image = LambdaImage("layer_downloader", False, False, docker_client=Mock())
        lambda_image.is_base_image_current = Mock(return_value=is_base_image_current)
        lambda_image._check_base_image_is_current("image_name")
        self.assertEqual(lambda_image.skip_pull_image, expected_skip_pull_image)
        self.assertEqual(lambda_image.force_image_build, expected_force_image_build)

import io
import tempfile

from unittest import TestCase
from unittest.mock import patch, Mock, mock_open, ANY, call

from docker.errors import ImageNotFound, BuildError, APIError
from parameterized import parameterized

from samcli.commands.local.lib.exceptions import InvalidIntermediateImageError
from samcli.lib.utils.packagetype import ZIP, IMAGE
from samcli.lib.utils.architecture import ARM64, X86_64
from samcli.local.docker.lambda_image import LambdaImage, RAPID_IMAGE_TAG_PREFIX
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
            f"mylambdaimage:{RAPID_IMAGE_TAG_PREFIX}-{version}-x86_64",
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
            f"mylambdaimage:{RAPID_IMAGE_TAG_PREFIX}-{version}-x86_64",
        )

        # No layers are added, because runtime is not defined.
        build_image_patch.assert_called_once_with(
            "mylambdaimage:v1",
            f"mylambdaimage:{RAPID_IMAGE_TAG_PREFIX}-{version}-x86_64",
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
            lambda_image.build("python3.6", "Non-accepted-packagetype", None, [], X86_64, function_name="function")
        with self.assertRaises(InvalidIntermediateImageError):
            lambda_image.build("python3.6", None, None, [], X86_64, function_name="function")

    def test_building_image_with_no_layers(self):
        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        setattr(layer_downloader_mock, "layer_cache", self.layer_cache_dir)
        docker_client_mock.api.build.return_value = ["mock"]

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        self.assertEqual(
            lambda_image.build("python3.6", ZIP, None, [], ARM64, function_name="function"),
            f"public.ecr.aws/sam/emulation-python3.6:{RAPID_IMAGE_TAG_PREFIX}-{version}-arm64",
        )

    def test_building_image_with_custom_image_uri(self):
        docker_client_mock = Mock()
        layer_downloader_mock = Mock()
        setattr(layer_downloader_mock, "layer_cache", self.layer_cache_dir)
        docker_client_mock.api.build.return_value = ["mock"]

        lambda_image = LambdaImage(
            layer_downloader_mock,
            False,
            False,
            docker_client=docker_client_mock,
            invoke_images={
                None: "amazon/aws-sam-cli-emulation-image-python3.6",
                "Function1": "amazon/aws-sam-cli-emulation-image2-python3.6",
            },
        )
        self.assertEqual(
            lambda_image.build("python3.6", ZIP, None, [], X86_64, function_name="Function1"),
            f"amazon/aws-sam-cli-emulation-image2-python3.6:{RAPID_IMAGE_TAG_PREFIX}-{version}-x86_64",
        )
        self.assertEqual(
            lambda_image.build("python3.6", ZIP, None, [], X86_64, function_name="Function2"),
            f"amazon/aws-sam-cli-emulation-image-python3.6:{RAPID_IMAGE_TAG_PREFIX}-{version}-x86_64",
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
        actual_image_id = lambda_image.build("python3.6", ZIP, None, [layer_mock], X86_64, function_name="function")

        self.assertEqual(actual_image_id, "samcli/lambda:image-version")

        layer_downloader_mock.download_all.assert_called_once_with([layer_mock], False)
        generate_docker_image_version_patch.assert_called_once_with([layer_mock], "python3.6", X86_64)
        docker_client_mock.images.get.assert_called_once_with("samcli/lambda:image-version")
        build_image_patch.assert_not_called()

    @parameterized.expand(
        [
            ("python3.6", "public.ecr.aws/sam/emulation-python3.6:latest"),
            ("python3.8", "public.ecr.aws/sam/emulation-python3.8:latest-x86_64"),
        ]
    )
    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    @patch("samcli.local.docker.lambda_image.LambdaImage._generate_docker_image_version")
    def test_force_building_image_that_doesnt_already_exists(
        self, runtime, image_name, generate_docker_image_version_patch, build_image_patch
    ):
        layer_downloader_mock = Mock()
        layer_downloader_mock.download_all.return_value = ["layers1"]

        generate_docker_image_version_patch.return_value = "image-version"

        docker_client_mock = Mock()
        docker_client_mock.images.get.side_effect = ImageNotFound("image not found")
        docker_client_mock.images.list.return_value = []

        stream = io.StringIO()

        lambda_image = LambdaImage(layer_downloader_mock, False, True, docker_client=docker_client_mock)
        actual_image_id = lambda_image.build(
            runtime, ZIP, None, ["layers1"], X86_64, stream=stream, function_name="function"
        )

        self.assertEqual(actual_image_id, "samcli/lambda:image-version")

        layer_downloader_mock.download_all.assert_called_once_with(["layers1"], True)
        generate_docker_image_version_patch.assert_called_once_with(["layers1"], runtime, X86_64)
        docker_client_mock.images.get.assert_called_once_with("samcli/lambda:image-version")
        build_image_patch.assert_called_once_with(
            image_name,
            "samcli/lambda:image-version",
            ["layers1"],
            X86_64,
            stream=stream,
        )

    @parameterized.expand(
        [
            ("python3.6", "public.ecr.aws/sam/emulation-python3.6:latest"),
            ("python3.8", "public.ecr.aws/sam/emulation-python3.8:latest-arm64"),
        ]
    )
    @patch("samcli.local.docker.lambda_image.LambdaImage._build_image")
    @patch("samcli.local.docker.lambda_image.LambdaImage._generate_docker_image_version")
    def test_not_force_building_image_that_doesnt_already_exists(
        self, runtime, image_name, generate_docker_image_version_patch, build_image_patch
    ):
        layer_downloader_mock = Mock()
        layer_downloader_mock.download_all.return_value = ["layers1"]

        generate_docker_image_version_patch.return_value = "image-version"

        docker_client_mock = Mock()
        docker_client_mock.images.get.side_effect = ImageNotFound("image not found")
        docker_client_mock.images.list.return_value = []

        stream = io.StringIO()

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)
        actual_image_id = lambda_image.build(
            runtime, ZIP, None, ["layers1"], ARM64, stream=stream, function_name="function"
        )

        self.assertEqual(actual_image_id, "samcli/lambda:image-version")

        layer_downloader_mock.download_all.assert_called_once_with(["layers1"], False)
        generate_docker_image_version_patch.assert_called_once_with(["layers1"], runtime, ARM64)
        docker_client_mock.images.get.assert_called_once_with("samcli/lambda:image-version")
        build_image_patch.assert_called_once_with(
            image_name,
            "samcli/lambda:image-version",
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

        image_version = LambdaImage._generate_docker_image_version([layer_mock], "runtime", ARM64)

        self.assertEqual(image_version, "runtime-arm64-thisisahexdigestofshahash")

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
            with self.assertRaisesRegexp(ImageBuildException, "Problem in the build!"):
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
        repo = "public.ecr.aws/sam/emulation-python3.6"
        docker_client_mock = Mock()
        docker_client_mock.api.build.return_value = ["mock"]
        docker_client_mock.images.get.side_effect = ImageNotFound("image not found")
        docker_client_mock.images.list.return_value = [
            Mock(id="old1", tags=[f"{repo}:{RAPID_IMAGE_TAG_PREFIX}-0.00.01-x86_64"]),
            Mock(id="old2", tags=[f"{repo}:{RAPID_IMAGE_TAG_PREFIX}-0.00.02-arm64"]),
            Mock(id="old3", tags=[f"{repo}:{RAPID_IMAGE_TAG_PREFIX}-{version}-arm64"]),
            Mock(id="old4", tags=[f"{repo}:{RAPID_IMAGE_TAG_PREFIX}-{version}"]),
            Mock(id="old5", tags=[f"{repo}:{RAPID_IMAGE_TAG_PREFIX}-0.00.05-arm64"]),
        ]

        layer_downloader_mock = Mock()
        setattr(layer_downloader_mock, "layer_cache", self.layer_cache_dir)

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        self.assertEqual(
            lambda_image.build("python3.6", ZIP, None, [], X86_64, function_name="function"),
            f"{repo}:{RAPID_IMAGE_TAG_PREFIX}-{version}-x86_64",
        )

        docker_client_mock.images.remove.assert_has_calls(
            [
                call("old1"),
                call("old2"),
                call("old5"),
            ]
        )

    def test_building_existing_rapid_image_does_not_remove_old_rapid_images(self):
        repo = "public.ecr.aws/sam/emulation-python3.6"
        docker_client_mock = Mock()
        docker_client_mock.api.build.return_value = ["mock"]
        docker_client_mock.images.list.return_value = [
            Mock(id="old1", tags=[f"{repo}:{RAPID_IMAGE_TAG_PREFIX}-0.00.01-x86_64"]),
            Mock(id="old2", tags=[f"{repo}:{RAPID_IMAGE_TAG_PREFIX}-0.00.02-arm64"]),
        ]

        layer_downloader_mock = Mock()
        setattr(layer_downloader_mock, "layer_cache", self.layer_cache_dir)

        lambda_image = LambdaImage(layer_downloader_mock, False, False, docker_client=docker_client_mock)

        self.assertEqual(
            lambda_image.build("python3.6", ZIP, None, [], X86_64, function_name="function"),
            f"{repo}:{RAPID_IMAGE_TAG_PREFIX}-{version}-x86_64",
        )

        docker_client_mock.images.remove.assert_not_called()

    def test_is_rapid_image(self):
        self.assertFalse(LambdaImage.is_rapid_image(None))
        self.assertFalse(LambdaImage.is_rapid_image(""))
        self.assertFalse(LambdaImage.is_rapid_image("my_repo"))
        self.assertFalse(LambdaImage.is_rapid_image("my_repo:tag"))
        self.assertFalse(LambdaImage.is_rapid_image("public.ecr.aws/lambda/python:3.9"))
        self.assertFalse(LambdaImage.is_rapid_image("public.ecr.aws/sam/emulation-python3.6:latest"))

        self.assertTrue(LambdaImage.is_rapid_image("my_repo:rapid-1.29.0"))
        self.assertTrue(LambdaImage.is_rapid_image("my_repo:rapid-1.29.0beta"))
        self.assertTrue(LambdaImage.is_rapid_image("my_repo:rapid-1.29.0-x86_64"))
        self.assertTrue(
            LambdaImage.is_rapid_image(f"public.ecr.aws/sam/emulation-python3.6:{RAPID_IMAGE_TAG_PREFIX}-1.23.0")
        )

    def test_is_image_current(self):
        self.assertTrue(LambdaImage.is_image_current(f"my_repo:rapid-{version}"))
        self.assertTrue(LambdaImage.is_image_current(f"my_repo:rapid-{version}beta"))
        self.assertTrue(LambdaImage.is_image_current(f"my_repo:rapid-{version}-x86_64"))
        self.assertTrue(
            LambdaImage.is_image_current(f"public.ecr.aws/sam/emulation-python3.6:{RAPID_IMAGE_TAG_PREFIX}-{version}")
        )
        self.assertFalse(LambdaImage.is_image_current("my_repo:rapid-1.230.0"))
        self.assertFalse(LambdaImage.is_image_current("my_repo:rapid-1.204.0beta"))
        self.assertFalse(LambdaImage.is_image_current("my_repo:rapid-0.00.02-x86_64"))
        self.assertFalse(
            LambdaImage.is_image_current(f"public.ecr.aws/sam/emulation-python3.6:{RAPID_IMAGE_TAG_PREFIX}-0.01.01.01")
        )

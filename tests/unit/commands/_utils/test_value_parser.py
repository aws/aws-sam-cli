from unittest import TestCase
from samcli.commands._utils.option_value_processor import process_env_var, process_image_options


class TestEnvVarParsing(TestCase):
    def test_process_global_env_var(self):
        container_env_vars = ["ENV_VAR1=1", "ENV_VAR2=2"]

        result = process_env_var(container_env_vars)
        self.assertEqual(result, {"Parameters": {"ENV_VAR1": "1", "ENV_VAR2": "2"}})

    def test_process_function_env_var(self):
        container_env_vars = ["Function1.ENV_VAR1=1", "Function2.ENV_VAR2=2"]

        result = process_env_var(container_env_vars)
        self.assertEqual(result, {"Function1": {"ENV_VAR1": "1"}, "Function2": {"ENV_VAR2": "2"}})

    def test_irregular_env_var_value(self):
        container_env_vars = ["TEST_VERSION=1.2.3"]

        result = process_env_var(container_env_vars)
        self.assertEqual(result, {"Parameters": {"TEST_VERSION": "1.2.3"}})

    def test_invalid_function_env_var(self):
        container_env_vars = ["Function1.ENV_VAR1=", "Function2.ENV_VAR2=2"]

        result = process_env_var(container_env_vars)
        self.assertEqual(result, {"Function2": {"ENV_VAR2": "2"}})

    def test_invalid_global_env_var(self):
        container_env_vars = ["ENV_VAR1", "Function2.ENV_VAR2=2"]

        result = process_env_var(container_env_vars)
        self.assertEqual(result, {"Function2": {"ENV_VAR2": "2"}})

    def test_none_env_var_does_not_error_out(self):
        container_env_vars = None

        result = process_env_var(container_env_vars)
        self.assertEqual(result, {})


class TestImageParsing(TestCase):
    def check(self, image_options, expected):
        self.assertEqual(process_image_options(image_options), expected)

    def test_empty_list(self):
        self.check([], {})

    def test_default_image(self):
        self.check(["image1"], {None: "image1"})

    def test_one_function_image(self):
        self.check(["Function1=image1"], {"Function1": "image1"})

    def test_one_function_with_default_image(self):
        self.check(["Function1=image1", "image2"], {"Function1": "image1", None: "image2"})

    def test_two_functions_with_default_image(self):
        self.check(
            ["Function1=image1", "Function2=image2", "image3"],
            {"Function1": "image1", "Function2": "image2", None: "image3"},
        )

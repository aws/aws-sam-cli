from parameterized import parameterized
from unittest import TestCase
from unittest.mock import ANY
from typing import List
from enum import Enum, unique

from samcli.lib.runtimes.base import (
    Runtime,
    RuntimeDataMixin,
    Family,
    Architecture,
    RuntimeEnumBase,
    runtime_dependency_template_mapping,
    init_runtimes,
    lambda_images_runtimes_map,
    sam_runtime_to_schemas_code_lang_mapping,
    provided_runtimes,
    layer_subfolder_mapping,
)
from samcli.local.common.runtime_template import RUNTIME_DEP_TEMPLATE_MAPPING


class TestRuntimeDataMixin(TestCase):
    @parameterized.expand(
        [
            (
                RuntimeDataMixin(
                    key="x", family=Family.DOTNET, lambda_image=None, archs=[Architecture.X86_64, Architecture.ARM64]
                ),
                ["x86_64", "arm64"],
            ),
            (
                RuntimeDataMixin(
                    key="x1", family=Family.DOTNET, lambda_image=None, archs=[Architecture.ARM64, Architecture.X86_64]
                ),
                ["arm64", "x86_64"],
            ),
            (
                RuntimeDataMixin(key="y", family=Family.DOTNET, lambda_image=None, archs=[Architecture.X86_64]),
                ["x86_64"],
            ),
            (RuntimeDataMixin(key="z", family=Family.DOTNET, lambda_image=None, archs=[Architecture.ARM64]), ["arm64"]),
        ]
    )
    def test_archs_as_list_of_str(self, runtime, expect):
        self.assertEqual(runtime.archs_as_list_of_str(), expect)

    @parameterized.expand(
        [
            (RuntimeDataMixin(key="x", family=Family.DOTNET, lambda_image=None), False),
            (RuntimeDataMixin(key="x", family=Family.PYTHON, lambda_image=None), False),
            (RuntimeDataMixin(key="x", family=Family.PROVIDED, lambda_image=None), True),
        ]
    )
    def test_is_provided(self, runtime, expect):
        self.assertEqual(runtime.is_provided, expect)


@unique
class MockRuntime(RuntimeEnumBase):
    a = ("a1", Family.DOTNET, "image/a1", [Architecture.X86_64])
    b = ("b1", Family.DOTNET, "image/b1", [Architecture.X86_64, Architecture.ARM64])
    j = ("j", Family.JAVA, "image/j", [Architecture.X86_64, Architecture.ARM64])
    c39 = ("c.3.9", Family.PYTHON, "image/c.3.9", [Architecture.X86_64, Architecture.ARM64])
    c38 = ("c.3.8", Family.PYTHON, "image/c.3.8", [Architecture.X86_64, Architecture.ARM64])
    p = ("p", Family.PROVIDED, "image/p", [Architecture.X86_64, Architecture.ARM64])
    pg = ("go (provided.al2)", Family.PROVIDED, "image/go", [Architecture.X86_64, Architecture.ARM64], False)


@unique
class MockRuntimeDifferentOrder(RuntimeEnumBase):
    b = ("b1", Family.DOTNET, "image/b1", [Architecture.X86_64, Architecture.ARM64])
    a = ("a1", Family.DOTNET, "image/a1", [Architecture.X86_64])
    j = ("j", Family.JAVA, "image/j", [Architecture.X86_64, Architecture.ARM64])
    c38 = ("c.3.8", Family.PYTHON, "image/c.3.8", [Architecture.X86_64, Architecture.ARM64])
    c39 = ("c.3.9", Family.PYTHON, "image/c.3.9", [Architecture.X86_64, Architecture.ARM64])
    p = ("p", Family.PROVIDED, "image/p", [Architecture.X86_64, Architecture.ARM64])
    pg = ("go (provided.al2)", Family.PROVIDED, "image/go", [Architecture.X86_64, Architecture.ARM64], False)


class TestFuncs(TestCase):

    @parameterized.expand(
        [
            (
                MockRuntime,
                {
                    "dotnet": [
                        {
                            "runtimes": ["a1", "b1"],
                            "dependency_manager": "cli-package",
                            "init_location": str(Family.DOTNET.dep_manager[0][1]),
                            "build": True,
                        }
                    ],
                    "java": [
                        {
                            "runtimes": ["j"],
                            "dependency_manager": "maven",
                            "init_location": str(Family.JAVA.dep_manager[0][1]),
                            "build": True,
                        },
                        {
                            "runtimes": ["j"],
                            "dependency_manager": "gradle",
                            "init_location": str(Family.JAVA.dep_manager[1][1]),
                            "build": True,
                        },
                    ],
                    "python": [
                        {
                            "runtimes": ["c.3.9", "c.3.8"],
                            "dependency_manager": "pip",
                            "init_location": str(Family.PYTHON.dep_manager[0][1]),
                            "build": True,
                        }
                    ],
                },
            ),
            (
                MockRuntimeDifferentOrder,
                {
                    "dotnet": [
                        {
                            "runtimes": ["b1", "a1"],
                            "dependency_manager": "cli-package",
                            "init_location": str(Family.DOTNET.dep_manager[0][1]),
                            "build": True,
                        }
                    ],
                    "java": [
                        {
                            "runtimes": ["j"],
                            "dependency_manager": "maven",
                            "init_location": str(Family.JAVA.dep_manager[0][1]),
                            "build": True,
                        },
                        {
                            "runtimes": ["j"],
                            "dependency_manager": "gradle",
                            "init_location": str(Family.JAVA.dep_manager[1][1]),
                            "build": True,
                        },
                    ],
                    "python": [
                        {
                            "runtimes": ["c.3.8", "c.3.9"],
                            "dependency_manager": "pip",
                            "init_location": str(Family.PYTHON.dep_manager[0][1]),
                            "build": True,
                        }
                    ],
                },
            ),
        ]
    )
    def test_runtime_dependency_template_mapping(self, cls, expect):
        self.maxDiff = None
        r = runtime_dependency_template_mapping(list(cls))
        self.assertDictEqual(r, expect)

    def test_init_runtimes(self):
        r = init_runtimes(list(MockRuntime))
        self.assertEqual(r, ["a1", "b1", "j", "c.3.9", "c.3.8", "p"])

    def test_lambda_images_runtimes_map(self):
        r = lambda_images_runtimes_map(list(MockRuntime))
        self.assertEqual(
            r,
            {
                "a1": "image/a1",
                "b1": "image/b1",
                "c.3.8": "image/c.3.8",
                "c.3.9": "image/c.3.9",
                "go (provided.al2)": "image/go",
                "j": "image/j",
                "p": "image/p",
            },
        )

    def test_sam_runtime_to_schemas_code_lang_mapping(self):
        r = sam_runtime_to_schemas_code_lang_mapping(list(MockRuntime))
        self.assertEqual(
            r,
            {
                "c.3.8": "Python36",
                "c.3.9": "Python36",
                "j": "Java8",
            },
        )

    def test_provided_runtimes(self):
        r = provided_runtimes(list(MockRuntime))
        self.assertEqual(r, ["p"])

    def test_layer_subfolder_mapping(self):
        r = layer_subfolder_mapping(list(MockRuntime))
        self.assertEqual(
            r,
            {
                "a1": "dotnet",
                "b1": "dotnet",
                "c.3.8": "python",
                "c.3.9": "python",
                "j": "java",
            },
        )

import logging
import os
from dataclasses import dataclass, field
from enum import Enum, unique
from pathlib import Path
from typing import Dict, List, Optional, Tuple, cast

LOG = logging.getLogger(__name__)

_init_path = Path(os.path.dirname(__file__)).parent.parent
_templates = _init_path / "lib" / "init" / "templates"
_lambda_images_templates = _init_path / "lib" / "init" / "image_templates"


@unique
class Architecture(Enum):
    X86_64 = "x86_64"
    ARM64 = "arm64"


@dataclass
class FamilyDataMixin:
    key: str
    layer_subfolder: Optional[str]
    dep_manager: List[Tuple[str, Path]] = field(default_factory=list)  # (package manager, path to local init template)
    build: bool = True
    eb_code_binding: Optional[str] = None  # possible values are "Java8", "Python36", "Go1", "TypeScript3"
    include_in_runtime_dep_template_mapping: bool = field(repr=False, default=True)


@unique
class Family(FamilyDataMixin, Enum):
    DOTNET = (
        "dotnet",
        "dotnet",
        [("cli-package", _templates / "cookiecutter-aws-sam-hello-dotnet")],
        True,
    )
    GO = "go", None, [("mod", _templates / "cookiecutter-aws-sam-hello-golang")], False, "Go1"
    JAVA = (
        "java",
        "java",
        [
            ("maven", _templates / "cookiecutter-aws-sam-hello-java-maven"),
            ("gradle", _templates / "cookiecutter-aws-sam-hello-java-gradle"),
        ],
        True,
        "Java8",
    )
    NODEJS = (
        "nodejs",
        "nodejs",
        [("npm", _templates / "cookiecutter-aws-sam-hello-nodejs")],
        True,
    )
    PROVIDED = "provided", "", [], False, None, False  # type: ignore [var-annotated]
    PYTHON = (
        "python",
        "python",
        [("pip", _templates / "cookiecutter-aws-sam-hello-python")],
        True,
        "Python36",
    )
    RUBY = "ruby", "ruby/lib", [("bundler", _templates / "cookiecutter-aws-sam-hello-ruby")]


@dataclass
class RuntimeDataMixin:
    """
    Definition of a SAM Runtime
    """

    key: str
    family: Family
    lambda_image: Optional[str]
    archs: List[Architecture] = field(default_factory=list)
    is_lambda_enum: bool = True
    # build_workflow: WorkflowConfig
    # workflow_selector: ???

    # debug settings - samcli/local/docker/lambda_debug_settings.py
    # debug_entry_setting: callable

    # runtime enum - samcli/local/docker/lambda_image.py

    # DEPRECATED_RUNTIMES - samcli/lib/build/constants.py
    is_deprecated: bool = False

    # local manifest - samcli/lib/init/local_manifest.json
    # is local manifest useful at all?
    def archs_as_list_of_str(self) -> List[str]:
        return [a.value for a in self.archs]

    @property
    def is_provided(self):
        return self.family == Family.PROVIDED

    def to_local_init_manifest(self) -> List[Dict]:
        """
        Example:
        "java8.al2": [
            {
                "directory": "template/cookiecutter-aws-sam-hello-java-gradle",
                "displayName": "Hello World Example: Gradle",
                "dependencyManager": "gradle",
                "appTemplate": "hello-world",
                "packageType": "Zip",
                "useCaseName": "Hello World Example"
            },
            {
                "directory": "template/cookiecutter-aws-sam-hello-java-maven",
                "displayName": "Hello World Example: Maven",
                "dependencyManager": "maven",
                "appTemplate": "hello-world",
                "packageType": "Zip",
                "useCaseName": "Hello World Example"
            }
        ]
        """
        raise NotImplementedError()


class RuntimeEnumBase(RuntimeDataMixin, Enum):
    @classmethod
    def from_str(cls, runtime: Optional[str]) -> "RuntimeEnumBase":
        if runtime:
            for item in cls:
                if item.key == runtime:
                    return item
        raise ValueError("Unknown runtime %s", runtime)


@unique
class Runtime(RuntimeEnumBase):
    """
    NOTE: order runtimes from latest to oldest per family
    """

    dotnet8 = (
        "dotnet8",
        Family.DOTNET,
        "amazon/dotnet8-base",
        [Architecture.X86_64, Architecture.ARM64],
    )

    dotnet6 = (
        "dotnet6",
        Family.DOTNET,
        "amazon/dotnet6-base",
        [Architecture.X86_64, Architecture.ARM64],
    )

    go1x = (
        "go1.x",
        Family.GO,
        "amazon/go1.x-base",
        [Architecture.X86_64],
    )

    java21 = (
        "java21",
        Family.JAVA,
        "amazon/java21-base",
        [Architecture.X86_64, Architecture.ARM64],
    )
    java17 = (
        "java17",
        Family.JAVA,
        "amazon/java17-base",
        [Architecture.X86_64, Architecture.ARM64],
    )
    java11 = (
        "java11",
        Family.JAVA,
        "amazon/java11-base",
        [Architecture.X86_64, Architecture.ARM64],
    )
    java8al2 = (
        "java8.al2",
        Family.JAVA,
        "amazon/java8.al2-base",
        [Architecture.X86_64, Architecture.ARM64],
    )
    java8 = (
        "java8",
        Family.JAVA,
        "amazon/java8-base",
        [Architecture.X86_64],
    )

    nodejs20x = (
        "nodejs20.x",
        Family.NODEJS,
        "amazon/nodejs20.x-base",
        [Architecture.X86_64, Architecture.ARM64],
    )
    nodejs18x = (
        "nodejs18.x",
        Family.NODEJS,
        "amazon/nodejs18.x-base",
        [Architecture.X86_64, Architecture.ARM64],
    )
    nodejs16x = (
        "nodejs16.x",
        Family.NODEJS,
        "amazon/nodejs16.x-base",
        [Architecture.X86_64, Architecture.ARM64],
    )

    provided_al2023 = (
        "provided.al2023",
        Family.PROVIDED,
        None,
        [Architecture.X86_64, Architecture.ARM64],
    )
    provided_al2 = (
        "provided.al2",
        Family.PROVIDED,
        None,
        [Architecture.X86_64, Architecture.ARM64],
    )
    provided = (
        "provided",
        Family.PROVIDED,
        None,
        [Architecture.X86_64],
    )
    go_provided_al2023 = (
        "go (provided.al2023)",
        Family.PROVIDED,
        "amazon/go-provided.al2023-base",
        [Architecture.X86_64, Architecture.ARM64],
        False,
    )
    go_provided_al2 = (
        "go (provided.al2)",
        Family.PROVIDED,
        "amazon/go-provided.al2-base",
        [Architecture.X86_64, Architecture.ARM64],
        False,
    )

    python312 = (
        "python3.12",
        Family.PYTHON,
        "amazon/python3.12-base",
        [Architecture.X86_64, Architecture.ARM64],
    )
    python311 = (
        "python3.11",
        Family.PYTHON,
        "amazon/python3.11-base",
        [Architecture.X86_64, Architecture.ARM64],
    )
    python310 = (
        "python3.10",
        Family.PYTHON,
        "amazon/python3.10-base",
        [Architecture.X86_64, Architecture.ARM64],
    )
    python39 = (
        "python3.9",
        Family.PYTHON,
        "amazon/python3.9-base",
        [Architecture.X86_64, Architecture.ARM64],
    )
    python38 = (
        "python3.8",
        Family.PYTHON,
        "amazon/python3.8-base",
        [Architecture.X86_64, Architecture.ARM64],
    )
    python37 = (
        "python3.7",
        Family.PYTHON,
        "amazon/python3.7-base",
        [Architecture.X86_64],
    )

    ruby32 = (
        "ruby3.2",
        Family.RUBY,
        "amazon/ruby3.2-base",
        [Architecture.X86_64, Architecture.ARM64],
    )


@unique
class DeprecatedRuntime(RuntimeEnumBase):
    pass


def runtime_dep_template_mapping(runtimes: List[RuntimeDataMixin]) -> dict:
    ret: dict = {}
    for runtime in runtimes:
        family = runtime.family
        if not family.include_in_runtime_dep_template_mapping:
            continue
        if family.key not in ret:
            ret[family.key] = []
            for dep_manager, init_loc in family.dep_manager:
                ret[family.key].append(
                    {
                        "runtimes": [],
                        "dependency_manager": dep_manager,
                        "init_location": str(init_loc.absolute()),
                        "build": family.build,
                    }
                )
        for item in ret[family.key]:
            item["runtimes"].append(runtime.key)
    return ret


def init_runtimes(runtimes: List[RuntimeDataMixin]) -> List[str]:
    return [r.key for r in runtimes if r.is_lambda_enum]


def lambda_images_runtimes_map(runtimes: List[RuntimeDataMixin]) -> Dict[str, str]:
    s = sorted([r for r in runtimes if r.lambda_image], key=lambda r: r.key)
    return {r.key: cast(str, r.lambda_image) for r in s}


def sam_runtime_to_schemas_code_lang_mapping(runtimes: List[RuntimeDataMixin]) -> Dict[str, str]:
    return {r.key: r.family.eb_code_binding for r in runtimes if r.family.eb_code_binding}


def provided_runtimes(runtimes: List[RuntimeDataMixin]) -> List[str]:
    return [r.key for r in runtimes if r.family == Family.PROVIDED and r.is_lambda_enum]


def layer_subfolder_mapping(runtimes: List[RuntimeDataMixin]) -> Dict[str, str]:
    return {
        r.key: r.family.layer_subfolder for r in runtimes if not r.is_provided and r.family.layer_subfolder is not None
    }

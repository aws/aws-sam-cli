import os
from pathlib import Path
from typing import List, Dict, Optional, NamedTuple, Tuple
from enum import Enum, EnumMeta

from samcli.lib.build.workflows import CONFIG as WorkflowConfig


_init_path = Path(os.path.dirname(__file__)).parent.parent
_templates = _init_path / "lib" / "init" / "templates"
_lambda_images_templates = _init_path / "lib" / "init" / "image_templates"

class Architecture(Enum):
    X86_64 = "x86_64"
    ARM64 = "arm64"

class _Family(NamedTuple):
    name: str
    dep_manager: List[Tuple[str, Path]] = [] # (package manager, path to local init template)
    build: bool = True
    eb_code_binding: Optional[str] = None
    include_in_runtime_dep_template_mapping: bool = True

class Family(Enum):
    DOTNET = _Family(
        name="dotnet",
        dep_manager=[
            ("cli-package", _templates / "cookiecutter-aws-sam-hello-dotnet"),
        ],
    )

    GO = _Family(
        name="go",
        dep_manager=[
            ("mod", _templates / "cookiecutter-aws-sam-hello-golang"),
        ],
        build=False,
        eb_code_binding="Go1",
    )

    JAVA = _Family(
        name="java",
        dep_manager=[
            ("maven", _templates / "cookiecutter-aws-sam-hello-java-maven"),
            ("gradle", _templates / "cookiecutter-aws-sam-hello-java-gradle"),
        ],
        eb_code_binding="Java8",
    )

    NODEJS = _Family(
        name="nodejs",
        dep_manager=[
            ("npm", _templates / "cookiecutter-aws-sam-hello-nodejs")
        ],
    )

    PROVIDED = _Family(
        name="provided",
        include_in_runtime_dep_template_mapping=False,
    )

    PYTHON = _Family(
        name="python",
        dep_manager=[
            ("pip", _templates / "cookiecutter-aws-sam-hello-python"),
        ],
        eb_code_binding="Python36",
    )

    RUBY = _Family(
        name="ruby",
        dep_manager=[
            ("bundler", _templates / "cookiecutter-aws-sam-hello-ruby"),
        ],
    )


class _Runtime(NamedTuple):
    """
    Definition of a SAM Runtime 
    """
    name: str
    family: Family
    lambda_image: Optional[str]
    archs: List[Architecture] = [Architecture.X86_64]
    is_lambda_enum: bool = True
    # build_workflow: WorkflowConfig
    # layer_subfolder: str
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

class RuntimeEnumBase(Enum):
    @classmethod
    def from_name(cls, name: str) -> "Runtime":
        for item in cls:
            if item.value.name == name:
                return item
        raise ValueError("Unknown runtime %s", name)


class Runtime(RuntimeEnumBase):
    """
    NOTE: order runtimes from latest to oldest per family
    """

    dotnet6 = _Runtime(
        name="dotnet6",
        family=Family.DOTNET,
        lambda_image="amazon/dotnet6-base",
        archs=[Architecture.X86_64, Architecture.ARM64],
    )

    go1x = _Runtime(
        name="go1.x",
        family=Family.GO,
        lambda_image="amazon/go1.x-base",
        archs=[Architecture.X86_64],
    )

    java21 = _Runtime(
        name="java21",
        family=Family.JAVA,
        lambda_image="amazon/java21-base",
        archs=[Architecture.X86_64, Architecture.ARM64],
    )
    java17 = _Runtime(
        name="java17",
        family=Family.JAVA,
        lambda_image="amazon/java17-base",
        archs=[Architecture.X86_64, Architecture.ARM64],
    )
    java11 = _Runtime(
        name="java11",
        family=Family.JAVA,
        lambda_image="amazon/java11-base",
        archs=[Architecture.X86_64, Architecture.ARM64],
    )
    java8al2 = _Runtime(
        name="java8.al2",
        family=Family.JAVA,
        lambda_image="amazon/java8.al2-base",
        archs=[Architecture.X86_64, Architecture.ARM64],
    )
    java8 = _Runtime(
        name="java8",
        family=Family.JAVA,
        lambda_image="amazon/java8-base",
        archs=[Architecture.X86_64],
    )

    nodejs20x = _Runtime(
        name="nodejs20.x",
        family=Family.NODEJS,
        lambda_image="amazon/nodejs20.x-base",
        archs=[Architecture.X86_64, Architecture.ARM64],
    )
    nodejs18x = _Runtime(
        name="nodejs18.x",
        family=Family.NODEJS,
        lambda_image="amazon/nodejs18.x-base",
        archs=[Architecture.X86_64, Architecture.ARM64],
    )
    nodejs16x = _Runtime(
        name="nodejs16.x",
        family=Family.NODEJS,
        lambda_image="amazon/nodejs16.x-base",
        archs=[Architecture.X86_64, Architecture.ARM64],
    )

    provided_al2023 = _Runtime(
        name="provided.al2023",
        family=Family.PROVIDED,
        lambda_image=None,
        archs=[Architecture.X86_64, Architecture.ARM64],
    )
    provided_al2 = _Runtime(
        name="provided.al2",
        family=Family.PROVIDED,
        lambda_image=None,
        archs=[Architecture.X86_64, Architecture.ARM64],
    )
    provided = _Runtime(
        name="provided",
        family=Family.PROVIDED,
        lambda_image=None,
        archs=[Architecture.X86_64],
    )
    go_provided_al2023 = _Runtime(
        name="go (provided.al2023)",
        family=Family.PROVIDED,
        lambda_image="amazon/go-provided.al2023-base",
        archs=[Architecture.X86_64, Architecture.ARM64],
        is_lambda_enum=False,
        
    )
    go_provided_al2 = _Runtime(
        name="go (provided.al2)",
        family=Family.PROVIDED,
        lambda_image="amazon/go-provided.al2-base",
        archs=[Architecture.X86_64, Architecture.ARM64],
        is_lambda_enum=False,
    )

    python312 = _Runtime(
        name="python3.12",
        family=Family.PYTHON,
        lambda_image="amazon/python3.12-base",
        archs=[Architecture.X86_64, Architecture.ARM64],
    )
    python311 = _Runtime(
        name="python3.11",
        family=Family.PYTHON,
        lambda_image="amazon/python3.11-base",
        archs=[Architecture.X86_64, Architecture.ARM64],
    )
    python310 = _Runtime(
        name="python3.10",
        family=Family.PYTHON,
        lambda_image="amazon/python3.10-base",
        archs=[Architecture.X86_64, Architecture.ARM64],
    )
    python39 = _Runtime(
        name="python3.9",
        family=Family.PYTHON,
        lambda_image="amazon/python3.9-base",
        archs=[Architecture.X86_64, Architecture.ARM64],
    )
    python38 = _Runtime(
        name="python3.8",
        family=Family.PYTHON,
        lambda_image="amazon/python3.8-base",
        archs=[Architecture.X86_64, Architecture.ARM64],
    )
    python37 = _Runtime(
        name="python3.7",
        family=Family.PYTHON,
        lambda_image="amazon/python3.7-base",
        archs=[Architecture.X86_64],
    )

    ruby32 = _Runtime(
        name="ruby3.2",
        family=Family.RUBY,
        lambda_image="amazon/ruby3.2-base",
        archs=[Architecture.X86_64, Architecture.ARM64],
    )


class DeprecatedRuntime(RuntimeEnumBase):
    pass
    

def runtime_dep_template_mapping(runtimes: List[_Runtime]) -> Dict:
    ret = {}
    for runtime in runtimes:
        family = runtime.family.value
        if not family.include_in_runtime_dep_template_mapping:
            continue
        if family.name not in ret:
            ret[family.name] = []
            for dep_manager, init_loc in family.dep_manager:
                ret[family.name].append({
                    "runtimes": [],
                    "dependency_manager": dep_manager,
                    "init_location": str(init_loc.absolute()),
                    "build": family.build,
                })
        for item in ret[family.name]:
            item["runtimes"].append(runtime.name)
    return ret

def init_runtimes(runtimes: List[_Runtime]) -> List[str]:
    return [r.name for r in runtimes if r.family.value.include_in_runtime_dep_template_mapping]

def lambda_images_runtimes_map(runtimes: List[_Runtime]) -> Dict[str, str]:
    s = sorted([r for r in runtimes if r.lambda_image], key=lambda r: r.name)
    return {r.name: r.lambda_image for r in s}

def sam_runtime_to_schemas_code_lang_mapping(runtimes: List[_Runtime]) -> Dict[str, str]:
    return {r.name: r.family.value.eb_code_binding for r in runtimes if r.family.value.eb_code_binding}

def provided_runtimes(runtimes: List[_Runtime]) -> List[str]:
    return [r.name for r in runtimes if r.family == Family.PROVIDED and r.is_lambda_enum]

"""
Terraform Makefile and make rule generation

This module generates the Makefile for the project and the rules for each of the Lambda functions found
"""

import glob
import json
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import List, NamedTuple, Optional, Tuple

from samcli.hook_packages.terraform.hooks.prepare.types import (
    SamMetadataResource,
)
from samcli.lib.utils.hash import str_checksum
from samcli.lib.utils.path_utils import convert_path_to_unix_path

LOG = logging.getLogger(__name__)

TERRAFORM_BUILD_SCRIPT = "copy_terraform_built_artifacts.py"
ZIP_UTILS_MODULE = "zip.py"
TF_BACKEND_OVERRIDE_FILENAME = "z_samcli_backend_override"
ARGS_FILE_GLOB_PATTERN = "*.args.json"
# a 16-char hex checksum plus ".args.json" is 26 characters total, comfortably clear of both the
# 255-byte per-component filesystem/OS filename limit and Windows' 260-character MAX_PATH total
# path length limit (see _get_args_file_path)
ARGS_FILE_NAME_HASH_LEN = 16


class PendingArgsFile(NamedTuple):
    """
    An args file (see _get_args_file_path) that still needs to be written to disk.

    Building the args file's path and contents is kept separate from actually writing it, so
    that generation of every Makefile rule can complete - and be confirmed free of errors - before
    any file is written. See generate_makefile(), which is the only place these are written.
    """

    path: str
    expression: str
    target: str


def generate_makefile_rule_for_lambda_resource(
    sam_metadata_resource: SamMetadataResource,
    logical_id: str,
    terraform_application_dir: str,
    python_command_name: str,
    output_dir: str,
    mount_symlinks: bool = False,
) -> Tuple[str, PendingArgsFile]:
    """
    Generates and returns a makefile rule for the lambda resource associated with the given sam metadata resource.

    Parameters
    ----------
    sam_metadata_resource: SamMetadataResource
        A sam metadata resource; the generated makefile rule will correspond to building the lambda resource
        associated with this sam metadata resource
    logical_id: str
        Logical ID of the lambda resource
    terraform_application_dir: str
        the terraform project root directory
    python_command_name: str
        the python command name to use for running a script in the makefile rule
    output_dir: str
        the directory into which the Makefile is written

    Returns
    -------
    Tuple[str, PendingArgsFile]
        The generated makefile rule, and the args file this rule depends on. The caller is
        responsible for passing every PendingArgsFile collected across all rules to
        generate_makefile(), which writes them - this function itself performs no I/O.
    """
    target = _get_makefile_build_target(logical_id)
    resource_address = sam_metadata_resource.resource.get("address", "")
    command, pending_args_file = _build_makerule_python_command(
        python_command_name,
        output_dir,
        resource_address,
        sam_metadata_resource,
        terraform_application_dir,
        logical_id,
        mount_symlinks=mount_symlinks,
    )
    python_command_recipe = _format_makefile_recipe(command)
    return f"{target}{python_command_recipe}", pending_args_file


def generate_makefile(
    makefile_rules: List[str],
    pending_args_files: List[PendingArgsFile],
    output_directory_path: str,
) -> None:
    """
    Generates a makefile with the given rules in the given directory, and writes the args files
    each rule depends on.

    This is the only place args files are written to disk. Collecting every PendingArgsFile
    across all rules first, then writing them all here (rather than as each rule is built) means
    that if generating any single rule fails partway through - e.g. an unrecognized sam metadata
    resource type - no args file for *any* rule has been written yet, so a build that ultimately
    fails to produce a Makefile also leaves no partial args files behind. Stale args files from a
    previous run (e.g. for a Lambda resource that has since been renamed or removed) are pruned
    for the same reason: nothing here is left to accumulate indefinitely across builds.

    Parameters
    ----------
    makefile_rules: List[str]
        the list of rules to write in the Makefile
    pending_args_files: List[PendingArgsFile]
        the args files that the given makefile_rules depend on; written here, after any stale
        args files from a previous run are removed
    output_directory_path: str
        the output directory path to write the generated makefile
    """

    # create output directory if it doesn't exist
    if not os.path.exists(output_directory_path):
        os.makedirs(output_directory_path, exist_ok=True)

    # remove any args files left behind by a previous run (e.g. for a Lambda resource that has
    # since been renamed or removed) before writing this run's set
    for stale_args_file_path in glob.glob(os.path.join(output_directory_path, ARGS_FILE_GLOB_PATTERN)):
        os.remove(stale_args_file_path)

    for pending_args_file in pending_args_files:
        with open(pending_args_file.path, "w+") as args_file:
            json.dump({"expression": pending_args_file.expression, "target": pending_args_file.target}, args_file)

    # create z_samcli_backend_override.tf in output directory
    _generate_backend_override_file(output_directory_path)

    # copy copy_terraform_built_artifacts.py script into output directory
    copy_terraform_built_artifacts_script_path = os.path.join(
        Path(os.path.dirname(__file__)).parent.parent, TERRAFORM_BUILD_SCRIPT
    )
    shutil.copy(copy_terraform_built_artifacts_script_path, output_directory_path)

    samcli_root_path = Path(os.path.dirname(__file__)).parent.parent.parent.parent

    # copy zip.py script into output directory
    ZIP_UTILS_MODULE_script_path = os.path.join(samcli_root_path, "local", "lambdafn", ZIP_UTILS_MODULE)
    shutil.copy(ZIP_UTILS_MODULE_script_path, output_directory_path)

    # create makefile
    makefile_path = os.path.join(output_directory_path, "Makefile")
    with open(makefile_path, "w+") as makefile:
        makefile.writelines(makefile_rules)


def _generate_backend_override_file(output_directory_path: str):
    """
    Generates an override tf file to use a temporary backend

    Parameters
    ----------
    output_directory_path: str
        the output directory path to write the generated makefile
    """
    statefile_filename = f"{uuid.uuid4()}.tfstate"
    override_content = "terraform {\n" '  backend "local" {\n' f'    path = "./{statefile_filename}"\n' "  }\n" "}\n"
    override_file_path = os.path.join(output_directory_path, TF_BACKEND_OVERRIDE_FILENAME)
    with open(override_file_path, "w+") as f:
        f.write(override_content)


def _build_makerule_python_command(
    python_command_name: str,
    output_dir: str,
    resource_address: str,
    sam_metadata_resource: SamMetadataResource,
    terraform_application_dir: str,
    logical_id: str,
    mount_symlinks: bool = False,
) -> Tuple[str, PendingArgsFile]:
    """
    Build the Python command recipe to be used inside of the Makefile rule

    Parameters
    ----------
    python_command_name: str
        the python command name to use for running a script in the makefile recipe
    output_dir: str
        the directory into which the Makefile is written
    resource_address: str
        Address of a given terraform resource
    sam_metadata_resource: SamMetadataResource
        A sam metadata resource; the generated show command recipe will correspond to building the lambda resource
        associated with this sam metadata resource
    terraform_application_dir: str
        the terraform project root directory
    logical_id: str
        Logical ID of the lambda resource; used to name the generated args file

    Returns
    -------
    Tuple[str, PendingArgsFile]
        Fully resolved Terraform show command, and the args file it depends on (not yet written
        to disk - see generate_makefile())
    """
    show_command_template = (
        '{python_command_name} "{terraform_built_artifacts_script_path}" '
        '--directory "$(ARTIFACTS_DIR)" --args-file "{args_file_path}"'
    )
    jpath_string = _build_jpath_string(sam_metadata_resource, resource_address)
    terraform_built_artifacts_script_path = convert_path_to_unix_path(
        str(Path(output_dir, TERRAFORM_BUILD_SCRIPT).relative_to(terraform_application_dir))
    )
    args_file_path = _get_args_file_path(output_dir, logical_id)
    args_file_relative_path = convert_path_to_unix_path(
        str(Path(args_file_path).relative_to(terraform_application_dir))
    )
    command = show_command_template.format(
        python_command_name=python_command_name,
        terraform_built_artifacts_script_path=terraform_built_artifacts_script_path,
        args_file_path=args_file_relative_path,
    )
    if mount_symlinks:
        command += " --mount-symlinks"
    pending_args_file = PendingArgsFile(path=args_file_path, expression=jpath_string, target=resource_address)
    return command, pending_args_file


def _get_args_file_path(output_dir: str, logical_id: str) -> str:
    """
    Deterministically computes the path of the args file for a given Lambda resource, without
    writing anything to disk - see generate_makefile(), which is where the args file content
    (the potentially untrusted Terraform jpath expression and resource address) actually gets
    written, once every Makefile rule has been generated successfully.

    Keeping this path computation free of I/O is what lets _build_makerule_python_command (and
    generate_makefile_rule_for_lambda_resource above it) remain pure functions of their inputs:
    the Makefile recipe text can be built and returned - including the args file path it
    references - without anything touching the filesystem, so a failure generating a *later*
    rule can't leave an *earlier* rule's args file already written with nothing to clean it up.

    The recipe line generated by `_build_makerule_python_command` is first macro-expanded by
    `make`, and the result is then handed to a shell for execution (`/bin/sh` on Linux/macOS,
    or `cmd.exe` on Windows when no `sh.exe` is found on PATH). There is no single escaping
    scheme that is simultaneously safe for `make`'s macro expansion and portable across both
    shells, since their quoting rules are fundamentally different (and `cmd.exe` does not treat
    single quotes as quoting characters at all). Keeping the untrusted expression/resource
    address off the command line entirely sidesteps the problem: only this file path (safe on
    every shell) is ever embedded in the recipe text, and the untrusted content is read directly
    from disk by `copy_terraform_built_artifacts.py`.

    The file is named by hashing logical_id to a fixed-length string, rather than embedding (even
    truncated) logical_id itself. logical_id is deterministic and unique per resource
    (build_cfn_logical_id() strips every non-alphanumeric character and appends a hash of the
    full Terraform address) but can be up to 255 *characters* and is Unicode-aware
    ("alphanumeric" is not limited to ASCII), so a truncation-based name would have to reason
    separately about the 255-*byte* per-component filesystem/OS filename limit and, on Windows,
    the 260-character MAX_PATH limit on the *total* path once combined with a real project
    directory path (MAX_PATH is hit by the project's own path depth too, not just this file name
    in isolation, and a deeply-nested Terraform module address can push logical_id itself close
    to 255 characters). A fixed-length hash sidesteps both regardless of how long or non-ASCII
    logical_id is, and the deterministic name means each `sam build` (which always re-runs
    prepare) overwrites the previous run's file for this resource, rather than accumulating one.

    Note that logical_id is itself derived from the same (potentially attacker-controlled)
    Terraform resource address that motivates this fix - hashing it is safe to embed in the
    recipe because the hash, not the input, is what actually appears there, not because the
    input is inherently trusted.

    Parameters
    ----------
    output_dir: str
        the directory into which the Makefile (and this args file) is written
    logical_id: str
        Logical ID of the lambda resource; hashed to name the args file

    Returns
    -------
    str
        The absolute path of the args file (this function does not create it)
    """
    args_file_name = f"{str_checksum(logical_id)[:ARGS_FILE_NAME_HASH_LEN]}.args.json"
    return os.path.join(output_dir, args_file_name)


def _get_makefile_build_target(logical_id: str) -> str:
    """
    Formats the Makefile rule build target string as is needed by the Makefile

    Parameters
    ----------
    logical_id: str
       Logical ID of the resource to use for the Makefile rule target

    Returns
    -------
    str
        The formatted Makefile rule build target
    """
    return f"build-{logical_id}:\n"


def _format_makefile_recipe(rule_string: str) -> str:
    """
    Formats the Makefile rule string as is needed by the Makefile

    Parameters
    ----------
    rule_string: str
       Makefile rule string to be formatted

    Returns
    -------
    str
        The formatted target rule
    """
    return f"\t{rule_string}\n"


def _build_jpath_string(sam_metadata_resource: SamMetadataResource, resource_address: str) -> str:
    """
    Constructs the JPath string for a given sam metadata resource from the planned_values
    to the build_output_path as is created by the Terraform plan output

    Parameters
    ----------
    sam_metadata_resource: SamMetadataResource
        A sam metadata resource; the generated recipe jpath will correspond to building the lambda resource
        associated with this sam metadata resource

    resource_address: str
        Full address of a Terraform resource

    Returns
    -------
    str
       Full JPath string for a resource from planned_values to build_output_path
    """
    jpath_string_template = (
        "|values|root_module{child_modules}|resources|"
        '[?address=="{resource_address}"]|values|triggers|built_output_path'
    )
    child_modules_template = "|child_modules|[?address=={module_address}]"
    module_address = sam_metadata_resource.current_module_address
    full_module_path = ""
    parent_modules = _get_parent_modules(module_address)
    for module in parent_modules:
        full_module_path += child_modules_template.format(module_address=module)
    jpath_string = jpath_string_template.format(child_modules=full_module_path, resource_address=resource_address)
    return jpath_string


def _get_parent_modules(module_address: Optional[str]) -> List[str]:
    """
    Convert an a full Terraform resource address to a list of module
    addresses from the root module to the current module

    e.g. "module.level1_lambda.module.level2_lambda" as input will return
    ["module.level1_lambda", "module.level1_lambda.module.level2_lambda"]

    Parameters
    ----------
    module_address: str
       Full address of the Terraform module

    Returns
    -------
    List[str]
       List of module addresses starting from the root module to the current module
    """
    if not module_address:
        return []

    # Split the address on "." then combine it back with the "module" prefix for each module name
    modules = module_address.split(".")
    modules = [".".join(modules[i : i + 2]) for i in range(0, len(modules), 2)]

    if not modules:
        # The format of the address was somehow different than we expected from the
        # module.<name>.module.<child_module_name>
        return []

    # Prefix each nested module name with the previous
    previous_module = modules[0]
    full_path_modules = [previous_module]
    for module in modules[1:]:
        norm_module = previous_module + "." + module
        previous_module = norm_module
        full_path_modules.append(norm_module)
    return full_path_modules

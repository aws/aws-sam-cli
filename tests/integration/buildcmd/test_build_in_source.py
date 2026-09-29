import json
import os
import shutil
from pathlib import Path
import pytest
import logging
from parameterized import parameterized
from samcli.lib.utils import osutils

from tests.integration.buildcmd.build_integ_base import (
    BuildIntegBase,
    BuildIntegNodeBase,
    BuildIntegProvidedBase,
    BuildIntegEsbuildBase,
)
from tests.testing_utils import (
    IS_WINDOWS,
    run_command,
)

LOG = logging.getLogger(__name__)


class TestBuildCommand_BuildInSource_Makefile(BuildIntegProvidedBase):
    template = "template.yaml"
    is_nested_parent = False

    def setUp(self):
        super().setUp()

        self.code_uri = "provided_create_new_file"
        test_data_code_uri = Path(self.test_data_path, self.code_uri)
        self.file_created_from_make_command = "file-created-from-make-command.txt"

        scratch_code_uri_path = Path(self.working_dir, self.code_uri)
        self.code_uri_path = str(scratch_code_uri_path)

        # copy source code into temporary directory and update code uri to that scratch dir
        osutils.copytree(test_data_code_uri, scratch_code_uri_path)

    @parameterized.expand(
        [
            (True, True),  # build in source
            (False, False),  # don't build in source
            (None, False),  # use default for workflow (don't build in source)
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_builds_successfully_with_makefile(self, build_in_source, new_file_should_be_in_codeuri):
        self._test_with_Makefile(
            runtime="provided.al2",
            use_container=False,
            manifest=None,
            code_uri=self.code_uri_path,
            build_in_source=build_in_source,
        )

        self.assertEqual(
            self.file_created_from_make_command in os.listdir(self.code_uri_path), new_file_should_be_in_codeuri
        )


class TestBuildCommand_BuildInSource_Esbuild(BuildIntegEsbuildBase):
    is_nested_parent = False
    template = "template_with_metadata_esbuild.yaml"

    def setUp(self):
        super().setUp()

        source_files_path = Path(self.test_data_path, "Esbuild")
        osutils.copytree(source_files_path, self.working_dir)

    @parameterized.expand(
        [
            (True, True),  # build in source
            (False, False),  # don't build in source
            (None, False),  # use default for workflow (don't build in source)
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_builds_successfully_without_local_dependencies(self, build_in_source, dependencies_expected_in_source):
        codeuri = os.path.join(self.working_dir, "Node")

        self._test_with_default_package_json(
            build_in_source=build_in_source,
            runtime="nodejs24.x",
            code_uri=codeuri,
            handler="main.lambdaHandler",
            architecture="x86_64",
            use_container=False,
            expected_files={"main.js", "main.js.map"},
        )

        # check whether dependencies were installed in source dir
        self.assertEqual(os.path.isdir(os.path.join(codeuri, "node_modules")), dependencies_expected_in_source)

    @pytest.mark.flaky(reruns=3)
    def test_builds_successfully_with_local_dependency(self):
        codeuri = os.path.join(self.working_dir, "NodeWithLocalDependency")
        runtime = "nodejs24.x"
        architecture = "x86_64"

        self._test_with_default_package_json(
            build_in_source=True,
            runtime=runtime,
            code_uri=codeuri,
            handler="main.lambdaHandler",
            architecture=architecture,
            use_container=False,
            expected_files={"main.js", "main.js.map"},
        )

        # check whether dependencies were installed in source dir
        self.assertEqual(os.path.isdir(os.path.join(codeuri, "node_modules")), True)


class TestBuildCommand_BuildInSource_Nodejs(BuildIntegNodeBase):
    is_nested_parent = False
    template = "template.yaml"

    def setUp(self):
        super().setUp()

        osutils.copytree(Path(self.test_data_path, "Esbuild"), self.working_dir)

    def tearDown(self):
        super().tearDown()

    def validate_node_modules(self, is_build_in_source_behaviour: bool):
        # validate if node modules exist in the built artifact dir
        built_node_modules = Path(self.default_build_dir, "Function", "node_modules")
        self.assertEqual(built_node_modules.is_dir(), True, "node_modules not found in artifact dir")
        self.assertEqual(built_node_modules.is_symlink(), is_build_in_source_behaviour)

        # validate that node modules are suppose to exist in the source dir
        source_node_modules = Path(self.codeuri_path, "node_modules")
        self.assertEqual(source_node_modules.is_dir(), is_build_in_source_behaviour)

    @parameterized.expand(
        [
            (True, True),  # build in source
            (False, False),  # don't build in source
            (None, False),  # use default for workflow (don't build in source)
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_builds_successfully_without_local_dependencies(self, build_in_source, expected_built_in_source):
        self.codeuri_path = Path(self.working_dir, "Node")

        overrides = self.get_override(
            runtime="nodejs24.x", code_uri=self.codeuri_path, architecture="x86_64", handler="main.lambdaHandler"
        )
        command_list = self.get_command_list(build_in_source=build_in_source, parameter_overrides=overrides, debug=True)

        run_command(command_list, self.working_dir)
        self.validate_node_modules(expected_built_in_source)

    @pytest.mark.flaky(reruns=3)
    def test_builds_successfully_with_local_dependency(self):
        self.codeuri_path = Path(self.working_dir, "NodeWithLocalDependency")

        overrides = self.get_override(
            runtime="nodejs24.x", code_uri=self.codeuri_path, architecture="x86_64", handler="main.lambdaHandler"
        )
        command_list = self.get_command_list(build_in_source=True, parameter_overrides=overrides)

        run_command(command_list, self.working_dir)
        self.validate_node_modules(True)


WORKSPACE_INSTALL_LOG_MESSAGE = "Installing dependencies once for workspace root"


class NpmCallLogMixin:
    """
    Puts an npm shim first on PATH that appends every npm invocation to a log file before
    delegating to the real npm, so tests can assert on how many installs a build ran.
    """

    def setup_npm_call_log(self):
        real_npm = shutil.which("npm")
        if not real_npm:
            self.skipTest("npm is not available on PATH")

        self.npm_call_log = Path(self.scratch_dir, "npm-calls.log")
        self._npm_shim_dir = Path(self.scratch_dir, "npm-shim")
        self._npm_shim_dir.mkdir()

        if IS_WINDOWS:
            shim = self._npm_shim_dir / "npm.cmd"
            shim.write_text('@echo off\r\necho %* >> "%NPM_CALL_LOG%"\r\ncall "{}" %*\r\n'.format(real_npm))
        else:
            shim = self._npm_shim_dir / "npm"
            shim.write_text('#!/bin/sh\necho "$@" >> "$NPM_CALL_LOG"\nexec "{}" "$@"\n'.format(real_npm))
            shim.chmod(0o755)

    def npm_logging_env(self):
        env = os.environ.copy()
        env["PATH"] = str(self._npm_shim_dir) + os.pathsep + env["PATH"]
        env["NPM_CALL_LOG"] = str(self.npm_call_log)
        return env

    def npm_install_commands(self):
        """Every logged npm invocation that resolves dependencies (install/update/ci)."""
        if not self.npm_call_log.exists():
            return []
        lines = [line.strip() for line in self.npm_call_log.read_text().splitlines() if line.strip()]
        return [line for line in lines if line.split()[0] in ("install", "update", "ci")]


class TestBuildCommand_BuildInSource_NodejsWorkspaces(NpmCallLogMixin, BuildIntegBase):
    """
    An npm workspaces monorepo builds all member functions off ONE install at the workspace
    root. The fixture has two functions with disjoint dependencies plus a shared workspace
    package, and its lockfile pins versions below what the manifests' ranges allow (lodash
    4.17.20 for a ^4.17.20 range), so a lockfile-ignoring build is detectable. The shared
    package pins lodash 4.17.15 exactly, giving a version conflict npm keeps as a nested copy.
    """

    template = None  # the template lives inside the copied fixture

    def setUp(self):
        super().setUp()
        osutils.copytree(Path(self.test_data_path, "NodeWorkspaces"), self.working_dir)
        self.template_path = str(Path(self.working_dir, "template.yaml"))
        self.lockfile_path = Path(self.working_dir, "package-lock.json")
        self.setup_npm_call_log()

    def artifact_modules(self, logical_id) -> Path:
        return Path(self.default_build_dir, logical_id, "node_modules")

    def run_built_handler(self, logical_id) -> dict:
        result = run_command(
            ["node", "-e", 'require("./index.js").handler().then(r => console.log(r.body))'],
            cwd=str(Path(self.default_build_dir, logical_id)),
        )
        self.assertEqual(result.process.returncode, 0, result.stderr.decode("utf-8"))
        return json.loads(result.stdout.decode("utf-8").strip())

    def build_workspace(self, parallel=False):
        command_list = self.get_command_list(build_in_source=True, parallel=parallel, debug=True)
        result = run_command(command_list, cwd=self.working_dir, env=self.npm_logging_env())
        self.assertEqual(result.process.returncode, 0, result.stderr.decode("utf-8"))
        return result

    def assert_artifacts_are_disjoint(self):
        lodash_modules = self.artifact_modules("LodashFunction")
        self.assertTrue((lodash_modules / "lodash").is_dir(), "LodashFunction is missing its own dependency")
        self.assertTrue((lodash_modules / "@mono" / "shared").is_dir(), "LodashFunction is missing the shared package")
        self.assertFalse((lodash_modules / "axios").exists(), "LodashFunction got its sibling's dependency")

        axios_modules = self.artifact_modules("AxiosFunction")
        self.assertTrue((axios_modules / "axios").is_dir(), "AxiosFunction is missing its own dependency")
        self.assertTrue((axios_modules / "@mono" / "shared").is_dir(), "AxiosFunction is missing the shared package")
        self.assertFalse((axios_modules / "lodash").exists(), "AxiosFunction got its sibling's dependency")

    @pytest.mark.flaky(reruns=3)
    def test_installs_once_with_disjoint_artifacts_and_untouched_lockfile(self):
        lockfile_bytes_before = self.lockfile_path.read_bytes()

        result = self.build_workspace()

        self.assertIn(WORKSPACE_INSTALL_LOG_MESSAGE, result.stderr.decode("utf-8"))

        # one install for the whole workspace, not one per function
        installs = self.npm_install_commands()
        self.assertEqual(len(installs), 1, f"expected exactly one npm install, saw: {installs}")
        # the root install must keep the root's own devDependencies (build tools like esbuild)
        self.assertNotIn("--omit=dev", installs[0])

        self.assert_artifacts_are_disjoint()

        # the lockfile was honoured: it pins 4.17.20 although the manifest range allows newer
        lodash_manifest = self.artifact_modules("LodashFunction") / "lodash" / "package.json"
        self.assertEqual(json.loads(lodash_manifest.read_text())["version"], "4.17.20")

        # and its bytes are untouched by the build
        self.assertEqual(self.lockfile_path.read_bytes(), lockfile_bytes_before)

    @pytest.mark.flaky(reruns=3)
    def test_handlers_resolve_from_artifact_dirs(self):
        self.build_workspace()

        lodash_body = self.run_built_handler("LodashFunction")
        self.assertEqual(lodash_body["ownLodashVersion"], "4.17.20")
        # the shared package's conflicting lodash 4.17.15 stayed a nested copy: the function
        # resolves its own version while the shared package resolves the pinned one
        self.assertEqual(lodash_body["sharedLodashVersion"], "4.17.15")

        axios_body = self.run_built_handler("AxiosFunction")
        self.assertEqual(axios_body["axiosVersion"], "1.6.0")
        self.assertEqual(axios_body["sharedLodashVersion"], "4.17.15")

    @pytest.mark.flaky(reruns=3)
    def test_parallel_build_installs_once_before_function_builds(self):
        result = self.build_workspace(parallel=True)

        self.assertIn(WORKSPACE_INSTALL_LOG_MESSAGE, result.stderr.decode("utf-8"))
        installs = self.npm_install_commands()
        self.assertEqual(len(installs), 1, f"expected exactly one npm install, saw: {installs}")

        # a function build racing ahead of the install would link dependencies that do not
        # exist yet, so complete artifacts prove the install was a barrier
        self.assert_artifacts_are_disjoint()

    @pytest.mark.flaky(reruns=3)
    def test_use_container_cannot_reach_the_workspace_grouping(self):
        # workspace grouping only activates under --build-in-source, and the CLI refuses that
        # flag together with --use-container, so a container build can never group: it keeps
        # today's per-function installs by construction
        command_list = self.get_command_list(build_in_source=True, use_container=True)
        result = run_command(command_list, cwd=self.working_dir, env=self.npm_logging_env())

        self.assertNotEqual(result.process.returncode, 0)
        self.assertIn(
            "must not provide both the --build-in-source and --use-container",
            result.stderr.decode("utf-8"),
        )
        self.assertNotIn(WORKSPACE_INSTALL_LOG_MESSAGE, result.stderr.decode("utf-8"))
        self.assertEqual(self.npm_install_commands(), [])


class TestBuildCommand_BuildInSource_NodejsWorkspacesEsbuild(NpmCallLogMixin, BuildIntegBase):
    """
    The esbuild workflow reaches the same grouping, because both nodejs workflows funnel their
    installs through the same npm project tree. What differs is the artifact side: esbuild bundles
    what each entry point imports instead of linking a node_modules, so these functions are built
    with no dependency directory at all and the bundle has to have resolved through the tree npm
    hoisted to the workspace root.

    This is the workflow aws/aws-sam-cli#6567 actually reports, and the fixture carries the reason
    the shared install must not pass --omit=dev: `esbuild` is the ROOT's own devDependency, so an
    install that pruned it would delete the bundler this build needs.
    """

    template = None  # the template lives inside the copied fixture

    def setUp(self):
        super().setUp()
        osutils.copytree(Path(self.test_data_path, "NodeWorkspacesEsbuild"), self.working_dir)
        self.template_path = str(Path(self.working_dir, "template.yaml"))
        self.setup_npm_call_log()

    def artifact_dir(self, logical_id) -> Path:
        return Path(self.default_build_dir, logical_id)

    def run_bundle(self, logical_id) -> dict:
        result = run_command(
            ["node", "-e", 'require("./index.js").handler().then(r => console.log(r.body))'],
            cwd=str(self.artifact_dir(logical_id)),
        )
        self.assertEqual(result.process.returncode, 0, result.stderr.decode("utf-8"))
        return json.loads(result.stdout.decode("utf-8").strip())

    @pytest.mark.flaky(reruns=3)
    def test_installs_once_then_bundles_each_function(self):
        command_list = self.get_command_list(build_in_source=True, debug=True)
        result = run_command(command_list, cwd=self.working_dir, env=self.npm_logging_env())
        self.assertEqual(result.process.returncode, 0, result.stderr.decode("utf-8"))

        self.assertIn(WORKSPACE_INSTALL_LOG_MESSAGE, result.stderr.decode("utf-8"))

        # one install for the whole workspace, not one per function
        installs = self.npm_install_commands()
        self.assertEqual(len(installs), 1, f"expected exactly one npm install, saw: {installs}")
        # --omit=dev here would remove the root's own esbuild and the bundling below could not run
        self.assertNotIn("--omit=dev", installs[0])
        self.assertTrue(
            Path(self.working_dir, "node_modules", "esbuild").is_dir(),
            "the shared install pruned the root's own esbuild devDependency",
        )

        for logical_id in ("LodashFunction", "AxiosFunction"):
            artifacts = self.artifact_dir(logical_id)
            self.assertTrue((artifacts / "index.js").is_file(), f"{logical_id} produced no bundle")
            # esbuild inlines what it needs, so unlike the plain npm workflow there is nothing to link
            self.assertFalse(
                (artifacts / "node_modules").exists(),
                f"{logical_id} got a node_modules; the bundle should carry its dependencies",
            )

        # each bundle resolved through the hoisted root tree, including the shared package's
        # conflicting lodash, which npm keeps as a nested copy
        lodash_body = self.run_bundle("LodashFunction")
        self.assertEqual(lodash_body["ownLodashVersion"], "4.17.20")
        self.assertEqual(lodash_body["sharedLodashVersion"], "4.17.15")

        axios_body = self.run_bundle("AxiosFunction")
        self.assertEqual(axios_body["axiosVersion"], "1.6.0")
        self.assertEqual(axios_body["sharedLodashVersion"], "4.17.15")


class TestBuildCommand_BuildInSource_NodejsStandaloneNotGrouped(NpmCallLogMixin, BuildIntegNodeBase):
    """A standalone (non-workspace) nodejs project keeps its per-function install unchanged."""

    template = "template.yaml"

    def setUp(self):
        super().setUp()
        osutils.copytree(Path(self.test_data_path, "Esbuild"), self.working_dir)
        self.setup_npm_call_log()

    @pytest.mark.flaky(reruns=3)
    def test_standalone_project_keeps_per_function_install(self):
        codeuri = Path(self.working_dir, "Node")

        overrides = self.get_override(
            runtime="nodejs24.x", code_uri=str(codeuri), architecture="x86_64", handler="main.lambdaHandler"
        )
        command_list = self.get_command_list(build_in_source=True, parameter_overrides=overrides, debug=True)
        result = run_command(command_list, cwd=self.working_dir, env=self.npm_logging_env())
        self.assertEqual(result.process.returncode, 0, result.stderr.decode("utf-8"))

        # no workspace grouping for a project whose npm root is its own directory
        self.assertNotIn(WORKSPACE_INSTALL_LOG_MESSAGE, result.stderr.decode("utf-8"))

        # the same single per-function install as before the change: this fixture has no
        # lockfile, so building in source resolves dependencies with `npm update --omit=dev`
        installs = self.npm_install_commands()
        self.assertEqual(len(installs), 1, f"expected exactly one npm install, saw: {installs}")
        self.assertEqual(installs[0].split()[0], "update")
        self.assertIn("--omit=dev", installs[0])

        self.assertTrue(Path(codeuri, "node_modules").is_dir())

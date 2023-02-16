import os
import pytest
import logging
from unittest import skip
from parameterized import parameterized

from tests.integration.buildcmd.build_integ_base import BuildIntegProvidedBase

LOG = logging.getLogger(__name__)


@skip("Building in source option is not exposed yet. Stop skipping once it is.")
class TestBuildCommand_BuildInSource_Makefile(BuildIntegProvidedBase):
    template = "template.yaml"
    is_nested_parent = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.code_uri = "provided_create_new_file"
        cls.code_uri_path = os.path.join(cls.test_data_path, cls.code_uri)
        cls.file_created_from_make_command = "file-created-from-make-command.txt"

    def tearDown(self):
        super().tearDown()
        new_file_in_codeuri_path = os.path.join(self.code_uri_path, self.file_created_from_make_command)
        if os.path.isfile(new_file_in_codeuri_path):
            os.remove(new_file_in_codeuri_path)

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
            code_uri=self.code_uri,
            build_in_source=build_in_source,
        )

        self.assertEqual(
            self.file_created_from_make_command in os.listdir(self.code_uri_path), new_file_should_be_in_codeuri
        )

import os
import shutil
from pathlib import Path
from typing import List
from unittest import TestCase


class InitIntegBase(TestCase):
    generated_files: List[Path] = []

    @classmethod
    def setUpClass(cls) -> None:
        # we need to compare the whole generated template, which is
        # larger than normal diff size limit
        cls.maxDiff = None

    def setUp(self) -> None:
        super().setUp()
        self.generated_files = []

    def tearDown(self) -> None:
        for generated_file in self.generated_files:
            if generated_file.is_dir():
                shutil.rmtree(generated_file)
            else:
                generated_file.unlink()
        super().tearDown()

    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_init_command_list(
        self,
    ):
        command_list = [self.base_command(), "pipeline", "init"]
        return command_list

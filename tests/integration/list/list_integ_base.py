import os
from unittest import TestCase
from pathlib import Path
import uuid
import shutil
import tempfile
from tests.testing_utils import get_sam_command


class ListIntegBase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cmd = cls.base_command()

    @classmethod
    def base_command(cls):
        return get_sam_command()

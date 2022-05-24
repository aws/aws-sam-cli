import os
from typing import Optional
from unittest import TestCase, skipIf
from pathlib import Path
from subprocess import Popen, PIPE, TimeoutExpired

class ResourcesIntegBase(TestCase):
    @classmethod
    def setUpClass(cls):

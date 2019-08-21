import os
import platform

IS_WINDOWS = platform.system().lower() == 'windows'
RUNNING_ON_TRAVIS = os.environ.get("TRAVIS", False)
RUNNING_TEST_FOR_MASTER_ON_TRAVIS = os.environ.get("TRAVIS_BRANCH", "master") != "master"
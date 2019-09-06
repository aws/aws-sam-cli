import io
import sys
import os
from subprocess import Popen, PIPE


def read(*filenames, **kwargs):
    encoding = kwargs.get("encoding", "utf-8")
    sep = kwargs.get("sep", os.linesep)
    buf = []
    for filename in filenames:
        with io.open(filename, encoding=encoding) as f:
            buf.append(f.read())
    return sep.join(buf)


def get_requirements_list(content):
    pkgs_versions = []
    for line in content.split(os.linesep):
        if line:
            # remove markers from the line, which are seperated by ';'
            pkgs_versions.append(line.split(";")[0])

    return pkgs_versions


# Don't try and compare the isolated list with the Python2 version. SAM CLI installers
# all use Python3.6+ and Python2.7 is going EOL
if sys.version_info[0] < 3:
    sys.exit(0)

isolated_req_content = read(os.path.join("requirements", "isolated.txt"))
base_req_content = read(os.path.join("requirements", "base.txt"))

isolated_req_list = get_requirements_list(isolated_req_content)
base_req_list = get_requirements_list(base_req_content)

process = Popen(["pip", "freeze"], stdout=PIPE)

all_installed_pkgs_list = []
for package in process.stdout.readlines():
    package = package.decode("utf-8").strip(os.linesep)
    all_installed_pkgs_list.append(package)

for installed_pkg_version in all_installed_pkgs_list:
    for base_req in base_req_list:
        # a base requirement can be defined with different specifiers (>, <, ==, etc.). Instead of doing tons of string parsing,
        # brute force the check by assuming the installed_pkgs will have == as a specifier. This is true due to how pip freeze
        # works. So check to make sure the installed pakcage we are looking at is in the base.txt file, if so make sure the
        # full requirement==version is within the isolated list.
        installed_pkg = installed_pkg_version.split("==")[0]
        # There is a py library we use but due to how we are comparing requirements, we need to handle this as a special case. :(
        if installed_pkg not in ("py", "boto3") and base_req.startswith(installed_pkg):
            assert installed_pkg_version in isolated_req_list, "{} is in base.txt but not in isolated.txt".format(
                installed_pkg_version
            )
            print ("{} is in the isolated.txt file".format(installed_pkg_version))
            break

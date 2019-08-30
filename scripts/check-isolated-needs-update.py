import io
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


isolated_req_content = read(os.path.join("requirements", "isolated.txt"))
base_req_content = read(os.path.join("requirements", "base.txt"))

isolated_req_list = get_requirements_list(isolated_req_content)
base_req_list = get_requirements_list(base_req_content)

process = Popen(["pip", "freeze"], stdout=PIPE)

all_installed_pkgs_list = []
for package in process.stdout.readlines():
    package = package.decode("utf-8").strip(os.linesep)
    all_installed_pkgs_list.append(package)

for installed_pkg in all_installed_pkgs_list:
    for base_req in base_req_list:
        # a base requirement can be defined with different specifiers (>, <, ==, etc.). Instead of doing tons of string parsing,
        # brute force the check by assuming the installed_pkgs will have == as a specifier. This is true due to how pip freeze
        # works. So check to make sure the installed pakcage we are looking at is in the base.txt file, if so make sure the
        # full requirement==version is within the isolated list.
        if base_req.startswith(installed_pkg.split("==")[0]):
            assert installed_pkg in isolated_req_list, "{} is in base.txt but not in isolated.txt".format(installed_pkg)
            print("{} is in the isolated.txt file".format(installed_pkg))
            break

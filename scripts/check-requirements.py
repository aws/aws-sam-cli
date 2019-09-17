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


exclude_packages = ("setuptools", "wheel", "pip", "aws-sam-cli")

all_pkgs_list = []
process = Popen(["pip", "freeze"], stdout=PIPE)

for package in process.stdout.readlines():
    package = package.decode("utf-8").strip(os.linesep)
    if package.split("==")[0] not in exclude_packages:
        all_pkgs_list.append(package)
all_pkgs_list = sorted(all_pkgs_list)
print ("installed package/versions" + os.linesep)
print (",".join(all_pkgs_list))
print (os.linesep)

content = read(os.path.join("requirements", "isolated.txt"))

locked_pkgs = []
for line in content.split(os.linesep):
    if line:
        locked_pkgs.append(line)

locked_pkgs = sorted(locked_pkgs)
print ("locked package/versions" + os.linesep)
print (",".join(locked_pkgs))
print (os.linesep)

assert len(locked_pkgs) == len(all_pkgs_list), "Number of expected dependencies do not match the number installed"
assert locked_pkgs == all_pkgs_list, "The list of expected dependencies do not match what is installed"

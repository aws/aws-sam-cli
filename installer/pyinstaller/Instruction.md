Running build script
```
docker run --mount type=bind,src="{Absolute path to AWS SAM CLI source}",dst="/aws-sam-cli" -it quay.io/pypa/manylinux2014_x86_64
cd aws-sam-cli
./installer/pyinstaller/build-linux.sh aws-sam-cli-linux-x86_64.zip
```

### Linux Builds
The Linux builds require using a [manylinux image](https://github.com/pypa/manylinux) to build an artifact usable on a breadth of Linux machines. The currently used image is
`quay.io/pypa/manylinux2014_x86_64:latest` which uses glibc version `2.17`. This version of glibc is outdated and requires updating
to support newer software such as Node.js 20 used by GitHub actions. In the meantime, the Linux pyinstaller action is run inside
of a nested container to get around this issue. In the future, we need to move to using a newer image with a newer version of glibc
configured. 

A good candidate for this is `quay.io/pypa/manylinux_2_28_x86_64` which is an image that uses glibc version `2.28`. However,
the current Amazon Linux 2 image uses glibc version `2.26`, meaning that upgrading now will render customer on that OS incapable of using
newer versions of AWS SAM CLI. When that image hits its [end-of-life date](https://github.com/mayeut/pep600_compliance?tab=readme-ov-file#distro-compatibility), we can update the installer to use the newer image.


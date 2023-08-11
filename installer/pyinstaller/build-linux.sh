#!/bin/sh
binary_zip_filename=$1
python_library_zip_filename=$2
build_binary_name=$3
build_folder=$4
python_version=$5

if [ "$python_library_zip_filename" = "" ]; then
    python_library_zip_filename="python-libraries.zip";
fi

if [ "$python_version" = "" ]; then
    python_version="3.11.3";
fi

if [ "$CI_OVERRIDE" = "1" ]; then
  build_folder="aws-sam-cli-beta"
  build_binary_name="sam-beta"
fi

if ! [ "$build_binary_name" = "" ]; then
    echo "Building native installer with nightly/beta build"
    is_nightly="true"
else
    echo "Building native installer with normal build"
    is_nightly="false"
fi

set -eux

yum install -y zlib-devel libffi-devel bzip2-devel

echo "Making Folders"
mkdir -p .build/src
mkdir -p .build/output/aws-sam-cli-src
mkdir -p .build/output/python-libraries
mkdir -p .build/output/pyinstaller-output
mkdir -p .build/output/openssl
cd .build/output/openssl

curl "https://www.openssl.org/source/openssl-1.1.1t.tar.gz" --output openssl-1.1.1.tar.gz
tar xzf openssl-1.1.1.tar.gz
cd openssl-1.1.1t
./config --prefix=/opt/openssl && make && make install
cd ../../..

echo "Copying Source"
cp -r ../[!.]* ./src
cp -r ./src/* ./output/aws-sam-cli-src

echo "Removing CI Scripts and other files/direcories not needed"
rm -vf ./output/aws-sam-cli-src/appveyor*.yml
rm -rf ./output/aws-sam-cli-src/tests
rm -rf ./output/aws-sam-cli-src/designs
rm -rf ./output/aws-sam-cli-src/docs
rm -rf ./output/aws-sam-cli-src/media
rm -rf ./output/aws-sam-cli-src/schema
rm -rf ./output/aws-sam-cli-src/Make.ps1
rm -rf ./output/aws-sam-cli-src/CODEOWNERS
rm -rf ./output/aws-sam-cli-src/CODE_OF_CONDUCT.md
rm -rf ./output/aws-sam-cli-src/CONTRIBUTING.md
rm -rf ./output/aws-sam-cli-src/DESIGN.md
rm -rf ./output/aws-sam-cli-src/Makefile
rm -rf ./output/aws-sam-cli-src/mypy.ini
rm -rf ./output/aws-sam-cli-src/pytest.ini

echo "Installing Python"
curl "https://www.python.org/ftp/python/${python_version}/Python-${python_version}.tgz" --output python.tgz
tar -xzf python.tgz
cd Python-$python_version
./configure --enable-shared --with-openssl=/opt/openssl --with-openssl-rpath=auto 
make -j8
make install
ldconfig
cd ..

echo "Installing Python Libraries"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r src/requirements/reproducible-linux.txt

echo "Copying All Python Libraries"
cp -r ./venv/lib/python*/site-packages/* ./output/python-libraries

echo "Installing PyInstaller"
./venv/bin/pip install -r src/requirements/pyinstaller-build.txt
./venv/bin/pip check

echo "Building Binary"
cd src
if [ "$is_nightly" = "true" ]; then
    echo "Updating samcli.spec with nightly/beta build"
    sed -i.bak "s/'sam'/'$build_binary_name'/g" installer/pyinstaller/samcli.spec
    rm installer/pyinstaller/samcli.spec.bak
fi
echo "samcli.spec content is:"
cat installer/pyinstaller/samcli.spec
# --onedir/--onefile options not allowed when spec file provided for
# updated pyinstaller version.
../venv/bin/python -m PyInstaller --clean installer/pyinstaller/samcli.spec


mkdir pyinstaller-output
dist_folder="sam"
if [ "$is_nightly" = "true" ]; then
    echo "using dist_folder with nightly/beta build"
    dist_folder=$build_binary_name
fi
echo "dist_folder=$dist_folder"
mv "dist/$dist_folder" pyinstaller-output/dist
cp installer/assets/* pyinstaller-output
chmod 755 pyinstaller-output/install
if [ "$is_nightly" = "true" ]; then
    echo "Updating install script with nightly/beta build"
    sed -i.bak "s/\/usr\/local\/aws-sam-cli/\/usr\/local\/$build_folder/g" pyinstaller-output/install
    sed -i.bak 's/EXE_NAME=\"sam\"/EXE_NAME=\"'$build_binary_name'\"/g' pyinstaller-output/install
    rm pyinstaller-output/install.bak
fi
echo "install script content is:"
cat pyinstaller-output/install
echo "Copying Binary"
cd ..
cp -r src/pyinstaller-output/* output/pyinstaller-output

echo "Packaging Binary"
yum install -y zip
cd output/pyinstaller-output/
zip -r ../"$binary_zip_filename" ./*
cd ..
zip -r "$binary_zip_filename" aws-sam-cli-src

echo "Packaging Python Libraries"
cd python-libraries
rm -rf ./*.dist-info
rm -rf ./*.egg-info
rm -rf ./__pycache__
rm -rf ./pip
rm -rf ./easy_install.py
rm -rf ./pkg_resources
rm -rf ./setuptools

rm -rf ./*.so
zip -r ../$python_library_zip_filename ./*
cd ..
zip -r $python_library_zip_filename aws-sam-cli-src

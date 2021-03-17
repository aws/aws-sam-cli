#!/bin/sh
binary_zip_filename=$1
python_library_zip_filename=$2
python_version=$3

if [ "$python_library_zip_filename" = "" ]; then
    python_library_zip_filename="python-libraries.zip";
fi

if [ "$python_version" = "" ]; then
    python_version="3.7.9";
fi

set -eu

yum install -y zlib-devel openssl-devel

echo "Making Folders"
mkdir -p .build/src
mkdir -p .build/output/aws-sam-cli-src
mkdir -p .build/output/python-libraries
mkdir -p .build/output/pyinstaller-output
cd .build

echo "Copying Source"
cp -r ../[!.]* ./src
cp -r ./src/* ./output/aws-sam-cli-src

echo "Installing Python"
curl "https://www.python.org/ftp/python/${python_version}/Python-${python_version}.tgz" --output python.tgz
tar -xzf python.tgz
cd Python-$python_version
./configure --enable-shared
make -j8
make install
cd ..

echo "Installing Python Libraries"
python3 -m venv venv
./venv/bin/pip install -r src/requirements/reproducible-linux.txt

echo "Copying All Python Libraries"
cp -r ./venv/lib/python*/site-packages/* ./output/python-libraries

echo "Installing PyInstaller"
./venv/bin/pip install -r src/requirements/pyinstaller-build.txt

echo "Building Binary"
cd src
../venv/bin/python -m PyInstaller -D --clean installer/pyinstaller/samcli-nightly.spec


mkdir pyinstaller-output

mv dist/sam-nightly pyinstaller-output/dist
cp installer/assets/* pyinstaller-output
mv pyinstaller-output/install-nightly pyinstaller-output/install
chmod 755 pyinstaller-output/install

echo "Copying Binary"
cd ..
cp -r src/pyinstaller-output/* output/pyinstaller-output

echo "Packaging Binary"
yum install -y zip
cd output
cd pyinstaller-output
cd dist
cd ..
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

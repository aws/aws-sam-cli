#!/bin/sh

binary_zip_filename=${1:-}
python_library_zip_filename=${2:-}
python_version=${3:-}
build_binary_name=${4:-}
build_folder=${5:-}
openssl_version=${6:-}
mac_arch="$(uname -m)"
openssl_config_arch=""

# Set architecture to install openssl
if [ "$mac_arch" = "arm64" ]; then
    openssl_config_arch="darwin64-arm64-cc"
    export PATH=/usr/local/bin:"$PATH"
elif [ "$mac_arch" = "x86_64" ]; then
    openssl_config_arch="darwin64-x86_64-cc"
else
    echo "Invalid architecture found"
    exit 1
fi

if [ "$CI_OVERRIDE" = "1" ]; then
  build_folder="aws-sam-cli-beta"
  build_binary_name="sam-beta"
fi

if [ "$python_library_zip_filename" = "" ]; then
    python_library_zip_filename="python-libraries.zip";
fi

if [ "$openssl_version" = "" ]; then
    openssl_version="1.1.1o";
fi

if [ "$python_version" = "" ]; then
    python_version="3.8.13";
fi

if ! [ "$build_binary_name" = "" ]; then
    echo "Building native installer with nightly/beta build"
    is_nightly="true"
else
    echo "Building native installer with normal build"
    is_nightly="false"
fi

set -eux

echo "Making Folders"
mkdir -p .build/src
mkdir -p .build/output/aws-sam-cli-src
mkdir -p .build/output/python-libraries
mkdir -p .build/output/pyinstaller-output
cd .build

# Installing Openssl to allow pip configured in the TLS/SSL location to install python libraries
echo "Installing Openssl"
curl -LO https://www.openssl.org/source/openssl-"${openssl_version}".tar.gz
tar -xzf openssl-"${openssl_version}".tar.gz
cd openssl-"$openssl_version"
# Openssl configure https://wiki.openssl.org/index.php/Compilation_and_Installation
./Configure --prefix=/usr/local --openssldir=/usr/local/openssl no-ssl3 no-ssl3-method no-zlib ${openssl_config_arch} enable-ec_nistp_64_gcc_128

make
sudo make install
cd ..

# Copying aws-sam-cli source code
echo "Copying Source"
cp -r ../[!.]* ./src
cp -r ./src/* ./output/aws-sam-cli-src

echo "Removing CI Scripts"
rm -vf ./output/aws-sam-cli-src/appveyor*.yml

echo "Installing Python"
curl "https://www.python.org/ftp/python/${python_version}/Python-${python_version}.tgz" --output python.tgz
tar -xzf python.tgz
cd Python-"$python_version"
./configure --enable-shared
make -j8
sudo make install
cd ..

echo "Installing Python Libraries"
/usr/local/bin/python3.8 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r src/requirements/reproducible-mac.txt

echo "Copying All Python Libraries"
cp -r ./venv/lib/python*/site-packages/* ./output/python-libraries

echo "Installing PyInstaller"
./venv/bin/pip install -r src/requirements/pyinstaller-build.txt
./venv/bin/pip check

# Building the binary using pyinstaller
echo "Building Binary"
cd src
if [ "$is_nightly" = "true" ]; then
    # If nightly build, replace the exe_name in spec file with build_binary_name
    echo "Updating samcli-mac.spec with nightly/beta build"
    sed -i.bak "s/'sam'/'$build_binary_name'/g" installer/pyinstaller/samcli-mac.spec
    rm installer/pyinstaller/samcli-mac.spec.bak
fi
echo "samcli-mac.spec content is:"
cat installer/pyinstaller/samcli-mac.spec
# Note: onefile/onedir options are not valid when spec file is used on mac
../venv/bin/python -m PyInstaller --clean installer/pyinstaller/samcli-mac.spec

# Organizing the pyinstaller-output folder
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
    # If nightly build, replace the build folder and build_binary_name in the install script
    sed -i.bak "s/\/usr\/local\/aws-sam-cli/\/usr\/local\/$build_folder/g" pyinstaller-output/install
    sed -i.bak 's/EXE_NAME=\"sam\"/EXE_NAME=\"'"$build_binary_name"'\"/g' pyinstaller-output/install
    rm pyinstaller-output/install.bak
fi
echo "install script content is:"
cat pyinstaller-output/install
echo "Copying Binary"
cd ..
cp -r src/pyinstaller-output/* output/pyinstaller-output

echo "Packaging Binary"
cd output
cd pyinstaller-output
cd dist
cd ..
zip -r ../"$binary_zip_filename" ./*
cd ..
zip -r "$binary_zip_filename" aws-sam-cli-src

# Remove unwanted files and zip the python libraries
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
zip -r ../"$python_library_zip_filename" ./*
cd ..
zip -r "$python_library_zip_filename" aws-sam-cli-src

pyinstaller_zip_filename=$1
pyinstaller_package_foldername=$2
python_package_url=$3

if [ "$python_package_url" == "" ]; then
    python_package_url="https://www.python.org/ftp/python/3.7.9/Python-3.7.9.tgz";
fi

echo $python_package_url

yum install -y zlib-devel openssl-devel

echo "Making Folders"
mkdir -p .build/src
mkdir -p .build/output/src
mkdir -p .build/output/python-libraries
mkdir -p .build/output/pyinstaller-output
cd .build

echo "Copying Source"
#cp -r ../[^.]* ./src
#cp -r ./src/* ./output/src

echo "Installing Python"
curl $python_package_url --output python.tgz
tar -xzf python.tgz
cd Python*
./configure --enable-shared
make
make install
cd ..

echo "Installing Python Libraries"
python3 -m venv venv
./venv/bin/pip install -r src/requirements/reproducible-linux.txt

echo "Copying All Python Libraries"
#cp -r ./venv/lib/python*/site-packages/* ./output/python-libraries

echo "Installing PyInstaller"
./venv/bin/pip install -r src/requirements/pyinstaller-build.txt

echo "Building Binary"
cd src
../venv/bin/python -m PyInstaller -D --clean installer/pyinstaller/samcli.spec

mkdir pyinstaller-output

mv dist/sam pyinstaller-output/dist
cp installer/assets/install pyinstaller-output
chmod 755 pyinstaller-output/install

echo "Copying Binary"
cd ..
cp -r src/pyinstaller-output/* output/pyinstaller-output
#zip -r $PYINSTALLER_ZIP_FILENAME $pyinstaller_package_foldername
#mv $PYINSTALLER_ZIP_FILENAME ..
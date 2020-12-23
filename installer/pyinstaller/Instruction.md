Running build script
```
docker pull quay.io/pypa/manylinux2010_x86_64
docker run --mount type=bind,src="{Absolute path to AWS SAM CLI source}",dst="/aws-sam-cli" -it quay.io/pypa/manylinux2010_x86_64
cd aws-sam-cli
./installer/pyinstaller/build-linux.sh
```

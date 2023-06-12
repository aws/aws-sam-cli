Running build script
```
docker run --mount type=bind,src="{Absolute path to AWS SAM CLI source}",dst="/aws-sam-cli" -it quay.io/pypa/manylinux2014_x86_64
cd aws-sam-cli
./installer/pyinstaller/build-linux.sh aws-sam-cli-linux-x86_64.zip
```

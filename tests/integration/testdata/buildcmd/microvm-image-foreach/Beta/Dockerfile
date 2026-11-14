FROM python:3.12-slim
# Keep an instruction before COPY. With the classic builder and the containerd image store (the default for
# fresh Docker 29 installs, such as the Ubuntu 26.04 runners), a cross-platform build whose first instruction
# after FROM is COPY fails with "failed to export image: NotFound: content digest ... not found".
WORKDIR /app
COPY . /app

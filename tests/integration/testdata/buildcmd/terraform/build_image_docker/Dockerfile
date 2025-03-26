FROM public.ecr.aws/amazonlinux/amazonlinux:2

RUN yum -y update \
    && yum install -y unzip tar gzip ed less wget \
    && rm -rf /var/cache/yum

RUN yum -y groupinstall "Development Tools"

RUN yum -y install openssl-devel bzip2-devel libffi-devel

RUN yum install -y yum-utils \
    && yum-config-manager --add-repo https://rpm.releases.hashicorp.com/AmazonLinux/hashicorp.repo \
    && yum -y install terraform \
    && terraform --version

# AWS Lambda Builders
RUN cd /tmp \
    && wget https://www.python.org/ftp/python/3.9.17/Python-3.9.17.tgz \
    && tar xvf Python-3.9.17.tgz \
    && cd Python-3.9.17 \
    && ./configure --enable-optimizations \
    && make install

RUN python3 -m ensurepip
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install aws-lambda-builders
RUN python3 --version

VOLUME /project
WORKDIR /project

ENTRYPOINT ["sh"]



FROM public.ecr.aws/amazonlinux/amazonlinux:2023

RUN yum -y update \
    && yum install -y unzip tar gzip ed less \
    && rm -rf /var/cache/yum

RUN yum -y install make \
    && yum -y install zip

RUN yum install -y yum-utils \
    && yum-config-manager --add-repo https://rpm.releases.hashicorp.com/AmazonLinux/hashicorp.repo \
    && yum -y install terraform \
    && terraform --version

# AWS Lambda Builders
# AL2023 uses Python3.9 by default. This might fail in the future if that changes. We just need the proper version
RUN curl -L get-pip.io | python3.9
RUN pip3 install aws-lambda-builders
RUN python3 --version

VOLUME /project
WORKDIR /project

ENTRYPOINT ["sh"]



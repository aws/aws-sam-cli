FROM public.ecr.aws/lambda/python:3.6

ARG FUNCTION_DIR="/var/task"

RUN mkdir -p $FUNCTION_DIR

COPY main.py $FUNCTION_DIR

COPY __init__.py $FUNCTION_DIR



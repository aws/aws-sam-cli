ARG BASE_RUNTIME

FROM public.ecr.aws/lambda/python:$BASE_RUNTIME

ARG FUNCTION_DIR="/var/task"

RUN mkdir -p $FUNCTION_DIR

COPY main.py $FUNCTION_DIR

COPY requirements.txt $FUNCTION_DIR

RUN python -m pip install -r $FUNCTION_DIR/requirements.txt -t $FUNCTION_DIR
ARG BASE_RUNTIME

FROM public.ecr.aws/lambda/python:$BASE_RUNTIME

ARG FUNCTION_DIR="/var/task"

RUN mkdir -p $FUNCTION_DIR

COPY feature_phi/__init__.py $FUNCTION_DIR
COPY feature_phi/main.py $FUNCTION_DIR

COPY shared_code/ $FUNCTION_DIR/shared_code/

COPY requirements.txt $FUNCTION_DIR

RUN python -m pip install -r $FUNCTION_DIR/requirements.txt -t $FUNCTION_DIR


ARG BASE_RUNTIME

FROM public.ecr.aws/lambda/python:$BASE_RUNTIME

COPY myimage/main.py $FUNCTION_DIR

CMD [ "main.handler" ]
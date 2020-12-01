FROM public.ecr.aws/lambda/python:3.6

COPY app.py requirements.txt ./

RUN {{cookiecutter.runtime}} -m pip install -r requirements.txt -t .

# Command can be overwritten by providing a different command in the template directly.
CMD ["app.lambda_handler"]
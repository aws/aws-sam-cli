import requests


def handler(event, context):
    print(requests.__version__)
    return "Hello Mars"

import requests

def handler(event, context):
    return requests.__version__

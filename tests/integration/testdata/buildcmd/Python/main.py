import numpy

# from cryptography.fernet import Fernet
from jinja2 import Template


def handler(event, context):

    # Try using some of the modules to make sure they work & don't crash the process
    # print(Fernet.generate_key())

    template = Template("Hello {{ name }}")

    return {"pi": "{0:.2f}".format(numpy.pi), "jinja": template.render(name="World")}

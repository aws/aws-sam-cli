import numpy


# from cryptography.fernet import Fernet


def handler(event, context):
    # Try using some of the modules to make sure they work & don't crash the process
    # print(Fernet.generate_key())

    return {"pi": "{0:.2f}".format(numpy.pi)}


def first_function_handler(event, context):
    return "Hello World"


def second_function_handler(event, context):
    return "Hello Mars"

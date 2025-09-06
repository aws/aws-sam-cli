import numpy


def handler(event, context):
    return {"pi": "{0:.2f}".format(numpy.pi)}

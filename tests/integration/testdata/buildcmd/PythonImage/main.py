import numpy

def handler(event, context):
    return {"pi": "{0:.2f}".format(numpy.pi)}

def handler_two(event, context):
    return {"2pi": "{0:.2f}".format(numpy.pi * 2)}

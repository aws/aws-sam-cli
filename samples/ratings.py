import json

def handler(event, context):

    print("This is a log message from Python 3.6!")
    print("Event received ---> {}".format(event))
    return "Hello from Python 3.6!"
      

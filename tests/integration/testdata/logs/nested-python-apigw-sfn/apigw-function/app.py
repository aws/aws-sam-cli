
def handler(event, context):
    print("Hello world from HelloWorldServerlessApi/hello function")
    print("Hello world from ApiGwFunction function")
    print("this should be filtered ApiGwFunction")
    return {}

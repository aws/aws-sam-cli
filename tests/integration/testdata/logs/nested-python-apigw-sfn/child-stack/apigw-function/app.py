
def handler(event, context):
    print("Hello world from ChildStackHelloWorldServerlessApi/hello function")
    print("Hello world from ChildStack/ApiGwFunction function")
    print("this should be filtered ChildStackApiGwFunction")
    return {}

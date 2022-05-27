
def handler(event, context):
    print("Hello world from GrandChildStackHelloWorldServerlessApi/hello function")
    print("Hello world from ChildStack/GrandChildStack/ApiGwFunction function")
    print("this should be filtered ChildStack/GrandChildStack/ApiGwFunction")
    return {}

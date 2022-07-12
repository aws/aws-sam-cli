
def handler(event, context):
    print("Hello world from ChildStackGrandChildStackHelloWorldServerlessApi/hello function")
    print("Hello world from ChildStack/GrandChildStack/ApiGwFunction function")
    print("this should be filtered ChildStackGrandChildStackApiGwFunction")
    return {}

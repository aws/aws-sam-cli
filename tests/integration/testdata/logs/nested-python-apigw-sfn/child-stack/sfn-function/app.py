
def handler(event, context):
    print("Hello world from ChildStackHelloWorldServerlessApi/world function")
    print("Hello world from ChildStack/SfnFunction function")
    print("this should be filtered ChildStackSfnFunction")
    return {}

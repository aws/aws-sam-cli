
def handler(event, context):
    print("Hello world from SFN ChildStackHelloWorldServerlessApi/world function")
    print("Hello world from ChildStack/SfnFunction function")
    print("this should be filtered ChildStack/SfnFunction")
    return {}

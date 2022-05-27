
def handler(event, context):
    print("Hello world from SFN GrandChildStackHelloWorldServerlessApi/world function")
    print("Hello world from ChildStack/GrandChildStack/SfnFunction function")
    print("this should be filtered ChildStack/GrandChildStack/SfnFunction")
    return {}

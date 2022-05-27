
def handler(event, context):
    print("Hello world from HelloWorldServerlessApi/world function")
    print("Hello world from SfnFunction function")
    print("this should be filtered SfnFunction")
    return {}


def handler(event, context):
    print("Hello world from ChildStackGrandChildStackHelloWorldServerlessApi/world function")
    print("Hello world from ChildStack/GrandChildStack/SfnFunction function")
    print("this should be filtered ChildStackGrandChildStackSfnFunction")
    return {}


def handler(event, context):
    print("Hello world from ChildStack/GrandChildStack/FunctionWithCustomLoggingConfig function")
    print("this should be filtered ChildStackGrandChildStackFunctionWithCustomLoggingConfig")
    return {}

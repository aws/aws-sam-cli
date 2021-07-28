#!/usr/bin/env python3

from aws_cdk import core as cdk

# For consistency with TypeScript code, `cdk` is the preferred import name for
# the CDK's core module.  The following line also imports it as `core` for use
# with examples from the CDK Developer's Guide, which are in the process of
# being updated to use `cdk`.  You may delete this import if you don't need it.
from aws_cdk import core

from hello_cdk_nested_stacks.hello_cdk_nested_stacks_stack import (
    RootStack,
    HelloCdkNestedStacksStack,
    NestedNestedStack,
    Stack2,
)


app = core.App()

# root_stack = core.Stack(app, "R")
root_stack = RootStack(app, "root-stack")
nested_stack = HelloCdkNestedStacksStack(root_stack, "nested-stack")
nested_nested_stack = NestedNestedStack(nested_stack, "nested-nested-stack", lambda_role=nested_stack.lambda_role,)

stack2 = Stack2(app, "Stack2", lambda_role=nested_stack.lambda_role)

ca = app.synth()

# print(ca.manifest)

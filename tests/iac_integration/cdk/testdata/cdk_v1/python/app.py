#!/usr/bin/env python3
from aws_cdk import core

from python.python_stack import PythonStack


app = core.App()
PythonStack(app, "TestStack")

app.synth()

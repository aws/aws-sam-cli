#!/usr/bin/env python3
from aws_cdk import App

from python.python_stack import PythonStack


app = App()
PythonStack(app, "TestStack")

app.synth()

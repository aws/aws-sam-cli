"""
Fetch and print CloudFormation stack output
"""

import logging

import boto3

from samcli.lib.show.output import StackOutput


class ShowOutputContext:
    def __init__(self, stack_name):
        self._stack_name = stack_name
        self.output = StackOutput(boto3.client("cloudformation"))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def show(self, *args, **kwargs):
        if self.output.has_stack(self._stack_name):
            outputs = self.output.get_stack_outputs(self._stack_name, echo=False)
            if outputs:
                self.output.display_stack_outputs(outputs)

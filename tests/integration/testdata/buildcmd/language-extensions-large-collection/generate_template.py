#!/usr/bin/env python3
"""Generate a template with N ForEach items for performance testing."""

import sys


def generate(count=50):
    items = [f"func{i:03d}" for i in range(1, count + 1)]
    first = f"    - - {items[0]}"
    rest = "\n".join(f"      - {name}" for name in items[1:])
    collection = first + "\n" + rest
    print(f"""AWSTemplateFormatVersion: '2010-09-09'
Transform:
  - AWS::LanguageExtensions
  - AWS::Serverless-2016-10-31

Description: >
  TC-014: Large ForEach collection ({count} items).
  Performance test for large-scale ForEach expansion.

Parameters:
  Runtime:
    Type: String
    Default: python3.13

Globals:
  Function:
    Timeout: 10
    MemorySize: 128
    Runtime: !Ref Runtime

Resources:
  Fn::ForEach::Functions:
    - FunctionName
{collection}
    - ${{FunctionName}}Function:
        Type: AWS::Serverless::Function
        Properties:
          Handler: main.handler
          CodeUri: src/
          Environment:
            Variables:
              FUNCTION_NAME: !Sub ${{FunctionName}}""")


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    generate(count)

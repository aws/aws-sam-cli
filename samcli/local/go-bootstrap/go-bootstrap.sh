#!/bin/bash

export ORIGINAL_HANDLER=$AWS_LAMBDA_FUNCTION_HANDLER
export AWS_LAMBDA_FUNCTION_HANDLER=handler-wrapper.sh
/var/rapid/aws-lambda-rie --log-level error
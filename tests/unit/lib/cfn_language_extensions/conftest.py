"""
Pytest configuration and shared fixtures for cfn-language-extensions tests.
"""

import pytest


@pytest.fixture
def minimal_template():
    """A minimal valid CloudFormation template."""
    return {
        "Resources": {
            "MyResource": {
                "Type": "AWS::SQS::Queue",
            }
        }
    }


@pytest.fixture
def template_with_parameters():
    """A template with parameters for testing parameter resolution."""
    return {
        "Parameters": {
            "Environment": {
                "Type": "String",
                "Default": "dev",
            },
            "InstanceCount": {
                "Type": "Number",
                "Default": 1,
            },
        },
        "Resources": {
            "MyResource": {
                "Type": "AWS::SQS::Queue",
                "Properties": {
                    "QueueName": {"Ref": "Environment"},
                },
            }
        },
    }


@pytest.fixture
def template_with_mappings():
    """A template with mappings for testing Fn::FindInMap."""
    return {
        "Mappings": {
            "RegionMap": {
                "us-east-1": {
                    "AMI": "ami-12345678",
                    "InstanceType": "t2.micro",
                },
                "us-west-2": {
                    "AMI": "ami-87654321",
                    "InstanceType": "t2.small",
                },
            }
        },
        "Resources": {
            "MyResource": {
                "Type": "AWS::EC2::Instance",
                "Properties": {
                    "ImageId": {"Fn::FindInMap": ["RegionMap", "us-east-1", "AMI"]},
                },
            }
        },
    }


@pytest.fixture
def template_with_conditions():
    """A template with conditions for testing condition resolution."""
    return {
        "Parameters": {
            "Environment": {
                "Type": "String",
                "Default": "dev",
            },
        },
        "Conditions": {
            "IsProd": {"Fn::Equals": [{"Ref": "Environment"}, "prod"]},
        },
        "Resources": {
            "MyResource": {
                "Type": "AWS::SQS::Queue",
                "Condition": "IsProd",
            }
        },
    }

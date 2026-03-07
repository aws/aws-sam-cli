"""
Unit tests for Fn::ForEach support in SamTranslatorWrapper and shared foreach_handler utility
"""
import copy
from unittest import TestCase

from samcli.lib.samlib.wrapper import SamTranslatorWrapper
from samcli.lib.utils.foreach_handler import filter_foreach_constructs


class TestFilterForEachConstructs(TestCase):
    """Test the _filter_foreach_constructs static method"""

    def test_filters_foreach_from_regular_resources(self):
        """Verify Fn::ForEach constructs are filtered out while regular resources remain"""
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Topics": [
                    "TopicName",
                    ["Success", "Failure"],
                    {"SnsTopic${TopicName}": {"Type": "AWS::SNS::Topic"}},
                ],
                "RegularFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"Handler": "app.handler"},
                },
                "AnotherResource": {"Type": "AWS::S3::Bucket", "Properties": {}},
            },
        }

        filtered, foreach = filter_foreach_constructs(template)

        # Regular resources should remain
        self.assertIn("RegularFunction", filtered["Resources"])
        self.assertIn("AnotherResource", filtered["Resources"])

        # ForEach should be removed
        self.assertNotIn("Fn::ForEach::Topics", filtered["Resources"])

        # ForEach should be in separate dict
        self.assertIn("Fn::ForEach::Topics", foreach)
        self.assertEqual(len(foreach), 1)

    def test_adds_placeholder_when_only_foreach(self):
        """Verify placeholder resource is added when template only has ForEach"""
        template = {
            "Resources": {
                "Fn::ForEach::OnlyThis": [
                    "Item",
                    ["A", "B"],
                    {"Resource${Item}": {"Type": "AWS::SNS::Topic"}},
                ]
            }
        }

        filtered, foreach = filter_foreach_constructs(template)

        # Placeholder should be added
        self.assertIn("__PlaceholderForForEachOnly", filtered["Resources"])
        self.assertEqual(
            filtered["Resources"]["__PlaceholderForForEachOnly"]["Type"],
            "AWS::CloudFormation::WaitConditionHandle",
        )

        # ForEach should be in separate dict
        self.assertIn("Fn::ForEach::OnlyThis", foreach)

    def test_preserves_multiple_foreach_constructs(self):
        """Verify multiple Fn::ForEach constructs are all filtered and preserved"""
        template = {
            "Resources": {
                "Fn::ForEach::Topics": ["X", ["A"], {"T${X}": {"Type": "AWS::SNS::Topic"}}],
                "Fn::ForEach::Functions": ["Y", ["B"], {"F${Y}": {"Type": "AWS::Lambda::Function"}}],
                "Fn::ForEach::Queues": ["Z", ["C"], {"Q${Z}": {"Type": "AWS::SQS::Queue"}}],
                "RegularResource": {"Type": "AWS::S3::Bucket"},
            }
        }

        filtered, foreach = filter_foreach_constructs(template)

        # Regular resource remains
        self.assertIn("RegularResource", filtered["Resources"])

        # All ForEach removed from filtered
        self.assertNotIn("Fn::ForEach::Topics", filtered["Resources"])
        self.assertNotIn("Fn::ForEach::Functions", filtered["Resources"])
        self.assertNotIn("Fn::ForEach::Queues", filtered["Resources"])

        # All ForEach in separate dict
        self.assertEqual(len(foreach), 3)
        self.assertIn("Fn::ForEach::Topics", foreach)
        self.assertIn("Fn::ForEach::Functions", foreach)
        self.assertIn("Fn::ForEach::Queues", foreach)

    def test_handles_empty_resources_dict(self):
        """Verify handling of template with empty Resources dict"""
        template = {"Resources": {}}

        filtered, foreach = filter_foreach_constructs(template)

        # Should return empty foreach dict
        self.assertEqual(foreach, {})
        # Resources should still be empty dict
        self.assertEqual(filtered["Resources"], {})

    def test_handles_template_with_no_foreach(self):
        """Verify normal templates without ForEach are unchanged"""
        template = {
            "Resources": {
                "Function1": {"Type": "AWS::Serverless::Function"},
                "Bucket1": {"Type": "AWS::S3::Bucket"},
            }
        }

        original = copy.deepcopy(template)
        filtered, foreach = filter_foreach_constructs(template)

        # No ForEach found
        self.assertEqual(foreach, {})

        # Resources unchanged
        self.assertEqual(filtered["Resources"], original["Resources"])

    def test_foreach_with_complex_structure(self):
        """Test ForEach with nested intrinsic functions"""
        template = {
            "Parameters": {"EnvNames": {"Type": "CommaDelimitedList"}},
            "Resources": {
                "Fn::ForEach::ComplexFunctions": [
                    "Env",
                    {"Ref": "EnvNames"},  # Ref in iterator
                    {
                        "Function${Env}": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "FunctionName": {"Fn::Sub": "func-${Env}"},  # Sub in properties
                            },
                        }
                    },
                ]
            }
        }

        filtered, foreach = filter_foreach_constructs(template)

        # ForEach should be preserved with all its complexity
        self.assertIn("Fn::ForEach::ComplexFunctions", foreach)
        self.assertEqual(foreach["Fn::ForEach::ComplexFunctions"][1], {"Ref": "EnvNames"})

    def test_function_uses_deepcopy_internally(self):
        """Verify the function uses deepcopy so original is not directly modified"""
        template = {
            "Resources": {
                "Fn::ForEach::Items": ["X", ["A"], {"R${X}": {"Type": "AWS::SNS::Topic"}}],
                "RegularResource": {"Type": "AWS::S3::Bucket"},
            }
        }

        template_id_before = id(template["Resources"])
        filtered, foreach = filter_foreach_constructs(template)
        
        # The filtered template should be a different object
        self.assertNotEqual(id(filtered["Resources"]), template_id_before)
        
        # Foreach should contain the ForEach construct
        self.assertIn("Fn::ForEach::Items", foreach)
        
        # Filtered should not contain ForEach
        self.assertNotIn("Fn::ForEach::Items", filtered["Resources"])

    def test_foreach_detection_is_prefix_based(self):
        """Verify detection uses startswith, not exact match"""
        template = {
            "Resources": {
                "Fn::ForEach::TopicsV1": ["X", ["A"], {}],
                "Fn::ForEach::Functions": ["Y", ["B"], {}],
                "NotForEach": {"Type": "AWS::S3::Bucket"},
            }
        }

        filtered, foreach = filter_foreach_constructs(template)

        # Both ForEach variants detected
        self.assertEqual(len(foreach), 2)
        self.assertIn("Fn::ForEach::TopicsV1", foreach)
        self.assertIn("Fn::ForEach::Functions", foreach)


class TestForEachEdgeCases(TestCase):
    """Test edge cases and error conditions"""

    def test_foreach_with_empty_collection(self):
        """Test ForEach with empty list"""
        template = {"Resources": {"Fn::ForEach::Empty": ["X", [], {"R${X}": {"Type": "AWS::SNS::Topic"}}]}}

        filtered, foreach = filter_foreach_constructs(template)

        # Should still be filtered (CloudFormation will handle empty list)
        self.assertIn("Fn::ForEach::Empty", foreach)
        self.assertIn("__PlaceholderForForEachOnly", filtered["Resources"])

    def test_resource_named_starting_with_foreach_but_is_dict(self):
        """Test resource that starts with 'Fn::ForEach' but is a regular resource dict"""
        template = {
            "Resources": {
                "Fn::ForEach::MyCustomName": {  # Dict, not list - unusual naming
                    "Type": "AWS::Serverless::Function",
                    "Properties": {},
                }
            }
        }

        filtered, foreach = filter_foreach_constructs(template)

        # Current implementation filters by prefix, so this would be filtered
        # This is acceptable - users shouldn't name resources like this
        self.assertIn("Fn::ForEach::MyCustomName", foreach)

    def test_mixed_resources_preserves_correct_ones(self):
        """Test complex mix of ForEach and regular resources"""
        template = {
            "Resources": {
                "Bucket1": {"Type": "AWS::S3::Bucket"},
                "Fn::ForEach::Set1": ["A", ["1"], {}],
                "Function1": {"Type": "AWS::Serverless::Function"},
                "Fn::ForEach::Set2": ["B", ["2"], {}],
                "Table1": {"Type": "AWS::DynamoDB::Table"},
                "Fn::ForEach::Set3": ["C", ["3"], {}],
            }
        }

        filtered, foreach = filter_foreach_constructs(template)

        # 3 regular resources
        self.assertEqual(len(filtered["Resources"]), 3)
        self.assertIn("Bucket1", filtered["Resources"])
        self.assertIn("Function1", filtered["Resources"])
        self.assertIn("Table1", filtered["Resources"])

        # 3 ForEach constructs
        self.assertEqual(len(foreach), 3)

    def test_foreach_structure_is_preserved_exactly(self):
        """Verify ForEach structure is not modified during filtering"""
        original_foreach = [
            "EnvName",
            {"Ref": "Environments"},
            {
                "Topic${EnvName}": {
                    "Type": "AWS::SNS::Topic",
                    "Properties": {"TopicName": {"Fn::Sub": "topic-${EnvName}"}},
                }
            },
        ]

        template = {"Resources": {"Fn::ForEach::Topics": copy.deepcopy(original_foreach)}}

        _, foreach = filter_foreach_constructs(template)

        # Structure should be identical
        self.assertEqual(foreach["Fn::ForEach::Topics"], original_foreach)

    def test_foreach_with_malformed_structure(self):
        """Test ForEach with unexpected structure"""
        template = {
            "Resources": {
                "Fn::ForEach::Malformed": "not-a-list",  # Should be list, but isn't
                "RegularResource": {"Type": "AWS::S3::Bucket"},
            }
        }

        filtered, foreach = filter_foreach_constructs(template)

        # Malformed ForEach should still be filtered (by prefix)
        self.assertIn("Fn::ForEach::Malformed", foreach)
        self.assertIn("RegularResource", filtered["Resources"])


class TestForEachWithTransforms(TestCase):
    """Test ForEach with different Transform configurations"""

    def test_with_language_extensions_only(self):
        """Test with only LanguageExtensions transform"""
        template = {
            "Transform": "AWS::LanguageExtensions",
            "Resources": {"Fn::ForEach::Items": ["X", ["A"], {}]},
        }

        filtered, foreach = filter_foreach_constructs(template)

        # Should still work
        self.assertIn("Fn::ForEach::Items", foreach)

    def test_with_serverless_only_no_foreach(self):
        """Test normal Serverless template without LanguageExtensions"""
        template = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {"Function1": {"Type": "AWS::Serverless::Function"}},
        }

        filtered, foreach = filter_foreach_constructs(template)

        # No ForEach in Serverless-only template
        self.assertEqual(foreach, {})
        self.assertIn("Function1", filtered["Resources"])

    def test_with_both_transforms_in_list(self):
        """Test with list of transforms (correct usage)"""
        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Items": ["X", ["A"], {}],
                "Function1": {"Type": "AWS::Serverless::Function"},
            },
        }

        filtered, foreach = filter_foreach_constructs(template)

        self.assertEqual(len(foreach), 1)
        self.assertIn("Function1", filtered["Resources"])


class TestForEachRealWorldScenarios(TestCase):
    """Test real-world scenarios from issue #5647"""

    def test_multi_tenant_lambda_functions(self):
        """Test multi-tenant use case - multiple tenant functions"""
        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Parameters": {"Tenants": {"Type": "CommaDelimitedList", "Default": "tenant1,tenant2"}},
            "Resources": {
                "Fn::ForEach::TenantFunctions": [
                    "TenantId",
                    {"Fn::Split": [",", {"Ref": "Tenants"}]},
                    {
                        "${TenantId}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "FunctionName": {"Fn::Sub": "${TenantId}-processor"},
                                "Handler": "app.handler",
                                "Runtime": "python3.11",
                            },
                        }
                    },
                ]
            },
        }

        filtered, foreach = filter_foreach_constructs(template)

        # ForEach should be filtered
        self.assertIn("Fn::ForEach::TenantFunctions", foreach)
        # Placeholder added since no other resources
        self.assertIn("__PlaceholderForForEachOnly", filtered["Resources"])

    def test_sns_topics_from_issue_example(self):
        """Test original issue #5647 example"""
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Topics": [
                    "TopicName",
                    ["Success", "Failure", "Timeout", "Unknown"],
                    {
                        "SnsTopic${TopicName}": {
                            "Type": "AWS::SNS::Topic",
                            "Properties": {"TopicName": {"Ref": "TopicName"}, "FifoTopic": True},
                        }
                    },
                ]
            },
        }

        filtered, foreach = filter_foreach_constructs(template)

        # This should not crash (was the original bug)
        self.assertIn("Fn::ForEach::Topics", foreach)
        self.assertEqual(foreach["Fn::ForEach::Topics"][1], ["Success", "Failure", "Timeout", "Unknown"])

    def test_iam_policy_statements_foreach(self):
        """Test IAM policy use case - ForEach inside Policies (not top-level)"""
        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Parameters": {"BucketNames": {"Type": "CommaDelimitedList"}},
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Policies": {
                            "Fn::ForEach::S3Access": [
                                "BucketName",
                                {"Ref": "BucketNames"},
                                {
                                    "Statement": [
                                        {
                                            "Effect": "Allow",
                                            "Action": "s3:GetObject",
                                            "Resource": {"Fn::Sub": "arn:aws:s3:::${BucketName}/*"},
                                        }
                                    ]
                                },
                            ]
                        }
                    },
                }
            },
        }

        filtered, foreach = filter_foreach_constructs(template)

        # Regular function should remain
        self.assertIn("MyFunction", filtered["Resources"])
        # No top-level ForEach in this case (ForEach is inside Policies)
        self.assertEqual(len(foreach), 0)
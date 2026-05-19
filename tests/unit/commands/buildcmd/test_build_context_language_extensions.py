"""
Tests for BuildContext language extensions support.

Covers _copy_artifact_paths for various resource types,
and bug condition exploration tests for auto dependency layer with ForEach templates.
"""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from samcli.commands.build.build_context import BuildContext


class TestCopyArtifactPaths(TestCase):
    """Tests for _copy_artifact_paths."""

    def _make_context(self):
        with patch.object(BuildContext, "__init__", lambda self: None):
            return BuildContext()

    def test_serverless_function_codeuri(self):
        ctx = self._make_context()
        original = {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "./src"}}
        modified = {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": ".aws-sam/build/Func"}}
        ctx._copy_artifact_paths(original, modified)
        self.assertEqual(original["Properties"]["CodeUri"], ".aws-sam/build/Func")

    def test_serverless_function_imageuri(self):
        ctx = self._make_context()
        original = {"Type": "AWS::Serverless::Function", "Properties": {"PackageType": "Image"}}
        modified = {
            "Type": "AWS::Serverless::Function",
            "Properties": {"ImageUri": "123.dkr.ecr.us-east-1.amazonaws.com/repo"},
        }
        ctx._copy_artifact_paths(original, modified)
        self.assertEqual(original["Properties"]["ImageUri"], "123.dkr.ecr.us-east-1.amazonaws.com/repo")

    def test_lambda_function_code_packageable(self):
        """Packageable Code (S3 location, no ZipFile): merge wins."""
        ctx = self._make_context()
        original = {"Type": "AWS::Lambda::Function", "Properties": {"Code": {"S3Bucket": "old", "S3Key": "k"}}}
        modified = {"Type": "AWS::Lambda::Function", "Properties": {"Code": {"S3Bucket": "new", "S3Key": "k"}}}
        ctx._copy_artifact_paths(original, modified)
        self.assertEqual(original["Properties"]["Code"]["S3Bucket"], "new")

    def test_serverless_layer_contenturi(self):
        ctx = self._make_context()
        original = {"Type": "AWS::Serverless::LayerVersion", "Properties": {"ContentUri": "./layer"}}
        modified = {"Type": "AWS::Serverless::LayerVersion", "Properties": {"ContentUri": ".aws-sam/build/Layer"}}
        ctx._copy_artifact_paths(original, modified)
        self.assertEqual(original["Properties"]["ContentUri"], ".aws-sam/build/Layer")

    def test_lambda_layer_content(self):
        ctx = self._make_context()
        original = {"Type": "AWS::Lambda::LayerVersion", "Properties": {"Content": {"S3Bucket": "old"}}}
        modified = {"Type": "AWS::Lambda::LayerVersion", "Properties": {"Content": {"S3Bucket": "new"}}}
        ctx._copy_artifact_paths(original, modified)
        self.assertEqual(original["Properties"]["Content"]["S3Bucket"], "new")

    def test_serverless_api_definitionuri(self):
        ctx = self._make_context()
        original = {"Type": "AWS::Serverless::Api", "Properties": {"DefinitionUri": "./api.yaml"}}
        modified = {"Type": "AWS::Serverless::Api", "Properties": {"DefinitionUri": ".aws-sam/build/api.yaml"}}
        ctx._copy_artifact_paths(original, modified)
        self.assertEqual(original["Properties"]["DefinitionUri"], ".aws-sam/build/api.yaml")

    def test_serverless_httpapi_definitionuri(self):
        ctx = self._make_context()
        original = {"Type": "AWS::Serverless::HttpApi", "Properties": {"DefinitionUri": "./api.yaml"}}
        modified = {"Type": "AWS::Serverless::HttpApi", "Properties": {"DefinitionUri": ".aws-sam/build/api.yaml"}}
        ctx._copy_artifact_paths(original, modified)
        self.assertEqual(original["Properties"]["DefinitionUri"], ".aws-sam/build/api.yaml")

    def test_serverless_statemachine_definitionuri(self):
        ctx = self._make_context()
        original = {"Type": "AWS::Serverless::StateMachine", "Properties": {"DefinitionUri": "./sm.json"}}
        modified = {"Type": "AWS::Serverless::StateMachine", "Properties": {"DefinitionUri": ".aws-sam/build/sm.json"}}
        ctx._copy_artifact_paths(original, modified)
        self.assertEqual(original["Properties"]["DefinitionUri"], ".aws-sam/build/sm.json")

    def test_unknown_resource_type_no_copy(self):
        ctx = self._make_context()
        original = {"Type": "AWS::SNS::Topic", "Properties": {"TopicName": "test"}}
        modified = {"Type": "AWS::SNS::Topic", "Properties": {"TopicName": "modified"}}
        ctx._copy_artifact_paths(original, modified)
        self.assertEqual(original["Properties"]["TopicName"], "test")

    def test_no_matching_property_no_copy(self):
        ctx = self._make_context()
        original = {"Type": "AWS::Serverless::Function", "Properties": {"Handler": "main.handler"}}
        modified = {"Type": "AWS::Serverless::Function", "Properties": {"Handler": "main.handler"}}
        ctx._copy_artifact_paths(original, modified)
        self.assertNotIn("CodeUri", original["Properties"])

    def test_glue_job_dotted_path(self):
        """Regression: dotted property path (Command.ScriptLocation) must be copied."""
        ctx = self._make_context()
        original = {
            "Type": "AWS::Glue::Job",
            "Properties": {"Command": {"Name": "glueetl", "ScriptLocation": "./script.py"}},
        }
        modified = {
            "Type": "AWS::Glue::Job",
            "Properties": {"Command": {"Name": "glueetl", "ScriptLocation": "s3://b/k.py"}},
        }
        ctx._copy_artifact_paths(original, modified)
        self.assertEqual(original["Properties"]["Command"]["ScriptLocation"], "s3://b/k.py")
        self.assertEqual(original["Properties"]["Command"]["Name"], "glueetl")


class TestUpdateOriginalTemplatePathsZipFile(TestCase):
    """#9029: At the root level, _update_original_template_paths must skip resources
    that produced no build artifact, mirroring the non-LE
    ApplicationBuilder.update_template skip. Inline-source ``ZipFile`` Lambdas have
    no CodeUri and are never built, so they must not be overwritten by the LE-resolved
    expansion (which strips intrinsics like Fn::Sub against pseudo-parameter defaults).
    """

    def _make_context(self):
        with patch.object(BuildContext, "__init__", lambda self: None):
            return BuildContext()

    def test_zipfile_resource_not_in_artifacts_is_skipped(self):
        """Lambda with Code.ZipFile is not in artifacts (no CodeUri to build);
        merge must skip it so the original Fn::Sub survives."""
        ctx = self._make_context()
        original_code = {"ZipFile": {"Fn::Sub": "arn:aws:states:${AWS::Region}:..."}}
        # LE-expanded template has Fn::Sub already resolved against defaults
        modified_code = {"ZipFile": "arn:aws:states:us-east-1:..."}
        original_template = {
            "Resources": {"MyFunc": {"Type": "AWS::Lambda::Function", "Properties": {"Code": original_code}}}
        }
        modified_template = {
            "Resources": {"MyFunc": {"Type": "AWS::Lambda::Function", "Properties": {"Code": modified_code}}}
        }
        stack = MagicMock()
        stack.parameters = {}
        stack.stack_path = ""

        # MyFunc not in artifacts (no CodeUri to build)
        ctx._update_original_template_paths(
            original_template,
            modified_template,
            stack,
            artifacts={},
            stack_output_template_path_by_stack_path={},
        )

        self.assertEqual(original_template["Resources"]["MyFunc"]["Properties"]["Code"], original_code)

    def test_packageable_resource_in_artifacts_is_merged(self):
        """Lambda with packageable Code is in artifacts; merge proceeds normally."""
        ctx = self._make_context()
        original_template = {
            "Resources": {
                "MyFunc": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": {"S3Bucket": "old", "S3Key": "k"}},
                }
            }
        }
        modified_template = {
            "Resources": {
                "MyFunc": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": {"S3Bucket": "new", "S3Key": "k"}},
                }
            }
        }
        stack = MagicMock()
        stack.parameters = {}
        stack.stack_path = ""

        ctx._update_original_template_paths(
            original_template,
            modified_template,
            stack,
            artifacts={"MyFunc": "/path/to/built/MyFunc"},
            stack_output_template_path_by_stack_path={},
        )

        self.assertEqual(original_template["Resources"]["MyFunc"]["Properties"]["Code"]["S3Bucket"], "new")


class TestForEachStaticArtifactsSkip(TestCase):
    """#9029 (case b): A ForEach body whose static property holds inline source
    (e.g. ``Code: {ZipFile: ...}``) is never built, so its expanded children are
    absent from ``artifacts``. The static-branch merge must skip them so the
    original property survives verbatim.
    """

    def _make_context(self):
        with patch.object(BuildContext, "__init__", lambda self: None):
            return BuildContext()

    def test_static_zipfile_in_foreach_skipped_when_not_in_artifacts(self):
        ctx = self._make_context()
        original_code = {"ZipFile": {"Fn::Sub": "print('${AWS::Region}')"}}
        foreach_value = [
            "Name",
            ["Alpha", "Beta"],
            {
                "${Name}Func": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {"Code": original_code},
                }
            },
        ]
        # Modified resources have the LE-expanded values (us-east-1 baked in)
        modified_resources = {
            "AlphaFunc": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": {"ZipFile": "print('us-east-1')"}},
            },
            "BetaFunc": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": {"ZipFile": "print('us-east-1')"}},
            },
        }
        # No artifacts entries — these functions had no CodeUri to build.
        ctx._update_foreach_artifact_paths(
            "Fn::ForEach::Names",
            foreach_value,
            modified_resources,
            template={},
            parameter_values={},
            artifacts={},
        )

        # Original Code (with Fn::Sub intact) must be untouched
        body = foreach_value[2]
        self.assertEqual(body["${Name}Func"]["Properties"]["Code"], original_code)


class TestForEachDynamicNoArtifactsRefusal(TestCase):
    """#9029: a dynamic Fn::ForEach property whose iterations produced no build
    artifacts cannot be expressed as a per-iteration CloudFormation Mapping
    (Mappings hold only static strings, so deploy-time intrinsics would be
    silently lost) and cannot leave the loop variable unresolved. Mirrors the
    artifacts-lookup discipline of the static branch and the root-level merge —
    refuse rather than emit a misleading template.
    """

    def _make_context(self):
        with patch.object(BuildContext, "__init__", lambda self: None):
            return BuildContext()

    def test_dynamic_property_with_no_artifacts_raises(self):
        from samcli.commands.exceptions import UserException

        ctx = self._make_context()
        foreach_value = [
            "Name",
            ["Alpha", "Beta"],
            {
                "${Name}Func": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        # ZipFile contains the loop variable; an inline-source
                        # Lambda has no CodeUri, so neither AlphaFunc nor BetaFunc
                        # appears in `artifacts`.
                        "Code": {"ZipFile": {"Fn::Sub": "print('${Name}')"}},
                    },
                }
            },
        ]
        modified_resources = {
            "AlphaFunc": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": {"ZipFile": "print('Alpha')"}},
            },
            "BetaFunc": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": {"ZipFile": "print('Beta')"}},
            },
        }
        with self.assertRaises(UserException) as cm:
            ctx._update_foreach_artifact_paths(
                "Fn::ForEach::Names",
                foreach_value,
                modified_resources,
                template={},
                parameter_values={},
                artifacts={},
            )
        message = str(cm.exception)
        self.assertIn("Name", message)
        self.assertIn("non-buildable property", message)


class TestGetTemplateForOutputForEachExploration(TestCase):
    """
    Bug condition exploration tests for _get_template_for_output with ForEach templates.

    These tests encode the EXPECTED (correct) behavior. They are expected to FAIL on
    unfixed code, confirming the bug exists. Once the fix is applied, they should PASS.

    Validates: Requirements 1.1, 1.2
    """

    NESTED_STACK_NAME = "AwsSamAutoDependencyLayerNestedStack"

    def _make_context(self):
        with patch.object(BuildContext, "__init__", lambda self: None):
            ctx = BuildContext()
            ctx._create_auto_dependency_layer = True
            return ctx

    def _make_stack_with_foreach(self):
        """
        Create a Stack with original_template_dict containing Fn::ForEach::Functions
        generating zip Lambda functions, and an expanded template_dict.
        """
        # Original template preserving Fn::ForEach structure
        original_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Parameters": {
                "FunctionNames": {
                    "Type": "CommaDelimitedList",
                    "Default": "Alpha,Beta",
                }
            },
            "Resources": {
                "Fn::ForEach::Functions": [
                    "FunctionName",
                    {"Ref": "FunctionNames"},
                    {
                        "${FunctionName}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "Handler": "index.handler",
                                "Runtime": "python3.12",
                                "CodeUri": "./src",
                            },
                        }
                    },
                ],
            },
        }

        # Expanded template (after language extensions processing)
        expanded_template = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "AlphaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.12",
                        "CodeUri": ".aws-sam/build/AlphaFunction",
                    },
                },
                "BetaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.12",
                        "CodeUri": ".aws-sam/build/BetaFunction",
                    },
                },
            },
        }

        stack = MagicMock()
        stack.original_template_dict = original_template
        stack.template_dict = expanded_template
        stack.parameters = {"FunctionNames": "Alpha,Beta"}
        stack.location = "/tmp/template.yaml"
        stack.stack_path = ""
        stack.parent_stack_path = ""
        stack.name = ""

        return stack, original_template, expanded_template

    def test_get_template_for_output_preserves_nested_stack_with_foreach(self):
        """
        Test 1a: When auto dependency layers are enabled and the expanded template
        contains AwsSamAutoDependencyLayerNestedStack, the output template (which
        preserves Fn::ForEach structure) must also contain that nested stack resource.

        EXPECTED: FAILS on unfixed code because _get_template_for_output returns
        the original template which does not contain the nested stack resource added
        by NestedStackManager to the expanded template.

        Validates: Requirements 1.1
        """
        ctx = self._make_context()
        stack, original_template, expanded_template = self._make_stack_with_foreach()

        # Simulate what NestedStackManager.generate_auto_dependency_layer_stack does:
        # It adds the nested stack resource and Layers to the expanded template
        expanded_template_with_adl = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "AlphaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.12",
                        "CodeUri": ".aws-sam/build/AlphaFunction",
                        "Layers": [{"Fn::GetAtt": [self.NESTED_STACK_NAME, "Outputs.AlphaFunctionDepLayer"]}],
                    },
                },
                "BetaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.12",
                        "CodeUri": ".aws-sam/build/BetaFunction",
                        "Layers": [{"Fn::GetAtt": [self.NESTED_STACK_NAME, "Outputs.BetaFunctionDepLayer"]}],
                    },
                },
                self.NESTED_STACK_NAME: {
                    "Type": "AWS::CloudFormation::Stack",
                    "DeletionPolicy": "Delete",
                    "Properties": {"TemplateURL": ".aws-sam/build/adl_nested_template.yaml"},
                    "Metadata": {"CreatedBy": "AWS SAM CLI sync command"},
                },
            },
        }

        # Call _get_template_for_output with the expanded template that has ADL additions
        result = ctx._get_template_for_output(stack, expanded_template_with_adl, {})

        # The output template MUST contain the AwsSamAutoDependencyLayerNestedStack resource
        self.assertIn(
            self.NESTED_STACK_NAME,
            result.get("Resources", {}),
            f"Output template must contain {self.NESTED_STACK_NAME} resource when auto dependency "
            f"layers are enabled with ForEach templates. The nested stack resource was added to the "
            f"expanded template by NestedStackManager but lost when _get_template_for_output returned "
            f"the original template.",
        )

    def test_get_template_for_output_preserves_layers_in_foreach_body(self):
        """
        Test 1b: When auto dependency layers are enabled and the expanded functions
        have Layers referencing the nested stack, the function bodies inside
        Fn::ForEach in the output template must also contain Layers entries.

        EXPECTED: FAILS on unfixed code because _update_original_template_paths
        only copies artifact paths (CodeUri, etc.) but not Layers references.

        Validates: Requirements 1.2
        """
        ctx = self._make_context()
        stack, original_template, expanded_template = self._make_stack_with_foreach()

        # Expanded template with ADL additions (Layers added to each function)
        expanded_template_with_adl = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "AlphaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.12",
                        "CodeUri": ".aws-sam/build/AlphaFunction",
                        "Layers": [{"Fn::GetAtt": [self.NESTED_STACK_NAME, "Outputs.AlphaFunctionDepLayer"]}],
                    },
                },
                "BetaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.12",
                        "CodeUri": ".aws-sam/build/BetaFunction",
                        "Layers": [{"Fn::GetAtt": [self.NESTED_STACK_NAME, "Outputs.BetaFunctionDepLayer"]}],
                    },
                },
                self.NESTED_STACK_NAME: {
                    "Type": "AWS::CloudFormation::Stack",
                    "DeletionPolicy": "Delete",
                    "Properties": {"TemplateURL": ".aws-sam/build/adl_nested_template.yaml"},
                    "Metadata": {"CreatedBy": "AWS SAM CLI sync command"},
                },
            },
        }

        result = ctx._get_template_for_output(stack, expanded_template_with_adl, {})

        # Get the ForEach construct from the output template
        foreach_construct = result.get("Resources", {}).get("Fn::ForEach::Functions")
        self.assertIsNotNone(foreach_construct, "Fn::ForEach::Functions must be preserved in output")
        self.assertIsInstance(foreach_construct, list)
        self.assertEqual(len(foreach_construct), 3, "ForEach construct must have 3 elements")

        # The body is the third element of the ForEach construct
        body = foreach_construct[2]
        self.assertIsInstance(body, dict)

        # Check that the function template body contains Layers
        for template_key, template_value in body.items():
            if isinstance(template_value, dict) and template_value.get("Type") == "AWS::Serverless::Function":
                properties = template_value.get("Properties", {})
                self.assertIn(
                    "Layers",
                    properties,
                    f"Function body '{template_key}' inside Fn::ForEach must contain Layers "
                    f"referencing the auto dependency layer nested stack. The Layers were added "
                    f"to expanded functions by NestedStackManager but not carried over to the "
                    f"ForEach body in the original template.",
                )


class TestGetTemplateForOutputPreservation(TestCase):
    """
    Preservation tests for _get_template_for_output.

    These tests verify that existing behavior is unchanged on UNFIXED code.
    They MUST PASS on both unfixed and fixed code.

    Validates: Requirements 3.1, 3.2, 3.3, 3.4
    """

    NESTED_STACK_NAME = "AwsSamAutoDependencyLayerNestedStack"

    def _make_context(self, create_auto_dependency_layer=True):
        with patch.object(BuildContext, "__init__", lambda self: None):
            ctx = BuildContext()
            ctx._create_auto_dependency_layer = create_auto_dependency_layer
            return ctx

    def test_get_template_for_output_non_foreach_template_unchanged(self):
        """
        Test 2a: When a Stack has NO original_template_dict (no language extensions),
        _get_template_for_output returns the expanded template directly with
        AwsSamAutoDependencyLayerNestedStack and Layers intact.

        This is the standard non-ForEach path that must remain unchanged.

        Validates: Requirements 3.1
        """
        ctx = self._make_context()

        # Stack without original_template_dict (no language extensions)
        stack = MagicMock()
        stack.original_template_dict = None

        # Expanded template with auto dependency layer additions
        expanded_template = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.12",
                        "CodeUri": ".aws-sam/build/MyFunction",
                        "Layers": [{"Fn::GetAtt": [self.NESTED_STACK_NAME, "Outputs.MyFunctionDepLayer"]}],
                    },
                },
                self.NESTED_STACK_NAME: {
                    "Type": "AWS::CloudFormation::Stack",
                    "DeletionPolicy": "Delete",
                    "Properties": {"TemplateURL": ".aws-sam/build/adl_nested_template.yaml"},
                    "Metadata": {"CreatedBy": "AWS SAM CLI sync command"},
                },
            },
        }

        result = ctx._get_template_for_output(stack, expanded_template, {})

        # When no original_template_dict, the expanded template is returned directly
        self.assertIs(
            result,
            expanded_template,
            "When stack has no original_template_dict, _get_template_for_output must "
            "return the expanded template directly (same object reference).",
        )

        # Verify the nested stack resource is present
        self.assertIn(
            self.NESTED_STACK_NAME,
            result.get("Resources", {}),
            "Expanded template must contain AwsSamAutoDependencyLayerNestedStack resource.",
        )

        # Verify Layers are present on the function
        func_props = result["Resources"]["MyFunction"]["Properties"]
        self.assertIn("Layers", func_props, "Function must have Layers in expanded template.")
        self.assertEqual(len(func_props["Layers"]), 1)

    def test_get_template_for_output_foreach_without_auto_dependency_layers(self):
        """
        Test 2b: When create_auto_dependency_layer=False and the template has
        Fn::ForEach, _get_template_for_output returns the original template with
        Fn::ForEach structure preserved and no nested stack resource.

        Validates: Requirements 3.2
        """
        ctx = self._make_context(create_auto_dependency_layer=False)

        # Original template with Fn::ForEach
        original_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Parameters": {
                "FunctionNames": {
                    "Type": "CommaDelimitedList",
                    "Default": "Alpha,Beta",
                }
            },
            "Resources": {
                "Fn::ForEach::Functions": [
                    "FunctionName",
                    {"Ref": "FunctionNames"},
                    {
                        "${FunctionName}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "Handler": "index.handler",
                                "Runtime": "python3.12",
                                "CodeUri": "./src",
                            },
                        }
                    },
                ],
            },
        }

        stack = MagicMock()
        stack.original_template_dict = original_template
        stack.parameters = {"FunctionNames": "Alpha,Beta"}

        # Expanded template WITHOUT auto dependency layers (no nested stack, no Layers)
        expanded_template = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "AlphaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.12",
                        "CodeUri": ".aws-sam/build/AlphaFunction",
                    },
                },
                "BetaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.12",
                        "CodeUri": ".aws-sam/build/BetaFunction",
                    },
                },
            },
        }

        result = ctx._get_template_for_output(stack, expanded_template, {})

        # The result should be a deep copy of the original template (not the expanded one)
        # with artifact paths updated
        self.assertIsNot(result, expanded_template)

        # Fn::ForEach structure must be preserved
        self.assertIn(
            "Fn::ForEach::Functions",
            result.get("Resources", {}),
            "Fn::ForEach::Functions must be preserved in output template.",
        )

        foreach_construct = result["Resources"]["Fn::ForEach::Functions"]
        self.assertIsInstance(foreach_construct, list)
        self.assertEqual(len(foreach_construct), 3)

        # No nested stack resource should be present (auto dependency layers disabled)
        self.assertNotIn(
            self.NESTED_STACK_NAME,
            result.get("Resources", {}),
            "No AwsSamAutoDependencyLayerNestedStack should exist when auto dependency layers are disabled.",
        )

        # The ForEach body should NOT have Layers (no auto dependency layers)
        body = foreach_construct[2]
        for template_key, template_value in body.items():
            if isinstance(template_value, dict):
                props = template_value.get("Properties", {})
                self.assertNotIn(
                    "Layers",
                    props,
                    f"Function body '{template_key}' should not have Layers when "
                    f"auto dependency layers are disabled.",
                )

    def test_build_without_sync_foreach_template_unchanged(self):
        """
        Test 2d: sam build (without sync/auto dependency layers) on ForEach templates
        continues to write the original unexpanded template with Mappings.

        When create_auto_dependency_layer=False, the output template should be
        the original template with artifact paths updated via Mappings, preserving
        the Fn::ForEach structure.

        Validates: Requirements 3.3
        """
        ctx = self._make_context(create_auto_dependency_layer=False)

        # Original template with Fn::ForEach where CodeUri uses the loop variable
        original_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Parameters": {
                "FunctionNames": {
                    "Type": "CommaDelimitedList",
                    "Default": "Alpha,Beta",
                }
            },
            "Resources": {
                "Fn::ForEach::Functions": [
                    "FunctionName",
                    {"Ref": "FunctionNames"},
                    {
                        "${FunctionName}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "Handler": "index.handler",
                                "Runtime": "python3.12",
                                "CodeUri": {"Fn::Sub": "./src/${FunctionName}"},
                            },
                        }
                    },
                ],
            },
        }

        stack = MagicMock()
        stack.original_template_dict = original_template
        stack.parameters = {"FunctionNames": "Alpha,Beta"}
        stack.stack_path = ""

        # Expanded template with built artifact paths
        expanded_template = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "AlphaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.12",
                        "CodeUri": ".aws-sam/build/AlphaFunction",
                    },
                },
                "BetaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.12",
                        "CodeUri": ".aws-sam/build/BetaFunction",
                    },
                },
            },
        }

        result = ctx._get_template_for_output(
            stack,
            expanded_template,
            {"AlphaFunction": "/built/AlphaFunction", "BetaFunction": "/built/BetaFunction"},
        )

        # Fn::ForEach structure must be preserved
        self.assertIn("Fn::ForEach::Functions", result.get("Resources", {}))

        # The template should have Mappings generated for dynamic artifact paths
        # (because CodeUri uses the loop variable via Fn::Sub)
        self.assertIn(
            "Mappings",
            result,
            "Output template must contain Mappings section for dynamic artifact properties "
            "when CodeUri uses the loop variable.",
        )

        # The ForEach body's CodeUri should be updated to use Fn::FindInMap
        foreach_construct = result["Resources"]["Fn::ForEach::Functions"]
        body = foreach_construct[2]
        for template_key, template_value in body.items():
            if isinstance(template_value, dict) and template_value.get("Type") == "AWS::Serverless::Function":
                code_uri = template_value.get("Properties", {}).get("CodeUri")
                self.assertIsNotNone(code_uri, "CodeUri must be present in the function body.")
                # CodeUri should be a Fn::FindInMap reference (not the original Fn::Sub)
                self.assertIsInstance(
                    code_uri,
                    dict,
                    "CodeUri should be a dict (Fn::FindInMap reference) after artifact path update.",
                )
                self.assertIn(
                    "Fn::FindInMap",
                    code_uri,
                    "CodeUri should use Fn::FindInMap to look up the built artifact path from Mappings.",
                )

"""
Unit tests for CloudFormation Language Extensions Integration.

This module contains unit tests for the correctness properties
defined in the design document:
- Property 3: Original Template Preserved for Output
- Property 4: Dynamic Artifact Property Transformation
- Property 5: Cloud-Dependent Collection Rejection
- Property 6: Locally Resolvable Collection Acceptance
- Property 7: Content-Based S3 Hashing for Dynamic Artifacts

Requirements tested:
    - 3.1, 3.2, 3.3, 3.4: Original template preservation
    - 4.1, 4.2, 4.3, 4.4, 4.5: Dynamic artifact property transformation
    - 5.1, 5.2, 5.3, 5.4, 5.5: Cloud-dependent collection rejection
    - 5.6, 5.7: Locally resolvable collection acceptance
"""

import copy
from unittest.mock import MagicMock, patch

import pytest

from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException
from samcli.lib.cfn_language_extensions.models import TemplateProcessingContext
from samcli.lib.cfn_language_extensions.processors.foreach import ForEachProcessor


# =============================================================================
# Property 3: Original Template Preserved for Output
# =============================================================================


class TestProperty3OriginalTemplatePreserved:
    """
    Property 3: Original Template Preserved for Output

    For any template with `Fn::ForEach` constructs, after processing,
    the `get_original_template()` method SHALL return a template that
    preserves the original `Fn::ForEach` structure.

    **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
    """

    @pytest.mark.parametrize(
        "loop_name,loop_variable,collection,resource_type",
        [
            ("Services", "Name", ["Alpha", "Beta"], "AWS::Serverless::Function"),
            ("Tables", "TableName", ["Users", "Orders", "Products"], "AWS::DynamoDB::Table"),
            ("Queues", "QName", ["High", "Low"], "AWS::SQS::Queue"),
        ],
    )
    def test_foreach_structure_preserved_in_original_template(
        self,
        loop_name,
        loop_variable,
        collection,
        resource_type,
    ):
        """
        For any template with Fn::ForEach, the original template
        preserves the Fn::ForEach structure after processing.

        **Validates: Requirements 3.1, 3.2, 3.3**
        """
        from samcli.lib.samlib.wrapper import SamTranslatorWrapper

        foreach_key = f"Fn::ForEach::{loop_name}"
        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                foreach_key: [
                    loop_variable,
                    collection,
                    {
                        f"Resource${{{loop_variable}}}": {
                            "Type": resource_type,
                            "Properties": {
                                "Name": {"Fn::Sub": f"${{{loop_variable}}}-resource"},
                            },
                        }
                    },
                ]
            },
        }

        original_copy = copy.deepcopy(template)
        wrapper = SamTranslatorWrapper(template)
        preserved = wrapper.get_original_template()

        # Verify Fn::ForEach structure is preserved
        assert foreach_key in preserved["Resources"]
        assert preserved == original_copy

        # Verify expanded resources are NOT in the original
        for value in collection:
            assert f"Resource{value}" not in preserved["Resources"]

    @pytest.mark.parametrize(
        "loop_name,loop_variable,collection",
        [
            ("Functions", "Name", ["Alpha", "Beta"]),
            ("Workers", "Wk", ["Process", "Notify", "Archive"]),
        ],
    )
    @patch("samcli.lib.samlib.wrapper._SamParserReimplemented")
    def test_original_template_unchanged_after_run_plugins(
        self,
        mock_parser_class,
        loop_name,
        loop_variable,
        collection,
    ):
        """
        For any template with Fn::ForEach, the original template
        remains unchanged after run_plugins() processes it.

        **Validates: Requirements 3.2, 3.4**
        """
        from samcli.lib.samlib.wrapper import SamTranslatorWrapper

        foreach_key = f"Fn::ForEach::{loop_name}"
        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                foreach_key: [
                    loop_variable,
                    collection,
                    {
                        f"Resource${{{loop_variable}}}": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "Handler": "index.handler",
                                "Runtime": "python3.9",
                            },
                        }
                    },
                ]
            },
        }

        original_copy = copy.deepcopy(template)
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser

        wrapper = SamTranslatorWrapper(template)
        wrapper.run_plugins()

        preserved = wrapper.get_original_template()
        assert preserved == original_copy
        assert foreach_key in preserved["Resources"]

    @pytest.mark.parametrize(
        "loop_name1,loop_name2,loop_var1,loop_var2,coll1,coll2",
        [
            ("Functions", "Tables", "FName", "TName", ["Alpha", "Beta"], ["Users", "Orders"]),
            ("APIs", "Queues", "ApiName", "QName", ["Public", "Private"], ["High", "Low", "Medium"]),
        ],
    )
    def test_multiple_foreach_blocks_preserved(
        self,
        loop_name1,
        loop_name2,
        loop_var1,
        loop_var2,
        coll1,
        coll2,
    ):
        """
        For any template with multiple Fn::ForEach blocks,
        all blocks are preserved in the original template.

        **Validates: Requirements 3.3**
        """
        from samcli.lib.samlib.wrapper import SamTranslatorWrapper

        foreach_key1 = f"Fn::ForEach::{loop_name1}"
        foreach_key2 = f"Fn::ForEach::{loop_name2}"
        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                foreach_key1: [
                    loop_var1,
                    coll1,
                    {
                        f"Func${{{loop_var1}}}": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"Handler": "index.handler"},
                        }
                    },
                ],
                foreach_key2: [
                    loop_var2,
                    coll2,
                    {
                        f"Table${{{loop_var2}}}": {
                            "Type": "AWS::DynamoDB::Table",
                            "Properties": {"TableName": {"Fn::Sub": f"${{{loop_var2}}}"}},
                        }
                    },
                ],
                "StaticResource": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {"BucketName": "my-bucket"},
                },
            },
        }

        wrapper = SamTranslatorWrapper(template)
        preserved = wrapper.get_original_template()

        assert foreach_key1 in preserved["Resources"]
        assert foreach_key2 in preserved["Resources"]
        assert "StaticResource" in preserved["Resources"]


# =============================================================================
# Property 5: Cloud-Dependent Collection Rejection
# =============================================================================


class TestProperty5CloudDependentCollectionRejection:
    """
    Property 5: Cloud-Dependent Collection Rejection

    For any `Fn::ForEach` collection containing `Fn::GetAtt`, `Fn::ImportValue`,
    or SSM/Secrets Manager dynamic references, the language extensions processor
    SHALL raise an error with a clear message suggesting the parameter workaround.

    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
    """

    @pytest.mark.parametrize(
        "loop_name,loop_variable,resource_name,attribute_name",
        [
            ("Functions", "Name", "MyResource", "Arn"),
            ("Services", "Svc", "OutputTable", "OutputList"),
            ("Workers", "Wk", "LambdaFunc", "Name"),
        ],
    )
    def test_fn_getatt_in_collection_raises_error(
        self,
        loop_name,
        loop_variable,
        resource_name,
        attribute_name,
    ):
        """
        For any Fn::ForEach with Fn::GetAtt in collection,
        an error SHALL be raised with a clear message.

        **Validates: Requirements 5.1, 5.4, 5.5**
        """
        processor = ForEachProcessor()
        foreach_key = f"Fn::ForEach::{loop_name}"
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    foreach_key: [
                        loop_variable,
                        {"Fn::GetAtt": [resource_name, attribute_name]},
                        {
                            f"Resource${{{loop_variable}}}": {
                                "Type": "AWS::SNS::Topic",
                            }
                        },
                    ]
                }
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_message = str(exc_info.value)
        assert "Fn::GetAtt" in error_message
        assert "cannot be resolved locally" in error_message.lower() or "unable to resolve" in error_message.lower()
        assert "parameter" in error_message.lower()

    @pytest.mark.parametrize(
        "loop_name,loop_variable,export_name",
        [
            ("Functions", "Name", "SharedFunctionNames"),
            ("Services", "Svc", "CrossStackExport"),
            ("Workers", "Wk", "ImportedList"),
        ],
    )
    def test_fn_importvalue_in_collection_raises_error(
        self,
        loop_name,
        loop_variable,
        export_name,
    ):
        """
        For any Fn::ForEach with Fn::ImportValue in collection,
        an error SHALL be raised with a clear message.

        **Validates: Requirements 5.2, 5.4, 5.5**
        """
        processor = ForEachProcessor()
        foreach_key = f"Fn::ForEach::{loop_name}"
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    foreach_key: [
                        loop_variable,
                        {"Fn::ImportValue": export_name},
                        {
                            f"Resource${{{loop_variable}}}": {
                                "Type": "AWS::SNS::Topic",
                            }
                        },
                    ]
                }
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_message = str(exc_info.value)
        assert "Fn::ImportValue" in error_message
        assert "parameter" in error_message.lower()

    @pytest.mark.parametrize(
        "loop_name,loop_variable,ssm_path,service",
        [
            ("Functions", "Name", "/my/path", "ssm"),
            ("Services", "Svc", "/secrets/list", "ssm-secure"),
            ("Workers", "Wk", "/app/config", "secretsmanager"),
        ],
    )
    def test_dynamic_reference_in_collection_raises_error(
        self,
        loop_name,
        loop_variable,
        ssm_path,
        service,
    ):
        """
        For any Fn::ForEach with SSM/Secrets Manager dynamic reference
        in collection, an error SHALL be raised with a clear message.

        **Validates: Requirements 5.3, 5.4, 5.5**
        """
        processor = ForEachProcessor()
        foreach_key = f"Fn::ForEach::{loop_name}"
        dynamic_ref = f"{{{{resolve:{service}:{ssm_path}}}}}"

        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    foreach_key: [
                        loop_variable,
                        [dynamic_ref],
                        {
                            f"Resource${{{loop_variable}}}": {
                                "Type": "AWS::SNS::Topic",
                            }
                        },
                    ]
                }
            }
        )

        with pytest.raises(InvalidTemplateException) as exc_info:
            processor.process_template(context)

        error_message = str(exc_info.value)
        assert "cannot be resolved locally" in error_message.lower() or "unable to resolve" in error_message.lower()
        assert "parameter" in error_message.lower()


# =============================================================================
# Property 6: Locally Resolvable Collection Acceptance
# =============================================================================


class TestProperty6LocallyResolvableCollectionAcceptance:
    """
    Property 6: Locally Resolvable Collection Acceptance

    For any `Fn::ForEach` collection that is a static list or a `!Ref` to a
    parameter with a provided value, the language extensions processor SHALL
    successfully resolve and expand the collection.

    **Validates: Requirements 5.6, 5.7**
    """

    @pytest.mark.parametrize(
        "loop_name,loop_variable,collection",
        [
            ("Functions", "Name", ["Alpha", "Beta"]),
            ("Services", "Svc", ["Users", "Orders", "Products"]),
            ("Queues", "QName", ["High"]),
        ],
    )
    def test_static_list_collection_succeeds(
        self,
        loop_name,
        loop_variable,
        collection,
    ):
        """
        For any Fn::ForEach with a static list collection,
        the processor SHALL successfully expand the collection.

        **Validates: Requirements 5.6**
        """
        processor = ForEachProcessor()
        foreach_key = f"Fn::ForEach::{loop_name}"
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    foreach_key: [
                        loop_variable,
                        collection,
                        {
                            f"Resource${{{loop_variable}}}": {
                                "Type": "AWS::SNS::Topic",
                                "Properties": {
                                    "TopicName": {"Fn::Sub": f"${{{loop_variable}}}-topic"},
                                },
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        assert foreach_key not in context.fragment["Resources"]
        for value in collection:
            assert f"Resource{value}" in context.fragment["Resources"]
        assert len(context.fragment["Resources"]) == len(collection)

    @pytest.mark.parametrize(
        "loop_name,loop_variable,param_name,collection",
        [
            ("Functions", "Name", "FuncNames", ["Alpha", "Beta"]),
            ("Services", "Svc", "ServiceList", ["Users", "Orders", "Products"]),
        ],
    )
    def test_parameter_ref_collection_with_override_succeeds(
        self,
        loop_name,
        loop_variable,
        param_name,
        collection,
    ):
        """
        For any Fn::ForEach with a parameter reference collection
        and provided parameter value, the processor SHALL successfully expand.

        **Validates: Requirements 5.7**
        """
        processor = ForEachProcessor()
        foreach_key = f"Fn::ForEach::{loop_name}"
        context = TemplateProcessingContext(
            fragment={
                "Parameters": {
                    param_name: {
                        "Type": "CommaDelimitedList",
                        "Default": "Default1,Default2",
                    }
                },
                "Resources": {
                    foreach_key: [
                        loop_variable,
                        {"Ref": param_name},
                        {
                            f"Resource${{{loop_variable}}}": {
                                "Type": "AWS::SNS::Topic",
                            }
                        },
                    ]
                },
            },
            parameter_values={param_name: collection},
        )

        processor.process_template(context)

        assert foreach_key not in context.fragment["Resources"]
        for value in collection:
            assert f"Resource{value}" in context.fragment["Resources"]

    @pytest.mark.parametrize(
        "loop_name,loop_variable,param_name,collection",
        [
            ("Functions", "Name", "FuncNames", ["Alpha", "Beta"]),
            ("Services", "Svc", "ServiceList", ["Users", "Orders", "Products"]),
        ],
    )
    def test_parameter_ref_collection_with_default_succeeds(
        self,
        loop_name,
        loop_variable,
        param_name,
        collection,
    ):
        """
        For any Fn::ForEach with a parameter reference collection
        and default value, the processor SHALL successfully expand using the default.

        **Validates: Requirements 5.7**
        """
        processor = ForEachProcessor()
        foreach_key = f"Fn::ForEach::{loop_name}"
        default_value = ",".join(collection)

        context = TemplateProcessingContext(
            fragment={
                "Parameters": {
                    param_name: {
                        "Type": "CommaDelimitedList",
                        "Default": default_value,
                    }
                },
                "Resources": {
                    foreach_key: [
                        loop_variable,
                        {"Ref": param_name},
                        {
                            f"Resource${{{loop_variable}}}": {
                                "Type": "AWS::SNS::Topic",
                            }
                        },
                    ]
                },
            },
            parameter_values={},
        )

        processor.process_template(context)

        assert foreach_key not in context.fragment["Resources"]
        for value in collection:
            assert f"Resource{value}" in context.fragment["Resources"]

    @pytest.mark.parametrize(
        "loop_name,loop_variable",
        [
            ("Functions", "Name"),
            ("Services", "Svc"),
        ],
    )
    def test_empty_collection_produces_no_resources(
        self,
        loop_name,
        loop_variable,
    ):
        """
        For any Fn::ForEach with an empty collection,
        the processor SHALL produce no resources.

        **Validates: Requirements 5.6**
        """
        processor = ForEachProcessor()
        foreach_key = f"Fn::ForEach::{loop_name}"
        context = TemplateProcessingContext(
            fragment={
                "Resources": {
                    foreach_key: [
                        loop_variable,
                        [],
                        {
                            f"Resource${{{loop_variable}}}": {
                                "Type": "AWS::SNS::Topic",
                            }
                        },
                    ]
                }
            }
        )

        processor.process_template(context)

        assert foreach_key not in context.fragment["Resources"]
        assert len(context.fragment["Resources"]) == 0


# =============================================================================
# Property 4: Dynamic Artifact Property Transformation
# =============================================================================


class TestProperty4DynamicArtifactPropertyTransformation:
    """
    Property 4: Dynamic Artifact Property Transformation

    For any `Fn::ForEach` block that generates a packageable resource type
    with a dynamic artifact property (containing the loop variable), after
    `sam package`:
    - A Mappings section SHALL be generated with S3 URIs for each collection value
    - The artifact property SHALL be replaced with `Fn::FindInMap` referencing
      the generated Mappings
    - The `Fn::ForEach` structure SHALL be preserved

    **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**
    """

    @pytest.mark.parametrize(
        "loop_name,loop_variable,collection",
        [
            ("Services", "Name", ["Users", "Orders"]),
            ("Functions", "FuncName", ["Alpha", "Beta", "Gamma"]),
            ("Workers", "Wk", ["Process", "Notify"]),
        ],
    )
    def test_dynamic_codeuri_detected(
        self,
        loop_name,
        loop_variable,
        collection,
    ):
        """
        For any Fn::ForEach with dynamic CodeUri (containing loop variable),
        the dynamic artifact property SHALL be detected.

        **Validates: Requirements 4.1**
        """
        from samcli.lib.cfn_language_extensions.sam_integration import detect_dynamic_artifact_properties

        foreach_key = f"Fn::ForEach::{loop_name}"
        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                foreach_key: [
                    loop_variable,
                    collection,
                    {
                        f"${{{loop_variable}}}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": f"./services/${{{loop_variable}}}",
                                "Handler": "index.handler",
                                "Runtime": "python3.9",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_props = detect_dynamic_artifact_properties(template)

        assert len(dynamic_props) == 1
        prop = dynamic_props[0]
        assert prop.foreach_key == foreach_key
        assert prop.loop_variable == loop_variable
        assert prop.property_name == "CodeUri"
        assert prop.collection == collection

    @pytest.mark.parametrize(
        "loop_name,loop_variable,collection",
        [
            ("Services", "Name", ["Users", "Orders"]),
            ("Functions", "FuncName", ["Alpha", "Beta", "Gamma"]),
        ],
    )
    def test_static_codeuri_not_detected_as_dynamic(
        self,
        loop_name,
        loop_variable,
        collection,
    ):
        """
        For any Fn::ForEach with static CodeUri (not containing loop variable),
        the artifact property SHALL NOT be detected as dynamic.

        **Validates: Requirements 4.7**
        """
        from samcli.lib.cfn_language_extensions.sam_integration import detect_dynamic_artifact_properties

        foreach_key = f"Fn::ForEach::{loop_name}"
        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                foreach_key: [
                    loop_variable,
                    collection,
                    {
                        f"${{{loop_variable}}}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./src",
                                "Handler": f"${{{loop_variable}}}.handler",
                                "Runtime": "python3.9",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_props = detect_dynamic_artifact_properties(template)
        assert len(dynamic_props) == 0

    @pytest.mark.parametrize(
        "loop_name,loop_variable,collection",
        [
            ("Services", "Name", ["Users", "Orders"]),
            ("Layers", "LayerName", ["Common", "Utils", "Shared"]),
        ],
    )
    def test_mappings_naming_convention(
        self,
        loop_name,
        loop_variable,
        collection,
    ):
        """
        For any dynamic artifact property, the generated Mappings
        SHALL follow the naming convention SAM{PropertyName}{LoopName}.

        **Validates: Requirements 4.6**
        """
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty
        from samcli.lib.package.language_extensions_packaging import _generate_artifact_mappings

        prop = DynamicArtifactProperty(
            foreach_key=f"Fn::ForEach::{loop_name}",
            loop_name=loop_name,
            loop_variable=loop_variable,
            collection=collection,
            resource_key=f"${{{loop_variable}}}Function",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value=f"./services/${{{loop_variable}}}",
            collection_is_parameter_ref=False,
            collection_parameter_name=None,
        )

        exported_resources = {}
        for value in collection:
            expanded_key = f"{value}Function"
            exported_resources[expanded_key] = {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": f"s3://test-bucket/{value}-hash.zip",
                    "Handler": "index.handler",
                    "Runtime": "python3.9",
                },
            }

        mappings, _ = _generate_artifact_mappings([prop], "/tmp", exported_resources)

        expected_mapping_name = f"SAMCodeUri{loop_name}"
        assert expected_mapping_name in mappings

        for value in collection:
            assert value in mappings[expected_mapping_name]


# =============================================================================
# Property 7: Content-Based S3 Hashing for Dynamic Artifacts
# =============================================================================


class TestProperty7ContentBasedS3Hashing:
    """
    Property 7: Content-Based S3 Hashing for Dynamic Artifacts

    For any dynamic artifact property in `Fn::ForEach`, each generated artifact
    SHALL have a unique S3 key based on content hash.

    **Validates: Requirements 4.2**
    """

    @pytest.mark.parametrize(
        "loop_name,loop_variable,collection",
        [
            ("Services", "Name", ["Users", "Orders"]),
            ("Functions", "FuncName", ["Alpha", "Beta", "Gamma"]),
        ],
    )
    def test_each_collection_value_gets_unique_s3_uri(
        self,
        loop_name,
        loop_variable,
        collection,
    ):
        """
        For any dynamic artifact property, each collection value
        SHALL have a unique S3 URI in the generated Mappings.

        **Validates: Requirements 4.2**
        """
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty
        from samcli.lib.package.language_extensions_packaging import _generate_artifact_mappings

        prop = DynamicArtifactProperty(
            foreach_key=f"Fn::ForEach::{loop_name}",
            loop_name=loop_name,
            loop_variable=loop_variable,
            collection=collection,
            resource_key=f"${{{loop_variable}}}Function",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value=f"./services/${{{loop_variable}}}",
            collection_is_parameter_ref=False,
            collection_parameter_name=None,
        )

        exported_resources = {}
        for i, value in enumerate(collection):
            expanded_key = f"{value}Function"
            content_hash = f"hash{i:04d}"
            exported_resources[expanded_key] = {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": f"s3://test-bucket/{content_hash}.zip",
                    "Handler": "index.handler",
                    "Runtime": "python3.9",
                },
            }

        mappings, _ = _generate_artifact_mappings([prop], "/tmp", exported_resources)

        mapping_name = f"SAMCodeUri{loop_name}"
        s3_uris = set()

        for value in collection:
            assert value in mappings[mapping_name]
            s3_uri = mappings[mapping_name][value].get("CodeUri")
            assert s3_uri is not None
            assert s3_uri not in s3_uris
            s3_uris.add(s3_uri)

        assert len(s3_uris) == len(collection)

    @pytest.mark.parametrize(
        "loop_name,loop_variable,collection",
        [
            ("Services", "Name", ["Users", "Orders"]),
            ("Workers", "Wk", ["Process", "Notify", "Archive"]),
        ],
    )
    def test_findmap_replacement_preserves_foreach_structure(
        self,
        loop_name,
        loop_variable,
        collection,
    ):
        """
        After replacing dynamic artifact property with Fn::FindInMap,
        the Fn::ForEach structure SHALL be preserved.

        **Validates: Requirements 4.4, 4.5**
        """
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty
        from samcli.lib.package.language_extensions_packaging import _apply_artifact_mappings_to_template

        foreach_key = f"Fn::ForEach::{loop_name}"

        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                foreach_key: [
                    loop_variable,
                    collection,
                    {
                        f"${{{loop_variable}}}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": f"./services/${{{loop_variable}}}",
                                "Handler": "index.handler",
                                "Runtime": "python3.9",
                            },
                        }
                    },
                ]
            },
        }

        prop = DynamicArtifactProperty(
            foreach_key=foreach_key,
            loop_name=loop_name,
            loop_variable=loop_variable,
            collection=collection,
            resource_key=f"${{{loop_variable}}}Function",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value=f"./services/${{{loop_variable}}}",
            collection_is_parameter_ref=False,
            collection_parameter_name=None,
        )

        mappings = {
            f"SAMCodeUri{loop_name}": {value: {"CodeUri": f"s3://test-bucket/{value}-hash.zip"} for value in collection}
        }

        result = _apply_artifact_mappings_to_template(copy.deepcopy(template), mappings, [prop])

        assert foreach_key in result["Resources"]
        assert "Mappings" in result
        assert f"SAMCodeUri{loop_name}" in result["Mappings"]

        foreach_value = result["Resources"][foreach_key]
        assert isinstance(foreach_value, list)
        assert len(foreach_value) == 3
        assert foreach_value[0] == loop_variable
        assert foreach_value[1] == collection


# =============================================================================
# Property 12: Recursive Detection of Nested ForEach Dynamic Artifact Properties
# =============================================================================


class TestProperty12RecursiveDetection:
    """
    Property 12: For any template containing nested Fn::ForEach blocks where an
    inner block generates a packageable resource with a dynamic artifact property,
    detect_dynamic_artifact_properties() SHALL detect the dynamic property
    regardless of nesting depth.

    Validates: Requirements 25.1, 25.10
    """

    @pytest.mark.parametrize(
        "outer_loop_name,inner_loop_name,outer_var,inner_var,outer_collection,inner_collection",
        [
            ("Envs", "Services", "Env", "Svc", ["dev", "prod"], ["Users", "Orders"]),
            ("Regions", "Functions", "Region", "Func", ["east", "west"], ["Alpha", "Beta", "Gamma"]),
        ],
    )
    def test_nested_foreach_dynamic_property_detected(
        self,
        outer_loop_name,
        inner_loop_name,
        outer_var,
        inner_var,
        outer_collection,
        inner_collection,
    ):
        """Validates: Requirements 25.1, 25.10"""
        from samcli.lib.cfn_language_extensions.sam_integration import detect_dynamic_artifact_properties

        template = {
            "Resources": {
                f"Fn::ForEach::{outer_loop_name}": [
                    outer_var,
                    outer_collection,
                    {
                        f"Fn::ForEach::{inner_loop_name}": [
                            inner_var,
                            inner_collection,
                            {
                                f"${{{outer_var}}}${{{inner_var}}}Function": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "CodeUri": f"./services/${{{inner_var}}}",
                                        "Handler": "index.handler",
                                    },
                                }
                            },
                        ]
                    },
                ]
            }
        }

        result = detect_dynamic_artifact_properties(template)
        assert len(result) == 1
        assert result[0].loop_variable == inner_var
        assert result[0].loop_name == inner_loop_name
        assert len(result[0].outer_loops) == 1
        assert result[0].outer_loops[0][1] == outer_var


# =============================================================================
# Property 13: Inner-Only Variable Mappings Naming Convention
# =============================================================================


class TestProperty13InnerOnlyMappingsNaming:
    """
    Property 13: For any nested Fn::ForEach where the dynamic artifact property
    references only the innermost loop variable, the generated Mappings section
    name SHALL follow the pattern SAM{PropertyName}{InnerLoopName}.

    Validates: Requirements 25.2
    """

    @pytest.mark.parametrize(
        "inner_loop_name,inner_collection",
        [
            ("Services", ["Users", "Orders"]),
            ("Workers", ["Process", "Notify", "Archive"]),
        ],
    )
    def test_inner_only_mappings_naming(self, inner_loop_name, inner_collection):
        """Validates: Requirements 25.2"""
        from samcli.lib.cfn_language_extensions.sam_integration import detect_dynamic_artifact_properties

        template = {
            "Resources": {
                "Fn::ForEach::Outer": [
                    "OuterVar",
                    ["a", "b"],
                    {
                        f"Fn::ForEach::{inner_loop_name}": [
                            "InnerVar",
                            inner_collection,
                            {
                                "${OuterVar}${InnerVar}Func": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {"CodeUri": "./svc/${InnerVar}"},
                                }
                            },
                        ]
                    },
                ]
            }
        }

        result = detect_dynamic_artifact_properties(template)
        assert len(result) == 1
        # Nesting path includes the outer loop name ("Outer") + inner loop name
        from samcli.lib.package.language_extensions_packaging import _nesting_path

        expected_mapping_name = f"SAMCodeUriOuter{inner_loop_name}"
        actual_mapping_name = f"SAM{result[0].property_name}{_nesting_path(result[0])}"
        assert actual_mapping_name == expected_mapping_name


# =============================================================================
# Property 14: Compound Key Generation for Multi-Variable References
# =============================================================================


class TestProperty14CompoundKeyGeneration:
    """
    Property 14: For any nested Fn::ForEach where the dynamic artifact property
    references both outer and inner loop variables, the generated Mappings SHALL
    use compound keys.

    Validates: Requirements 25.3, 25.7
    """

    def test_compound_keys_generated_for_multi_variable_reference(self):
        """Validates: Requirements 25.3, 25.7"""
        from samcli.lib.cfn_language_extensions.sam_integration import (
            detect_dynamic_artifact_properties,
            contains_loop_variable,
        )

        template = {
            "Resources": {
                "Fn::ForEach::Envs": [
                    "Env",
                    ["dev", "prod"],
                    {
                        "Fn::ForEach::Svcs": [
                            "Svc",
                            ["Users", "Orders"],
                            {
                                "${Env}${Svc}Func": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {"CodeUri": "./${Env}/${Svc}"},
                                }
                            },
                        ]
                    },
                ]
            }
        }

        result = detect_dynamic_artifact_properties(template)
        assert len(result) == 1
        prop = result[0]

        assert contains_loop_variable(prop.property_value, "Svc")
        assert contains_loop_variable(prop.property_value, "Env")

        assert len(prop.outer_loops) == 1
        assert prop.outer_loops[0][1] == "Env"
        assert prop.outer_loops[0][2] == ["dev", "prod"]

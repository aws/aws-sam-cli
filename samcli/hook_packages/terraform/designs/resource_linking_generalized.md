# Resource Linking

After translating a resource from Terraform to CloudFormation, 
that resource often needs to be linked to another based on a field.

For example, AWS Lambda Functions are linked to AWS Lambda Layers through the 
`Layers` property of a Lambda Function.

E.g.
```yaml
Resources:
  AwsLambdaFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: s3_lambda_function
      Code: function.zip
      Handler: app.lambda_handler
      PackageType: Zip
      Runtime: python3.8
      Layers:
      - Ref: AwsLambdaLayerVersion
  AwsLambdaLayerVersion:
    Type: AWS::Lambda::LayerVersion
    Properties:
      LayerName: lambda_layer1
      CompatibleRuntimes:
      - python3.8
      Content: layer.zip
```

In this case, the function will be defined as the `source` resource and the layer
as the `destination` resource. The `Layers` field links to the destination resource 
using a CloudFormation intrinsic function `!Ref`, and points to the Lambda Layer Arn.

Today, the linking logic is specific to Functions and Layers. The section below proposes
a method of generalization to make the linking of two resources more extensible and easier to implement.

## Proposed Solution
Currently, the linking design is functional and passes certain required parameters from 
the translation function to a specific Function to Layer linking function. Since the fields required to link any two resources primarily the same, they can be abstracted away to a data class
that will house them.

```python
@dataclass
class ResourceLinkingPair:
    source_resource_cfn_resource: Dict[str, List]
    source_resource_tf_config: Dict[str, TFResource]
    destination_resource_tf: Dict[str, Dict]
    intrinsic_type: LinkerIntrinsics
    cfn_intrinsic_attribute: Optional[str]
    source_link_field_name: str
    terraform_resource_type_prefix: str
    linking_exceptions: ResourcePairLinkingExceptions
```

- `source_resource_cfn_resource` this the CFN representation of the resource to which the linked resource will be added
- `source_resource_tf_config` the Terraform configuration object for the source resource
- `destination_resource_tf` the destination resources' Terraform planned values (not the configuration object)
- `intrinsic_type` the CFN intrinsic on which to link (`Ref` or `GetAtt`)
- `cfn_intrinsic_attribute` in the case of `GetAtt`, the resource attribute to link to (should be None for `Ref`)
- `source_link_field_name` the name in the source CFN resource to add the linked resource to
- `terraform_resource_type_prefix` the Terraform resource type prefix used for finding all resource of that type
- `linking_exceptions` these are exceptions that need to be created with messages specific to the resource linking pair to be used
by the `ResourceLinker`. With specific exception types, metric data can be collected specific to the resources being linked.

```python
class ResourcePairLinkingExceptions:
    multiple_resource_linking_exception: Type[UserException]
    local_variable_linking_exception: Type[UserException]
```


Only the first three fields are computed, and need to be collected the same way they are today, when parsing the Terraform modules.
E.g. collecting the Lambda function `source_resource_cfn_resource` and `source_resource_tf_config` looks like this:
```python
if resource_type == TF_AWS_LAMBDA_FUNCTION:
    resolved_config_address = _get_configuration_address(resource_full_address)
    matched_lambdas = source_resource_cfn_resource.get(resolved_config_address, [])
    matched_lambdas.append(translated_resource)
    source_resource_cfn_resource[resolved_config_address] = matched_lambdas
    source_resource_tf_config[resolved_config_address] = config_resource
```

and on the destination Layer resource, collecting the `destination_resource_tf`
```python
if resource_type == TF_AWS_LAMBDA_LAYER_VERSION:
    destination_resource_tf[logical_id] = resource
```

After collecting those three fields, a `ResourceLinkingPair` object can be instantiated.

Once all `ResourceLinkingPair` objects have been created, a list of these objects can be passed to the `ResourceLinker`.
```python
class ResourceLinker:
    _resource_pairs: List[ResourceLinkingPair]

    def link_resources(self):
        """
        Iterate through all of the ResourceLinkingPair items and link the
        corresponding source resource to destination resource
        """

    def _update_mapped_parent_resource_with_resolved_child_resources(self, destination_resources: List):
        """
        Set the resolved destination resource list to the mapped source resources.

        Parameters
        ----------
        destination_resources: List
            The resolved destination resource values that will be used as a value for the mapped CFN resource attribute.
        """

    def _process_reference_resource_value(self, resolved_destination_resource: ResolvedReference):
        """
        Process the a reference destination resource value of type ResolvedReference.

        Parameters
        ----------
        resolved_destination_resource: ResolvedReference
            The resolved destination resource reference.

        Returns
        -------
        List[Dict[str, str]]
            The resolved values that will be used as a value for the mapped CFN resource attribute.
        """

    def _process_resolved_resources(self, resolved_destination_resource: List[Union[ConstantValue, ResolvedReference]]):
        """
        Process the resolved destination resources.

        Parameters
        ----------
        resolved_destination_resource: List[Union[ConstantValue, ResolvedReference]]
            The resolved destination resources to be processed for the input source resource.

        Returns
        --------
        List[Dict[str, str]]:
            The list of destination resources after processing
        """
```

The `ResourceLinker` contains a public `link_resources` method to begin execution of the resource linking. The methods 
shown in the class are all generalized versions of the existing Function to Layer linking functions that exist today.

`link_resources` &larr; `_link_lambda_function_to_layer`, `_link_lambda_functions_to_layers`
`_update_mapped_parent_resource_with_resolved_child_resources` &larr; `_update_mapped_lambda_function_with_resolved_layers`
`_process_reference_resource_value` &larr; `_process_reference_layer_value`
`_process_resolved_resources` &larr; `_process_resolved_layers` 

To generalize these functions: 
- All instances of hard-coded properties need to be replaced with the corresponding values
defined in the `ResourceLinkingPair` instance
- Exception messages should be updated to be more generic
- The `_update_mapped_parent_resource_with_resolved_child_resources` method should be updated to support writing other intrinsic types.


### Adding New Resource Links
With the proposed change, creating a new link between two resources will include:
1. Collecting the three required fields (`source_resource_cfn_resource`, `source_resource_tf_config` and `destination_resource_tf`)
2. Creating a `ResourceLinkingPair` instance
3. Appending the `ResourceLinkingPair` to the list of pairs
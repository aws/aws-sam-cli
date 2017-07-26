# SAM CLI Parsing

One of the core processes of SAM Cli is the parsing of templates, for validation and characteristic-matching for the local server. This process is part of all the tasks of SAM CLI.

## Base modeling

### Resources

The most basic definition for SAM components are Resources and Properties. A resource represents an element of the template. Current existing resources are `AWS::Serverless::Function`, `AWS::Serverless::Api` and `AWS::Serverless::Table`. Every resource **must** have a `Type` - that shall be one of the aforementioned resource type strings -, a set of `Properties` that define the different characteristics of the resource, and an object defining the `ReturnValues` of the resource once it's parsed and validated. This abstract resource configuration is leveraged to define all valid resource types in SAM. 

### Properties

Properties are each of the attributes that characterize a resource. Every resource will have properties, whose values will eventually be used to configure the resource, as well as for the `ReturnValues` that every resource can export. Properties can be primitive values or inner resources, that include configuration for a particular aspect of a resource that requires further configuration. 

#### Property typing

Properties within every resource must define the valid data types its instances shall have. This values - which could be from any valid primitive to the reference to another resource - are used to match against the value... #TODO

## Parsing processes

### Marshalling

On the initial marshalling process, the YAML #TODO JSON file is parsed and converted to a golang `map[string]interface{}`, that will contain all resources present in the template file. On this process SAM CLI will assert that the template file is syntactically correct, or let you know that an error has been found.

Upon marshalling the template, only the `Resources` part of it will be converted for future use. The `Properties` object will be stored as static properties #TODO, for being used in the compiled template. This process also recognizes all intrinsic functions present in the template, whose reference will be stored for future resolution. On this phase the functions _per se_ are not touched within the template - but their reference is formalized to simplify its function resolution and further processing.


#### Intrinsic function detection

On this stage only inline functions are targeted. These functions use YAML tags for being defined - e.g. `!Ref` - which AFAIK aren't yet supported for Golang. Thus, these functions are identified and substituted to the full version - e.g. `Fn::Sub` - in a way it could be picked up for resolving the values upon post-processing.

At this phase the template is just a plain string - as if we unmarshal it we loose the tags -, so the simplest way for targeting these functions on this stage we use regular expressions. The regex in use is explained here:

All intrinsic Fn have the following common structure:
    * Starts by `!(Base64|FindInMap|GetAtt|GetAZs|ImportValue|Join|Select|Split|Sub|Ref)`.
    * Contains only a string (or)
    * Contains an Array of 2 elements.
        * Elements can be strings, arrays or objects
        * If Fn is Sub, contains an object with extra params.

And this is the regex:

```
// Leading spaces
[\n\t\s]*

// Fn Start
!(Base64|FindInMap|GetAtt|GetAZs|ImportValue|Join|Select|Split|Sub|Ref) 

// Value is a String
([\'\"]?[a-zA-Z0-9:_\.\-$\{\}\/]+[\'\"]?) ||

// Value is an inline array
(\[[a-zA-Z0-9:_\.\-$\{\}\/\[\]\'\"\s,]+\])

```

_NOTE: For avoiding indentation errors, the value is wrapped in an inline array, and hence the line breaks and tabs before the inline fn are removed._

### Scaffolding

Upon scaffolding, all resources found on the mashalling phase will be converted to proper resources, by using the definitions of all SAM resources available on SAM CLI. On this process, all resources and their properties will be validated, verifying that all required property values are fulfilled, and that the validation rules set for the properties pass the validation function. In case there's any validation error, you'll be notified. 

All the dynamic information defined within the resources will be generated on this phase, and assigned to the resource's properties. After the end of this process, all `ReturnValues` for the resources shall be accessible.

The result of this phase - if successful - is a Golang `map[string]interface{}`, similar to such outcomed from marshalling, though with all properties set and validated accordingly, and with the ReturnValues exposed for the resource evaluated and included.

### Post-processing

Once all resources are scaffolded, the output's `map` passes through a post-processing task. These tasks are `Resource` specific, and its main purpose is to convert the raw `map` definition of your resources into a formal `struct` that fully represents each `Resource`, with all the required data for creating the server and routing.

During post-processing, the intrinsic functions are evaluated, and the compiled template is queried against the `ReturnValues` of the `Resource` referenced by the function. During this phase, a function compliance assertion is run, notifying you if some of the function's value is not resolvable. 

Sometimes your template can have intrinsic functions that reference resources in a way that one post-processing execution might not suffice for resolving all the functions' values. By default, SAM CLI will retry up to 3 times to fully resolve your template, and in case it can't, it'll throw an exception. Use the options `--no-extra-preprocessing` or `--extra-preprocessing /[0-9]+/` to override this default value.


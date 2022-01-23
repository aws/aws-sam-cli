`samconfig.toml`
--------------------------

This doc goes through the different sections of the configuration file and explains them

```
version = 0.1

[default.build.paramaters]
profile="srirammv"
debug=true
skip_pull_image=true
use_container=true

[default.local_start_api.paramaters]
port=5400

[default.package.parameters]
profile="srirammv"
region="us-east-1"
s3_bucket="sam-bucket"
output_template_file="packaged.yaml"

[default.deploy.parameters]
stack_name="using_config_file"
capabilities="CAPABILITY_IAM"
region="us-east-1"
profile="srirammv"
```

Version
-------

`version` denotes the version of the `samconfig.toml` configuration file

Env
----------

The default chosen env (environment) is denoted as `default`

Command
-----------
The nested sections under `default` are reflected as `default.[SAM COMMAND]`

these commands should not have spaces or hyphens, both " " and "-" will be converted to underscores "_"

Therefore the sections for commands would like

```
[default.init]
[default.validate]
[default.build]
[default.local_generate_event_s3_delete]
[default.local_invoke]
[default.local_start_api]
[default.local_start_lambda]
[default.package]
[default.deploy]
[default.logs]
[default.publish]
```

Note: 
sam local generate-event has a ton of options within it, but the above rules apply.

Some examples:

```
[default.local.generate_event_alexa_skills_kit_intent_answer]
[default.local.generate_event_codepipeline_job]
```

Parameters
----------
Since this configuration file is TOML, the parameters have types built-in.

### Specifying a number

```
[default.local_start_api.paramaters]
port=5400
```

### Specifying a string

```
[default.deploy.parameters]
stack_name="using_config_file"
```

### Specifying a flag

```
[default.build.parameters]
debug=true
```


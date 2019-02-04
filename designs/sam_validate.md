# `sam validate` command

This is the design to improve the `sam validate` command to utilise the the `cfn-python-lint` package.

It would be good to go beyond just implementing the CloudFormation package for validation of template files, there is the opportunity to create something better.

## What's the current problem?

The current iteration of `sam validate` only goes so far in validating the the SAM template, it does some cursorary checks:

- Checks `CodeUri` to ensure an S3 URL exists
- Checks if the template is valid but doesn't return errors
  - If the template contains other resources outside of SAM it won't validate them

## What will be changed?

We will change how the `sam validate` command works, by integrating the [cfn-lint python package](https://github.com/awslabs/cfn-python-lint/) into the the validation workflow. This change would enhance the user's experience of working with SAM templates.

## Success criteria for the change

The user will be able to find detailed information about their template's validation errors or warnings by running `sam validate`. The validate command will also find any issues in non-SAM resources, such as S3 buckets or SNS topics.

## Out of Scope

- Customisation of the rules through the use of flags
- Ignoring checks
- Appending rules
- Specifying your own validation spec

## User Experience Walkthrough

- Create new project with `sam init --runtime python3.7 foobar`
- Run `sam validate -t ./template.yaml`
- Make changes
- If errors:

  - Show problems associated with the template

- If ok:

  - Awesome, carry on developing

Any issues identified will be printed to the user's console for them to act upon. The issues will be printed in the same fashion as `cfn-python-lint` already prints them. Using the existing printing mechanism would allow the user to use `sam validate` in place of the `cfn-lint` command in editors.

## Implementation

The improved functionality of `sam validate` will utilise the opensource `cfn-python-lint` package (https://github.com/awslabs/cfn-python-lint/) made by AWS. The changes will enhance the existing `sam validate` functionality.

`cfn-python-lint` has an optional dotfile per directory (`.cfnlintrc`) which allows users to specify rules and config of the tool. This will be implmented as a part of the changes proposed by this document.

The defaults for the tool will remain the same, whatever options `cfn-python-lint` sets by default will be used regardless of versional changes, it will be accepted that the default options are in everyone's best interest.

### Example

The following template has an error in the S3 Bucket resource, the `NotReal` key is erroneous:

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Transform: "AWS::Serverless-2016-10-31"
Resources:
  Bucket:
    Type: "AWS::S3::Bucket"
    Properties:
      NotReal: "name"
```

Expected Output would be:

```
E3002 Invalid Property Resources/Bucket/Properties/NotReal
workdir/invalid_template.yaml:7:7
```

### CLI Changes

- None

### Breaking Changes

- None

### Documentation Changes

- Explaination of what `sam validate` actually does.

### Open Issues

- https://github.com/awslabs/aws-sam-cli/issues/933

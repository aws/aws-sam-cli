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

## Implementation

The improved functionality of `sam validate` will utilise the opensource `cfn-python-lint` package (https://github.com/awslabs/cfn-python-lint/) made by AWS. The changes will enhance the existing `sam validate` functionality.

### CLI Changes

- None

### Breaking Changes

- None

### Documentation Changes

- Explaination of what `sam validate` actually does.

### Open Issues

- https://github.com/awslabs/aws-sam-cli/issues/933

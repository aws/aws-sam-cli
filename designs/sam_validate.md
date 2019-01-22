# `sam validate` command

This is the design to improve the `sam validate` command to utilise the the `cfn-python-lint` package.

It would be good to go beyond just implementing the CloudFormation package for validation of template files, there
is the opportunity to create something better.

## What's the current problem?

The current iteration of `sam validate` only goes so far in validating the the SAM template, it does some cursorary checks:

- Checks `CodeUri` to ensure an S3 URL exists
- Checks if the template is valid but doesn't return errors
  - If the template contains other resources outside of SAM it won't validate them

## What will be changed?

We will change how the `sam validate` command works, by integrating the [cfn-lint python package](https://github.com/awslabs/cfn-python-lint/) into the the validation workflow. This change would enhance the user's experience of working with SAM templates.

## Success criteria for the change

The user will be able to find detailed information about their template's validation errors or warnings by running `sam validate`

## Out of Scope

## User Experience Walkthrough

## Implementation

### CLI Changes

### Breaking Changes

### Design

### Documentation Changes

### Open Issues

### Task Breakdown

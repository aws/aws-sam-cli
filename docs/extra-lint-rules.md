# SAM CLI Extra Lint Rules Usage Guide

The AWS SAM CLI's `validate` command uses [cfn-lint](https://github.com/aws-cloudformation/cfn-lint) for template validation. 
SAM CLI now supports additional lint rules through the `--extra-lint-rules` option.

## Usage

```bash
sam validate --lint --extra-lint-rules="cfn_lint_serverless.rules"
```

## Considerations when Installing SAM CLI with the Installer

When SAM CLI is installed using the installer, it uses its own Python environment. In this case, additional rule modules must be installed in that environment. There are two approaches:

1. **Install packages in the installer's Python environment**: Install the required packages in the installer's Python environment.
2. **Specify the full path to the module**: Specify the full path to the package installed in the user's environment.

## Usage Examples

### Using Serverless Rules (cfn-lint-serverless)

```bash
# First, install the package
pip install cfn-lint-serverless

# Run SAM template validation
sam validate --lint --extra-lint-rules="cfn_lint_serverless.rules"
```

### Using Multiple Rule Modules

#### Method 1: Specify Multiple Modules Separated by Commas

You can specify multiple rule modules separated by commas in a single option:

```bash
sam validate --lint --extra-lint-rules="module1.rules,module2.rules,module3.rules"
```

Each module is automatically separated and passed to cfn-lint.

#### Method 2: Use the Option Multiple Times

You can also specify multiple rule modules by using the `--extra-lint-rules` option multiple times:

```bash
sam validate --lint --extra-lint-rules="module1.rules" --extra-lint-rules="module2.rules"
```

## Notes

* The previously used `--serverless-rules` option is deprecated.
* It is recommended to use the new `--extra-lint-rules` option.
* If you installed SAM CLI using the installer and additional rules are not working, check if the package is installed in the installer's Python environment.

"""
Exceptions that are raised by sam package
"""
from samcli.commands.exceptions import UserException


class InvalidLocalPathError(UserException):
    def __init__(self, resource_id, property_name, local_path):
        self.resource_id = resource_id
        self.property_name = property_name
        self.local_path = local_path
        message_fmt = (
            "Parameter {property_name} of resource {resource_id} refers "
            "to a file or folder that does not exist {local_path}"
        )
        super().__init__(
            message=message_fmt.format(
                resource_id=self.resource_id, property_name=self.property_name, local_path=self.local_path
            )
        )


class InvalidTemplateUrlParameterError(UserException):
    def __init__(self, resource_id, property_name, template_path):
        self.resource_id = resource_id
        self.property_name = property_name
        self.template_path = template_path

        message_fmt = (
            "{property_name} parameter of {resource_id} resource is invalid. "
            "It must be a S3 URL or path to CloudFormation "
            "template file. Actual: {template_path}"
        )
        super().__init__(
            message=message_fmt.format(
                property_name=self.property_name, resource_id=self.resource_id, template_path=self.template_path
            )
        )


class ExportFailedError(UserException):
    def __init__(self, resource_id, property_name, property_value, ex):
        self.resource_id = resource_id
        self.property_name = property_name
        self.property_value = property_value
        self.ex = ex

        message_fmt = (
            "Unable to upload artifact {property_value} referenced "
            "by {property_name} parameter of {resource_id} resource."
            "\n"
            "{ex}"
        )

        super().__init__(
            message=message_fmt.format(
                property_value=self.property_value,
                property_name=self.property_name,
                resource_id=self.resource_id,
                ex=self.ex,
            )
        )


class PackageFailedError(UserException):
    def __init__(self, template_file, ex):
        self.template_file = template_file
        self.ex = ex

        message_fmt = "Failed to package template: {template_file}. \n {ex}"

        super().__init__(message=message_fmt.format(template_file=self.template_file, ex=self.ex))


class NoSuchBucketError(UserException):
    def __init__(self, **kwargs):
        self.kwargs = kwargs

        message_fmt = "\nS3 Bucket does not exist."

        super().__init__(message=message_fmt.format(**self.kwargs))


class BucketNotSpecifiedError(UserException):
    def __init__(self, **kwargs):
        self.kwargs = kwargs

        message_fmt = "\nS3 Bucket not specified, use --s3-bucket to specify a bucket name or run sam deploy --guided"

        super().__init__(message=message_fmt.format(**self.kwargs))


class PackageResolveS3AndS3SetError(UserException):
    def __init__(self):
        message_fmt = "Cannot use both --resolve-s3 and --s3-bucket parameters. Please use only one."

        super().__init__(message=message_fmt)


class PackageResolveS3AndS3NotSetError(UserException):
    def __init__(self):
        message_fmt = "Cannot skip both --resolve-s3 and --s3-bucket parameters. Please provide one of these arguments."

        super().__init__(message=message_fmt)

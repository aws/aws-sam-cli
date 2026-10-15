# Package local MicroVM image code

For `AWS::Serverless::MicrovmImage`, `CodeUri` can point to a local directory
containing the Dockerfile and application code, or to an existing ZIP file:

```yaml
Resources:
  Image:
    Type: AWS::Serverless::MicrovmImage
    Properties:
      Name: my-image
      BaseImageArn: !Sub arn:${AWS::Partition}:lambda:${AWS::Region}:aws:microvm-image:al2023-1
      BaseImageVersion: '0'
      CodeUri: ./microvm-code/
```

Run `sam package --s3-bucket <artifact-bucket> --output-template-file packaged.yaml`,
or use `sam deploy --resolve-s3` to package as part of deployment. Directories are
zipped through the existing artifact uploader; ZIP files are uploaded unchanged.
The packaged `CodeUri` is a string S3 URI. The existing content-derived object key
changes when the source changes and allows unchanged artifacts to be reused.
Existing S3 URIs and intrinsic references are left unchanged.

`sam build` does not execute the Dockerfile or compile MicroVM code as a Lambda
function. The AWS service builds the MicroVM image after deployment. It preserves
the source reference when relocating the template into `.aws-sam/build`, including
custom build directories; packaging that template resolves the original context.
Keep that source context available until packaging completes. `--base-dir` and
Lambda runtime/build-method options do not introduce a MicroVM build workflow.

The uploader uses the existing directory archive behavior, not `.dockerignore`
or a new `.samignore` filter. Keep only intended artifacts in the selected source
directory, or prepare a ZIP with the desired exclusions. A missing `CodeUri` does
not implicitly upload the template directory; the property remains required.

The selected bucket must be readable by the MicroVM build role. Custom KMS keys
also require the role's `kms:Decrypt` permission. This feature does not change
bucket policies, IAM roles, or service-side image creation.

Registering the artifact also makes it eligible for the existing `sam delete`
artifact cleanup, subject to the resource's retention settings, as with other
packageable resources.

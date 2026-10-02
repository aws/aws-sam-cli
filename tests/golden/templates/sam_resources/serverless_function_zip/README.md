# serverless_function_zip

Sentinel SAM case. Vanilla `AWS::Serverless::Function` with local `CodeUri`
pointing at a ZIP-packaged source dir. Locks the post-build `template.yaml`
shape (`CodeUri` rewritten to the resource-id-relative path real `sam build`
produces) and post-package shape (CodeUri rewritten to
`s3://golden-bucket/<sha256>`).

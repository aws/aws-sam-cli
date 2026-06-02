# serverless_function_zip

Sentinel SAM case. Vanilla `AWS::Serverless::Function` with local `CodeUri`
pointing at a ZIP-packaged source dir. Locks the post-build `template.yaml`
shape (artifact path normalized to `<<BUILT_ARTIFACT>>`) and post-package
shape (CodeUri rewritten to `s3://golden-bucket/<sha256>`).

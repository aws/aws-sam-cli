# lambda_function_zip

Sentinel non-SAM case. Raw `AWS::Lambda::Function` with `Code: ./src/`. Locks
the post-package output shape after the CFN-resource-list packageable walker
rewrites `Code` to `s3://golden-bucket/<sha256>`.

import os
from aws_cdk import (
    core,
    aws_lambda,
    aws_ecr
)


class LambdaContainerFunctionStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)


        image_name    = "lambdaContainerFunction"
        image_version = "latest"

        ##
        ## If use_pre_existing_image is True
        ## then use an image that already exists in ECR.
        ## Otherwise, build a new image
        ##
        use_pre_existing_image = False



        ##
        ## ECR
        ##
        if (use_pre_existing_image):

            ##
            ## Container was build previously, or elsewhere.
            ## Use the pre-existing container
            ##
            ecr_repository = aws_ecr.Repository.from_repository_attributes(self, 
                id              = "ECR", 
                repository_arn  = '{0}.dkr.ecr.{1}.amazonaws.com/{2}:{3}'.format(core.Aws.ACCOUNT_ID, core.Aws.REGION, image_name, image_version),
                repository_name = image_name
            ) ## aws_ecr.Repository.from_repository_attributes

            ##
            ## Container Image.
            ## Pulled from the ECR repository.
            ##
            ecr_image = aws_lambda.EcrImageCode(
                repository = ecr_repository
            ) ## aws_lambda.EcrImageCode

        else:
            ##
            ## Create new Container Image.
            ##
            ecr_image = aws_lambda.EcrImageCode.from_asset_image(
                directory = os.path.join(os.getcwd(), "lambda-image")
            )




        ##
        ## Lambda Function
        ##
        aws_lambda.Function(self, 
          id            = "lambdaContainerFunction",
          description   = "Sample Lambda Container Function",
          code          = ecr_image,
          ##
          ## Handler and Runtime must be *FROM_IMAGE*
          ## when provisioning Lambda from Container.
          ##
          handler       = aws_lambda.Handler.FROM_IMAGE,
          runtime       = aws_lambda.Runtime.FROM_IMAGE,
          environment   = {"hello":"world"},
          function_name = "sampleContainerFunction",
          memory_size   = 128,
          reserved_concurrent_executions = 10,
          timeout       = core.Duration.seconds(10),
        ) ## aws_lambda.Function






app = core.App()
env = {'region': 'us-east-1'}

LambdaContainerFunctionStack(app, "LambdaContainerFunctionStack", env=env)

app.synth()


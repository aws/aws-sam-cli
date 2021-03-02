Auto Create ECR Repos in Guided Deploy
====================================


What is the problem?
--------------------

With the release of Lambda Container Images Support in SAM CLI, customers today have to specify a ECR Repo URI location where images will need to be uploaded by SAM CLI after having been built. This means that customers need to have pre-created resources ready (in this case ECR repos) to go, so that they can supply them during the deploy process. This introduces friction and break in the seamless workflow that sam deploy --guided normally offers, with customers having to figure out how to create a ECR repo and how to find correct ECR URI to specify.

Current flow for deploying a template with image based function:

1. Create ECR repo: `aws ecr create-repository --repository-name myecr_repo`

2. Deploy with SAM CLI guided: `sam deploy --guided`

3. Specify image repo: `Image Repository for HelloWorldFunction []: 12345.dkr.ecr.us-west-2.amazonaws.com/helloworldfunctionrepo`

What will be changed?
---------------------

When deploying with guided, SAM CLI will prompt the option to auto create ECR repos for image based functions.
The auto created ECR repos will reside in a companion stack that gets deployed along with the actual stack. 

During each guided deploy, the functions and repos will be synced. New repos will be created for new functions and repos without an associating function will be prompt for deletion.

There will be an escape hatch to use non SAM CLI managed repos by specifying `--image-repositories` or change `samconfig.toml`.

Success criteria for the change
-------------------------------

* No context switching from SAM CLI to creating resources using other tools.

Out-of-Scope
------------

* SAM CLI will not manage lifecycles of the created resources outside of SAM CLI, i.e. customer deleting a function from console.
* Auto create repo only concerns about guided experience. Repos are assumed to be provided in CI/CD situations. However the option --resolve-image-repos will be added for auto creating repos without going through guided.

User Experience Walkthrough
---------------------------

`sam deploy --guided`

**Creating New Repos**


```
======================
Looking for config file [samconfig.toml] : Not found

Setting default arguments for 'sam deploy'
=========================================
Stack Name [sam-app]: images-app
AWS Region [us-east-1]: us-east-2
#Shows you resources changes to be deployed and require a 'Y' to initiate deploy
Confirm changes before deploy [y/N]: y
#SAM needs permission to be able to create roles to connect to the resources in your template
Allow SAM CLI IAM role creation [Y/n]: y
Save arguments to configuration file [Y/n]: y
SAM configuration file [samconfig.toml]:
SAM configuration environment [default]:
Looking for resources needed for deployment:
 S3 bucket: Found! (aws-sam-cli-managed-default-samclisourcebucket-abcdef)
 Image repositories: Not found.
 #Managed repositories will be deleted when their functions are removed from the template and deployed
 Create managed ECR repositories for all functions? [Y/n]: Y
 Creating the required resources...
 Successfully created resources for deployment!

Successfully saved arguments to config file!
 #Running 'sam deploy' for future deployments will use the parameters saved above.
 #The above parameters can be changed by modifying samconfig.toml 
 #Learn more about samconfig.toml syntax at 
 #https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-config.html

Uploading to abcdefg/7dd33d96eafcae1086a1356df982d38e 539284 / 539284.0 (100.00%)	

Deploying with the following values
===================================
Stack name                 : test-stack
Region                     : us-east-2
Confirm changeset          : True
Deployment s3 bucket       : aws-sam-cli-managed-default-samclisourcebucket-abcdef
Image repositories         : [
 {“helloWorldFunction1”:"12345.dkr.ecr.us-east-2.amazonaws.com/helloworldfunction1-abcde"},
 {“helloWorldFunction2”:"12345.dkr.ecr.us-east-2.amazonaws.com/helloworldfunction2-abcde"},
 {“helloWorldFunction3”:"12345.dkr.ecr.us-east-2.amazonaws.com/helloworldfunction3-abcde”}
]
Capabilities               : ["CAPABILITY_IAM"]
Parameter overrides        : {}
Signing profiles           : {}

Initiating deployment
```

**Deleting Unreferenced Repos**

```
Configuring SAM deploy
======================

        Looking for config file [samconfig.toml] :  Found
        Reading default arguments  :  Success

        Setting default arguments for 'sam deploy'       
        =========================================        
        Stack Name [test-stack]:
        AWS Region [us-east-2]: 
        #Shows you resources changes to be deployed and require a 'Y' to initiate deploy
        Confirm changes before deploy [Y/n]: y
        #SAM needs permission to be able to create roles to connect to the resources in your template
        Allow SAM CLI IAM role creation [Y/n]: y
        HelloWorldFunction4 may not have authorization defined, Is this okay? [y/N]: y
        HelloWorldFunction5 may not have authorization defined, Is this okay? [y/N]: y
        Save arguments to configuration file [Y/n]: y
        SAM configuration file [samconfig.toml]: 
        SAM configuration environment [default]: 

        Looking for resources needed for deployment: Found!

                Managed S3 bucket: aws-sam-cli-managed-default-samclisourcebucket-abcdef
                A different default S3 bucket can be set in samconfig.toml

                Image repositories: Not found.
                #Managed repositories will be deleted when their functions are removed from the template and deployed
                Create managed ECR repositories for all functions? [Y/n]: y
                Checking for unreferenced ECR repositories to clean-up: 2 found
                 12345.dkr.ecr.us-east-2.amazonaws.com/helloworldfunction1-abcde
                 12345.dkr.ecr.us-east-2.amazonaws.com/helloworldfunction2-abcde
                 Delete the unreferenced repositories listed above when deploying? [y/N]: y

        helloworldfunction4:python3.8-v1 to be pushed to 12345.dkr.ecr.us-east-2.amazonaws.com/helloworldfunction4-abcde:helloworldfunction4-7bfff073dfcf-python3.8-v1
        helloworldfunction5:python3.8-v1 to be pushed to 12345.dkr.ecr.us-east-2.amazonaws.com/helloworldfunction5-abcde:helloworldfunction5-7bfff073dfcf-python3.8-v1


        Saved arguments to config file
        Running 'sam deploy' for future deployments will use the parameters saved above.
        The above parameters can be changed by modifying samconfig.toml
        Learn more about samconfig.toml syntax at
        https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-config.html


        Deploying with following values
        ===============================
        Stack name                   : auto-ecr-guided-test
        Region                       : us-west-2
        Confirm changeset            : True
        Deployment image repository  :
                                       {
                                           "HelloWorldFunction3": "12345.dkr.ecr.us-east-2.amazonaws.com/helloworldfunction3-abcde",
                                           "HelloWorldFunction4": "12345.dkr.ecr.us-east-2.amazonaws.com/helloworldfunction4-abcde",
                                           "HelloWorldFunction5": "12345.dkr.ecr.us-east-2.amazonaws.com/helloworldfunction5-abcde"
                                       }
        Deployment s3 bucket         : aws-sam-cli-managed-default-samclisourcebucket-abcde
        Capabilities                 : ["CAPABILITY_IAM"]
        Parameter overrides          : {}
        Signing Profiles             : {}
```


Implementation
==============

CLI Changes
-----------

* Add new prompt for guided deploy. 
  * `Create managed ECR repositories for all functions? [Y/n]: y`
* Add `--resolve-image-repos` to non-guided deploy


### Breaking Change

* Not a breaking change.

Design
------

**Companion Stack Naming Scheme**
```
#Escaped StackName with only common accpetable characters
escaped_stack_name = re.sub(r"[^a-z0-9]", "", stack_name.lower())
#Escaped LambdaName with only common accpetable characters
escaped_lambda_logical_id = re.sub(r"[^a-z0-9]", "", lambda_logical_id.lower())
#MD5 of the original StackName.
stack_md5 = hash.str_checksum(stack_name)
#MD5 of the original LambdaName
function_md5 = hash.str_checksum(lambda_logical_id)

#MD5 is used to avoid two having the same escaped name with different Lambda Functions
#For example: Helloworld and HELLO-WORLD
repo_logical_id =
    lambda_logical_id [:52] + function_md5 [:8] + "Repo"
    #52 + 8 + 4 = 64 max char
    
repo_name = 
    escaped_stack_name + stack_md5[:8] + "/" + escaped_lambda_logical_id + function_md5[:8] + "repo"
    #128        +         8      +  1  +     64      +        8      +      4 = 213 max char
    
companion_stack_name = 
    stack_name[:104] + "-" + stack_md5[:8] + "-" + "CompanionStack"
    #104 + 1 + 8 + 1 + 14 = 128 max char
    
repo_output_logical_id = 
    lambda_logical_id[:52] + function_md5 [:8] + "Out"
    #52 + 8 + 3 = 63 max char

Exmaple:
    Input:
        Customer Stack Name: Hello-World-Stack
        Function 1 Logical ID: TestFunction01
        Function 2 Logical ID: AnotherTestFunction02
    Output:
        Companion Stack Name: Hello-World-Stack-925976eb-CompanionStack
        Function 1 Repo Logical ID: TestFunction0150919004Repo
        Function 1 Repo Name: helloworldstack925976eb/testfunction0150919004repo
        Function 2 Repo Logical ID: AnotherTestFunction025c2cfd8cRepo
        Function 2 Repo Name: helloworldstack925976eb/anothertestfunction025c2cfd8crepo
```

**Companion Stack Structure**
```
AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: AWS SAM CLI Managed ECR Repo Stack
Metadata:
  SamCliInfo: 1.18.0
  CompanionStackname:  Hello-World-Stack-925976eb-CompanionStack

Resources:

  TestFunction0150919004Repo:
    Type: AWS::ECR::Repository
    Properties:
      RepositoryName: helloworldstack925976eb/testfunction0150919004repo
      Tags:
        - Key: ManagedStackSource
          Value: AwsSamCli
        - Key: AwsSamCliCompanionStack
          Value: Hello-World-Stack-925976eb-CompanionStack

      RepositoryPolicyText: 
        Version: "2012-10-17"
        Statement:
          -
            Sid: AllowLambdaSLR
            Effect: Allow
            Principal:
              Service:
                - "lambda.amazonaws.com"
            Action:
                - "ecr:GetDownloadUrlForLayer"
                - "ecr:GetRepositoryPolicy"
                - "ecr:BatchGetImage"

  AnotherTestFunction025c2cfd8cRepo:
    Type: AWS::ECR::Repository
    Properties:
      RepositoryName: helloworldstack925976eb/anothertestfunction025c2cfd8crepo
      Tags:
        - Key: ManagedStackSource
          Value: AwsSamCli
        - Key: AwsSamCliCompanionStack
          Value: Hello-World-Stack-925976eb-CompanionStack

      RepositoryPolicyText: 
        Version: "2012-10-17"
        Statement:
          -
            Sid: AllowLambdaSLR
            Effect: Allow
            Principal:
              Service:
                - "lambda.amazonaws.com"
            Action:
                - "ecr:GetDownloadUrlForLayer"
                - "ecr:GetRepositoryPolicy"
                - "ecr:BatchGetImage"

Outputs:

  None:
    Value: !Sub ${AWS::AccountId}.dkr.ecr.${AWS::Region}.${AWS::URLSuffix}/${TestFunction0150919004Repo}

  None:
    Value: !Sub ${AWS::AccountId}.dkr.ecr.${AWS::Region}.${AWS::URLSuffix}/${AnotherTestFunction025c2cfd8cRepo}
```

Documentation Changes
=====================
* New option `--resolve-image-repos`. This option will auto create repos without the needs of going through guided experience. 

Open Issues
============
https://github.com/aws/aws-sam-cli/issues/2447

Task Breakdown
==============

-   \[x\] Send a Pull Request with this design document
-   \[ \] Build Companion Stack Manager
-   \[ \] Change Deploy CLI
-   \[ \] Unit tests
-   \[ \] Functional Tests
-   \[ \] Integration tests
-   \[ \] Update documentation

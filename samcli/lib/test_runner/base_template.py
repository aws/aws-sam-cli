base_template_json = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Description": "Sample Template to deploy and run test container with Fargate",
    "Resources": {
        "ContainerIAMRole": {
            "Type": "AWS::IAM::Role",
            "Properties": {
                "Description": "Allows Fargate task to access S3 bucket to download tests and upload results",
                "AssumeRolePolicyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": ["ecs-tasks.amazonaws.com"]},
                            "Action": ["sts:AssumeRole"],
                        }
                    ],
                },
                "Policies": [
                    {
                        "PolicyName": "ContainerPermissions",
                        "PolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Sid": "S3BucketAccess",
                                    "Effect": "Allow",
                                    "Action": ["s3:PutObject", "s3:GetObject"],
                                    "Resource": {
                                        "Fn::Sub": ["arn:aws:s3:::${bucket}/*", {"bucket": {"Ref": "S3Bucket"}}]
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        },
        "TaskDefinition": {
            "Type": "AWS::ECS::TaskDefinition",
            "Properties": {
                "RequiresCompatibilities": ["FARGATE"],
                "ExecutionRoleArn": "{{ ecs_task_exec_role_arn }}",
                "TaskRoleArn": {"Ref": "ContainerIAMRole"},
                "Cpu": "{{ cpu }}",
                "Memory": "{{ memory }}",
                "NetworkMode": "awsvpc",
                "ContainerDefinitions": [
                    {
                        "Name": "cloud-test-python-container",
                        "Image": "{{ image_uri }}",
                        "PortMappings": [{"ContainerPort": 8080, "Protocol": "tcp"}],
                        "LogConfiguration": {
                            "LogDriver": "awslogs",
                            "Options": {
                                "awslogs-region": {"Ref": "AWS::Region"},
                                "awslogs-group": {"Ref": "LogGroup"},
                                "awslogs-stream-prefix": "ecs",
                            },
                        },
                    }
                ],
            },
        },
        "LogGroup": {"Type": "AWS::Logs::LogGroup", "Properties": {"LogGroupName": "cloud-test-loggroup"}},
        "ECSCluster": {"Type": "AWS::ECS::Cluster", "Properties": {"ClusterName": "cloud-test-fargate-cluster"}},
        "SecurityGroup": {
            "Type": "AWS::EC2::SecurityGroup",
            "Properties": {
                "GroupDescription": "cloud-test security group",
                "GroupName": "cloud-test-security-group",
                "VpcId": "{{ vpc_id }}",
            },
        },
        "S3Bucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "{{ s3_bucket_name }}"}},
    },
}

"""
File that holds functions for generating different types of events
"""

from samcli.local.events.api_event import ContextIdentity, ApiGatewayLambdaEvent, RequestContext


def generate_s3_event(region, bucket, key):
    """
    Generates a S3 Event

    :param str region: AWS Region
    :param str bucket: Name of the S3 bucket
    :param str key: S3 Bucket Key
    :return dict: Dictionary representing the S3 Event
    """
    return {
        "Records": [{
            "eventVersion": "2.0",
            "eventTime": "1970-01-01T00:00:00.000Z",
            "requestParameters": {
                "sourceIPAddress": "127.0.0.1"
            },
            "s3": {
                "configurationId": "testConfigRule",
                "object": {
                    "eTag": "0123456789abcdef0123456789abcdef",
                    "sequencer": "0A1B2C3D4E5F678901",
                    "key": key,
                    "size": 1024
                },
                "bucket": {
                    "arn": "arn:aws:s3:::{}".format(bucket),
                    "name": bucket,
                    "ownerIdentity": {
                        "principalId": "EXAMPLE"
                    }
                },
                "s3SchemaVersion": "1.0"
            },
            "responseElements": {
                "x-amz-id-2": "EXAMPLE123/5678abcdefghijklambdaisawesome/mnopqrstuvwxyzABCDEFGH",
                "x-amz-request-id": "EXAMPLE123456789"
            },
            "awsRegion": region,
            "eventName": "ObjectCreated:Put",
            "userIdentity": {
                "principalId": "EXAMPLE"
            },
            "eventSource": "aws:s3"
        }]
    }


def generate_sns_event(message, topic, subject):
    """
    Generates a SNS Event

    :param str message: Message sent to the topic
    :param str topic: Name of the Topic
    :param str subject: Subject of the Topic
    :return dict: Dictionary representing the SNS Event
    """
    return {
        "Records": [{
            "EventVersion": "1.0",
            "EventSubscriptionArn": "arn:aws:sns:EXAMPLE",
            "EventSource": "aws:sns",
            "Sns": {
                "SignatureVersion": "1",
                "Timestamp": "1970-01-01T00:00:00.000Z",
                "Signature": "EXAMPLE",
                "SigningCertUrl": "EXAMPLE",
                "MessageId": "95df01b4-ee98-5cb9-9903-4c221d41eb5e",
                "Message": message,
                "MessageAttributes": {
                    "Test": {
                        "Type": "String",
                        "Value": "TestString"
                    },
                    "TestBinary": {
                        "Type": "Binary",
                        "Value": "TestBinary"
                    }
                },
                "Type": "Notification",
                "UnsubscribeUrl": "EXAMPLE",
                "TopicArn": topic,
                "Subject": subject
            }
        }]
    }


def generate_schedule_event(region):
    """
    Generates a Scheduled Event

    :param str region: AWS Region
    :return dict: Dictionary representing the Schedule Event
    """
    return {
        "account": "123456789012",
        "region": region,
        "detail": {},
        "detail-type": "Scheduled Event",
        "source": "aws.events",
        "time": "1970-01-01T00:00:00Z",
        "id": "cdc73f9d-aea9-11e3-9d5a-835b769c0d9c",
        "resources": [
            "arn:aws:events:us-east-1:123456789012:rule/my-schedule"
        ]
    }


def generate_dynamodb_event(region):
    """
    Generates a DynamoDG Event

    :param str region: AWS region
    :return dict: Dictionary representing the DynamoDB Event
    """
    return {
        "Records": [
            {
                "eventID": "1",
                "eventVersion": "1.0",
                "dynamodb": {
                    "Keys": {
                        "Id": {
                            "N": "101"
                        }
                    },
                    "NewImage": {
                        "Message": {
                            "S": "New item!"
                        },
                        "Id": {
                            "N": "101"
                        }
                    },
                    "StreamViewType": "NEW_AND_OLD_IMAGES",
                    "SequenceNumber": "111",
                    "SizeBytes": 26
                },
                "awsRegion": region,
                "eventName": "INSERT",
                "eventSourceARN": "arn:aws:dynamodb:{}:account-id:table/"
                                  "ExampleTableWithStream/stream/2015-06-27T00:48:05.899".format(region),
                "eventSource": "aws:dynamodb"
            },
            {
                "eventID": "2",
                "eventVersion": "1.0",
                "dynamodb": {
                    "OldImage": {
                        "Message": {
                            "S": "New item!"
                        },
                        "Id": {
                            "N": "101"
                        }
                    },
                    "SequenceNumber": "222",
                    "Keys": {
                        "Id": {
                            "N": "101"
                        }
                    },
                    "SizeBytes": 59,
                    "NewImage": {
                        "Message": {
                            "S": "This item has changed"
                        },
                        "Id": {
                            "N": "101"
                        }
                    },
                    "StreamViewType": "NEW_AND_OLD_IMAGES"
                },
                "awsRegion": region,
                "eventName": "MODIFY",
                "eventSourceARN":
                    "arn:aws:dynamodb:{}:account-id:table/"
                    "ExampleTableWithStream/stream/2015-06-27T00:48:05.899".format(region),
                "eventSource": "aws:dynamodb"
            },
            {
                "eventID": "3",
                "eventVersion": "1.0",
                "dynamodb": {
                    "Keys": {
                        "Id": {
                            "N": "101"
                        }
                    },
                    "SizeBytes": 38,
                    "SequenceNumber": "333",
                    "OldImage": {
                        "Message": {
                            "S": "This item has changed"
                        },
                        "Id": {
                            "N": "101"
                        }
                    },
                    "StreamViewType": "NEW_AND_OLD_IMAGES"
                },
                "awsRegion": region,
                "eventName": "REMOVE",
                "eventSourceARN": "arn:aws:dynamodb:{}:account-id:table/"
                                  "ExampleTableWithStream/stream/2015-06-27T00:48:05.899".format(region),
                "eventSource": "aws:dynamodb"
            }
        ]
    }


def generate_kinesis_event(region, partition, sequence, data):
    """
    Generates a Kinesis Event

    :param str region: AWS Region
    :param str partition: PartitionKey in Kinesis
    :param str sequence: Sequence Number as a string
    :param str data: Data for the stream
    :return dict: Dictionary representing the Kinesis Event
    """
    return {
        "Records": [{
            "eventID": "shardId-000000000000:{}".format(sequence),
            "eventVersion": "1.0",
            "kinesis": {
                "approximateArrivalTimestamp": 1428537600,
                "partitionKey": partition,
                "data": data,
                "kinesisSchemaVersion": "1.0",
                "sequenceNumber": sequence
            },
            "invokeIdentityArn": "arn:aws:iam::EXAMPLE",
            "eventName": "aws:kinesis:record",
            "eventSourceARN": "arn:aws:kinesis:EXAMPLE",
            "eventSource": "aws:kinesis",
            "awsRegion": region
        }]
    }


def generate_api_event(method, body, resource, path):
    """
    Generates an Api Event

    :param str method: HTTP Method of the request
    :param str body: Body of the request
    :param str resource: Api Gateway resource path
    :param str path: Request path
    :return dict: Dictionary representing the Api Event
    """
    headers = {
        "Via": "1.1 08f323deadbeefa7af34d5feb414ce27.cloudfront.net (CloudFront)",
        "Accept-Language": "en-US,en;q=0.8",
        "CloudFront-Is-Desktop-Viewer": "true",
        "CloudFront-Is-SmartTV-Viewer": "false",
        "CloudFront-Is-Mobile-Viewer": "false",
        "X-Forwarded-For": "127.0.0.1, 127.0.0.2",
        "CloudFront-Viewer-Country": "US",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Upgrade-Insecure-Requests": "1",
        "X-Forwarded-Port": "443",
        "Host": "1234567890.execute-api.us-east-1.amazonaws.com",
        "X-Forwarded-Proto": "https",
        "X-Amz-Cf-Id": "aaaaaaaaaae3VYQb9jd-nvCd-de396Uhbp027Y2JvkCPNLmGJHqlaA==",
        "CloudFront-Is-Tablet-Viewer": "false",
        "Cache-Control": "max-age=0",
        "User-Agent": "Custom User Agent String",
        "CloudFront-Forwarded-Proto": "https",
        "Accept-Encoding": "gzip, deflate, sdch"
    }

    query_params = {
        "foo": "bar"
    }

    path_params = {
        "proxy": path
    }

    identity = ContextIdentity(source_ip='127.0.0.1')

    context = RequestContext(resource_path=resource,
                             http_method=method,
                             stage="prod",
                             identity=identity,
                             path=resource)

    event = ApiGatewayLambdaEvent(http_method=method,
                                  body=body,
                                  resource=resource,
                                  request_context=context,
                                  query_string_params=query_params,
                                  headers=headers,
                                  path_parameters=path_params,
                                  path=path)

    return event.to_dict()

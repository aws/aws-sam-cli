from unittest import TestCase

from samcli.commands.local.lib.events import generate_api_event, generate_dynamodb_event, generate_kinesis_event, \
    generate_schedule_event, generate_sns_event, generate_s3_event


class TestGeneratedEvent(TestCase):

    def test_s3_event(self):
        actual_event = generate_s3_event("us-east-1", "bucket", "key")

        expected_event = {
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
                        "key": "key",
                        "size": 1024
                    },
                    "bucket": {
                        "arn": "arn:aws:s3:::bucket",
                        "name": "bucket",
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
                "awsRegion": "us-east-1",
                "eventName": "ObjectCreated:Put",
                "userIdentity": {
                    "principalId": "EXAMPLE"
                },
                "eventSource": "aws:s3"
            }]
        }

        self.assertEquals(actual_event, expected_event)

    def test_sns_event(self):
        actual_event = generate_sns_event("message", "topic", "subject")

        expected_event = {
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
                    "Message": "message",
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
                    "TopicArn": "topic",
                    "Subject": "subject"
                }
            }]
        }

        self.assertEquals(actual_event, expected_event)

    def test_api_event(self):
        actual_event = generate_api_event("GET", "body of the request", "/path", "/path")
        self.maxDiff = None

        expected_event = {
            'body': 'body of the request',
            'headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, sdch',
                'Accept-Language': 'en-US,en;q=0.8',
                'Cache-Control': 'max-age=0',
                'CloudFront-Forwarded-Proto': 'https',
                'CloudFront-Is-Desktop-Viewer': 'true',
                'CloudFront-Is-Mobile-Viewer': 'false',
                'CloudFront-Is-SmartTV-Viewer': 'false',
                'CloudFront-Is-Tablet-Viewer': 'false',
                'CloudFront-Viewer-Country': 'US',
                'Host': '1234567890.execute-api.us-east-1.amazonaws.com',
                'Upgrade-Insecure-Requests': '1',
                'User-Agent': 'Custom User Agent String',
                'Via': '1.1 08f323deadbeefa7af34d5feb414ce27.cloudfront.net (CloudFront)',
                'X-Amz-Cf-Id': 'aaaaaaaaaae3VYQb9jd-nvCd-de396Uhbp027Y2JvkCPNLmGJHqlaA==',
                'X-Forwarded-For': '127.0.0.1, 127.0.0.2',
                'X-Forwarded-Port': '443',
                'X-Forwarded-Proto': 'https'
            },
            'httpMethod': 'GET',
            'isBase64Encoded': False,
            'path': '/path',
            'pathParameters': {'proxy': '/path'},
            'queryStringParameters': {'foo': 'bar'},
            'requestContext': {
                'accountId': "123456789012",
                'apiId': "1234567890",
                'extendedRequestId': None,
                'httpMethod': 'GET',
                'identity': {
                    'accountId': None,
                    'apiKey': None,
                    'caller': None,
                    'cognitoAuthenticationProvider': None,
                    'cognitoAuthenticationType': None,
                    'cognitoIdentityPoolId': None,
                    'sourceIp': '127.0.0.1',
                    'user': None,
                    'userAgent': "Custom User Agent String",
                    'userArn': None
                },
                'path': '/path',
                'requestId': "c6af9ac6-7b61-11e6-9a41-93e8deadbeef",
                'resourceId': "123456",
                'resourcePath': '/path',
                'stage': 'prod'
            },
            'resource': '/path',
            'stageVariables': None
        }

        self.assertEquals(actual_event, expected_event)

    def test_dynamodb_event(self):
        actual_event = generate_dynamodb_event("us-east-1")

        expected_event = {
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
                    "awsRegion": "us-east-1",
                    "eventName": "INSERT",
                    "eventSourceARN": "arn:aws:dynamodb:us-east-1:account-id:table/"
                                      "ExampleTableWithStream/stream/2015-06-27T00:48:05.899",
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
                    "awsRegion": "us-east-1",
                    "eventName": "MODIFY",
                    "eventSourceARN": "arn:aws:dynamodb:us-east-1:account-id:table/"
                                      "ExampleTableWithStream/stream/2015-06-27T00:48:05.899",
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
                    "awsRegion": "us-east-1",
                    "eventName": "REMOVE",
                    "eventSourceARN": "arn:aws:dynamodb:us-east-1:account-id:table/"
                                      "ExampleTableWithStream/stream/2015-06-27T00:48:05.899",
                    "eventSource": "aws:dynamodb"
                }
            ]
        }

        self.assertEquals(actual_event, expected_event)

    def test_scheudle_event(self):
        actual_event = generate_schedule_event("us-east-1")

        expected_event = {
            "account": "123456789012",
            "region": "us-east-1",
            "detail": {},
            "detail-type": "Scheduled Event",
            "source": "aws.events",
            "time": "1970-01-01T00:00:00Z",
            "id": "cdc73f9d-aea9-11e3-9d5a-835b769c0d9c",
            "resources": [
                "arn:aws:events:us-east-1:123456789012:rule/my-schedule"
            ]
        }

        self.assertEquals(actual_event, expected_event)

    def test_kinesis_event(self):
        actual_event = generate_kinesis_event("us-east-1", "partition", "sequence", "this is data")

        expected_event = {
            "Records": [{
                "eventID": "shardId-000000000000:sequence",
                "eventVersion": "1.0",
                "kinesis": {
                    "approximateArrivalTimestamp": 1428537600,
                    "partitionKey": "partition",
                    "data": "this is data",
                    "kinesisSchemaVersion": "1.0",
                    "sequenceNumber": "sequence"
                },
                "invokeIdentityArn": "arn:aws:iam::EXAMPLE",
                "eventName": "aws:kinesis:record",
                "eventSourceARN": "arn:aws:kinesis:EXAMPLE",
                "eventSource": "aws:kinesis",
                "awsRegion": "us-east-1"
            }]
        }

        self.assertEquals(actual_event, expected_event)

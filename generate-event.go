package main

import (
	"encoding/base64"
	"fmt"
	"os"
	"text/template"

	"github.com/codegangsta/cli"
)

var events = map[string]string{
	"S3":                   s3Event,
	"SNS":                  snsEvent,
	"Kinesis":              kinesisEvent,
	"DynamoDB":             dynamodbEvent,
	"Api":                  apiEvent,
	"Schedule":             scheduleEvent,
	"CloudFormation":       cloudFormationEvent,
	"SES":                  sesEvent,
	"CloudWatchLogs":       cloudWatchLogsEvent,
	"CognitoSyncTrigger":   cognitoSyncTriggerEvent,
	"Lex":                  lexEvent,
}

func generate(eventType string, c *cli.Context) {

	sample, ok := events[eventType]
	if !ok {
		fmt.Printf("Unsupported event type: %s", eventType)
		os.Exit(1)
	}

	t, err := template.New("event").Parse(sample)
	if err != nil {
		fmt.Printf("Failed to load sample %s event: %s", eventType, err)
		os.Exit(1)
	}

	switch eventType {
	case "S3":
		t.Execute(os.Stdout, struct {
			Region string
			Bucket string
			Key    string
		}{
			Region: c.String("region"),
			Bucket: c.String("bucket"),
			Key:    c.String("key"),
		})
		os.Exit(0)

	case "SNS":
		t.Execute(os.Stdout, struct {
			Message string
			Subject string
			Topic   string
		}{
			Message: c.String("message"),
			Subject: c.String("subject"),
			Topic:   c.String("topic"),
		})
		os.Exit(0)

	case "Kinesis":
		t.Execute(os.Stdout, struct {
			Region    string
			Partition string
			Sequence  string
			Data      string
		}{
			Region:    c.String("region"),
			Partition: c.String("partition"),
			Sequence:  c.String("sequence"),
			Data:      base64.StdEncoding.EncodeToString([]byte(c.String("data"))),
		})
		os.Exit(0)

	case "DynamoDB":
		t.Execute(os.Stdout, struct {
			Region string
		}{
			Region: c.String("region"),
		})
		os.Exit(0)

	case "Api":
		t.Execute(os.Stdout, struct {
			Method   string
			Body     string
			Resource string
			Path     string
		}{
			Method:   c.String("method"),
			Body:     c.String("body"),
			Resource: c.String("resource"),
			Path:     c.String("path"),
		})
		os.Exit(0)

	case "Schedule":
		t.Execute(os.Stdout, struct {
			Region string
		}{
			Region: c.String("region"),
		})
		os.Exit(0)

	case "CloudFormation":
		fmt.Println(sample)
		os.Exit(0)

	case "SES":
		fmt.Println(sample)
		os.Exit(0)

	case "CloudWatchLogs":
		t.Execute(os.Stdout, struct {
			Data string
		}{
			Data: base64.StdEncoding.EncodeToString([]byte(c.String("data"))),
		})
		os.Exit(0)

	case "CognitoSyncTrigger":
		t.Execute(os.Stdout, struct {
			Region string
		}{
			Region: c.String("region"),
		})
		os.Exit(0)

	case "Lex":
		fmt.Println(sample)
		os.Exit(0)
	}

	fmt.Printf("Error - event type %s not implemented\n", eventType)
	os.Exit(1)

}

var s3Event = `{
  "Records": [
    {
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
          "key": "{{.Key}}",
          "size": 1024
        },
        "bucket": {
          "arn": "arn:aws:s3:::{{.Bucket}}",
          "name": "{{.Bucket}}",
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
      "awsRegion": "{{.Region}}",
      "eventName": "ObjectCreated:Put",
      "userIdentity": {
        "principalId": "EXAMPLE"
      },
      "eventSource": "aws:s3"
    }
  ]
}`

var snsEvent = `{
  "Records": [
    {
      "EventVersion": "1.0",
      "EventSubscriptionArn": "arn:aws:sns:EXAMPLE",
      "EventSource": "aws:sns",
      "Sns": {
        "SignatureVersion": "1",
        "Timestamp": "1970-01-01T00:00:00.000Z",
        "Signature": "EXAMPLE",
        "SigningCertUrl": "EXAMPLE",
        "MessageId": "95df01b4-ee98-5cb9-9903-4c221d41eb5e",
        "Message": "{{.Message}}",
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
        "TopicArn": "{{.Topic}}",
        "Subject": "{{.Subject}}"
      }
    }
  ]
}`

var kinesisEvent = `{
  "Records": [
    {
      "eventID": "shardId-000000000000:{{.Sequence}}",
      "eventVersion": "1.0",
      "kinesis": {
        "approximateArrivalTimestamp": 1428537600,
        "partitionKey": "{{.Partition}}",
        "data": "{{.Data}}",
        "kinesisSchemaVersion": "1.0",
        "sequenceNumber": "{{.Sequence}}"
      },
      "invokeIdentityArn": "arn:aws:iam::EXAMPLE",
      "eventName": "aws:kinesis:record",
      "eventSourceARN": "arn:aws:kinesis:EXAMPLE",
      "eventSource": "aws:kinesis",
      "awsRegion": "{{.Region}}"
    }
  ]
}
`
var dynamodbEvent = `{
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
      "awsRegion": "{{.Region}}",
      "eventName": "INSERT",
      "eventSourceARN": "arn:aws:dynamodb:{{.Region}}:account-id:table/ExampleTableWithStream/stream/2015-06-27T00:48:05.899",
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
      "awsRegion": "{{.Region}}",
      "eventName": "MODIFY",
      "eventSourceARN": "arn:aws:dynamodb:{{.Region}}:account-id:table/ExampleTableWithStream/stream/2015-06-27T00:48:05.899",
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
      "awsRegion": "{{.Region}}",
      "eventName": "REMOVE",
      "eventSourceARN": "arn:aws:dynamodb:{{.Region}}:account-id:table/ExampleTableWithStream/stream/2015-06-27T00:48:05.899",
      "eventSource": "aws:dynamodb"
    }
  ]
}`

var apiEvent = `{
  "body": "{{.Body}}",
  "resource": "{{.Resource}}",
  "requestContext": {
    "resourceId": "123456",
    "apiId": "1234567890",
    "resourcePath": "{{.Resource}}",
    "httpMethod": "{{.Method}}",
    "requestId": "c6af9ac6-7b61-11e6-9a41-93e8deadbeef",
    "accountId": "123456789012",
    "identity": {
      "apiKey": null,
      "userArn": null,
      "cognitoAuthenticationType": null,
      "caller": null,
      "userAgent": "Custom User Agent String",
      "user": null,
      "cognitoIdentityPoolId": null,
      "cognitoIdentityId": null,
      "cognitoAuthenticationProvider": null,
      "sourceIp": "127.0.0.1",
      "accountId": null
    },
    "stage": "prod"
  },
  "queryStringParameters": {
    "foo": "bar"
  },
  "headers": {
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
  },
  "pathParameters": {
    "proxy": "{{.Path}}"
  },
  "httpMethod": "{{.Method}}",
  "stageVariables": {
    "baz": "qux"
  },
  "path": "{{.Path}}"
}`

var scheduleEvent = `{
  "account": "123456789012",
  "region": "{{.Region}}",
  "detail": {},
  "detail-type": "Scheduled Event",
  "source": "aws.events",
  "time": "1970-01-01T00:00:00Z",
  "id": "cdc73f9d-aea9-11e3-9d5a-835b769c0d9c",
  "resources": [
    "arn:aws:events:us-east-1:123456789012:rule/my-schedule"
  ]
}`

var cloudFormationEvent = `{
	"StackId": stackidarn,
	"ResponseURL": "http://pre-signed-S3-url-for-response",
	"ResourceProperties": {
		"StackName": "stack-name",
		"List": [
			"1",
			"2",
			"3"
		]
	},
	"RequestType": "Create",
	"ResourceType": "Custom::TestResource",
	"RequestId": "unique id for this create request",
	"LogicalResourceId": "MyTestResource"
}`

var sesEvent = `
     "Records": [
     {
       "eventVersion": "1.0",
       "ses": {
       "mail": {
       "commonHeaders": {
       "from": [
       "Jane Doe <janedoe@example.com>"
       ],
       "to": [
       "johndoe@example.com"
       ],
      "returnPath": "janedoe@example.com",
      "messageId": "<0123456789example.com>",
      "date": "Wed, 7 Oct 2015 12:34:56 -0700",
      "subject": "Test Subject"
      },
      "source": "janedoe@example.com",
      "timestamp": "1970-01-01T00:00:00.000Z",
      "destination": [
      "johndoe@example.com"
       ],
       "headers": [
       {
        "name": "Return-Path",
        "value": "<janedoe@example.com>"
       },
       {
         "name": "Received",
         "value": "from mailer.example.com (mailer.example.com [203.0.113.1]) by inbound-smtp.us-west-2.amazonaws.com with SMTP id o3vrnil0e2ic28trm7dfhrc2v0cnbeccl4nbp0g1x for johndoe@example.com; Wed, 07 Oct 2015 12:34:56 +0000 (UTC)"
       },
       {
        "name": "DKIM-Signature",
        "value": "v=1; a=rsa-sha256; c=relaxed/relaxed; d=example.com; s=example; h=mime-version:from:date:message-id:subject:to:content-type; bh=jX3F0bCAI7sIbkHyy3mLYO28ieDQz2R0P8HwQkklFj4x=; b=sQwJ+LMe9RjkesGu+vqU56asvMhrLRRYrWCbVt6WJulueecwfEwRf9JVWgkBTKiL6m2hr70xDbPWDhtLdLO+jB3hzjVnXwK3pYIOHw3vxG6NtJ6o61XSUwjEsp9tdyxQjZf2HNYee873832l3K1EeSXKzxYk9Pwqcpi3dMC74ct9GukjIevf1H46hm1L2d9VYTL0LGZGHOAyMnHmEGB8ZExWbI+k6khpurTQQ4sp4PZPRlgHtnj3Zzv7nmpTo7dtPG5z5S9J+L+Ba7dixT0jn3HuhaJ9b+VThboo4YfsX9PMNhWWxGjVksSFOcGluPO7QutCPyoY4gbxtwkN9W69HA=="
       },
       {
        "name": "MIME-Version",
        "value": "1.0"
       },
       {
        "name": "From",
        "value": "Jane Doe <janedoe@example.com>"
       },
       {
         "name": "Date",
         "value": "Wed, 7 Oct 2015 12:34:56 -0700"
       },
       {
         "name": "Message-ID",
         "value": "<0123456789example.com>"
      },
      {
         "name": "Subject",
         "value": "Test Subject"
      },
      {
        "name": "To",
        value": "johndoe@example.com"
      },
      {
        "name": "Content-Type",
        "value": "text/plain; charset=UTF-8"
      }
      ],
        "headersTruncated": false,
        "messageId": "o3vrnil0e2ic28trm7dfhrc2v0clambda4nbp0g1x"
      },
        "receipt": {
        "recipients": [
        "johndoe@example.com"
        ],
       "timestamp": "1970-01-01T00:00:00.000Z",
       "spamVerdict": {
       "status": "PASS"
      },
      "dkimVerdict": {
      "status": "PASS"
      },
      "processingTimeMillis": 574,
      "action": {
      "type": "Lambda",
      "invocationType": "Event",
      "functionArn": functionarn
      },
      "spfVerdict": {
      "status": "PASS"
      },
      "virusVerdict": {
      "status": "PASS"
      }
      }
      },
      "eventSource": "aws:ses"
      }
      ]
      }]}`

var cloudWatchLogsEvent = `{
 	"awslogs": {
 		"data": "{{.Data}}"
 	}
 }`

var cognitoSyncTriggerEvent = `{
  "datasetName": "datasetName",
  "eventType": "SyncTrigger",
  "region": "{{.Region}}",
  "identityId": "identityId",
  "datasetRecords": {
    "SampleKey2": {
      "newValue": "newValue2",
      "oldValue": "oldValue2",
      "op": "replace"
    },
    "SampleKey1": {
      "newValue": "newValue1",
      "oldValue": "oldValue1",
      "op": "replace"
    }
  },
  "identityPoolId": "identityPoolId",
  "version": 2
}`

var lexEvent = `{
  "messageVersion": "1.0",
  "invocationSource": "FulfillmentCodeHook or DialogCodeHook",
  "userId": "user-id specified in the POST request to Amazon Lex.",
  "sessionAttributes": {
     "key1": "value1",
     "key2": "value2",
  },
  "bot": {
    "name": "bot-name",
    "alias": "bot-alias",
    "version": "bot-version"
  },
  "outputDialogMode": "Text or Voice, based on ContentType request header in runtime API request",
  "currentIntent": {
    "name": "intent-name",
    "slots": {
      "slot-name": "value",
      "slot-name": "value",
      "slot-name": "value"
    },
    "confirmationStatus": "None, Confirmed, or Denied
      (intent confirmation, if configured)"
  }
}`
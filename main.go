package main

import (
	"fmt"
	"os"

	"github.com/codegangsta/cli"
	"github.com/fatih/color"
)

// BuildVersion is replaced automatically by the build process
var BuildVersion = "SNAPSHOT"

// BuildDate is replaced automatically by the build process
var BuildDate = "NA"

func main() {

	color.Unset()

	v, err := checkVersion()
	if err == nil && !v.IsUpToDate {
		fmt.Fprintf(os.Stderr, "A newer version of the AWS SAM CLI is available!\n")
		fmt.Fprintf(os.Stderr, "Your version:   %s\n", BuildVersion)
		fmt.Fprintf(os.Stderr, "Latest version: %s\n", v.LatestVersion)
		fmt.Fprintf(os.Stderr, "See https://github.com/awslabs/aws-sam-cli for upgrade instructions\n\n")
	}

	app := cli.NewApp()

	app.Name = "sam"
	app.Version = BuildVersion
	app.Usage = "AWS Serverless Application Model (SAM) CLI.\n\nThe AWS Serverless Application Model extends AWS CloudFormation to provide a simplified way of defining the Amazon API Gateway APIs, AWS Lambda functions, and Amazon DynamoDB tables needed by your serverless application. \n\nYou can find more in-depth guide about the SAM specification here:\nhttps://github.com/awslabs/serverless-application-model."
	app.EnableBashCompletion = true // \m/

	app.Commands = []cli.Command{
		cli.Command{
			Name:  "local",
			Usage: "Run your Serverless application locally for quick development & testing",
			Subcommands: []cli.Command{
				cli.Command{
					Name:   "start-api",
					Action: start,
					Usage:  "Allows you to run your Serverless application locally for quick development & testing. When run in a directory that contains your Serverless functions and your AWS SAM template, it will create a local HTTP server hosting all of your functions. When accessed (via browser, cli etc), it will launch a Docker container locally to invoke the function. It will read the CodeUri property of AWS::Serverless::Function resource to find the path in your file system containing the Lambda Function code. This could be the project's root directory for interpreted languages like Node & Python, or a build directory that stores your compiled artifacts or a JAR file. If you are using a interpreted language, local changes will be available immediately in Docker container on every invoke. For more compiled languages or projects requiring complex packing support, we recommended you run your own building solution and point SAM to the directory or file containing build artifacts.\n",
					Flags: []cli.Flag{
						cli.StringFlag{
							Name:   "template, t",
							Value:  "template.yaml",
							Usage:  "AWS SAM template file",
							EnvVar: "SAM_TEMPLATE_FILE",
						},
						cli.StringFlag{
							Name:  "log, l",
							Usage: "Optional logfile to send runtime logs to",
						},
						cli.StringFlag{
							Name:  "port, p",
							Value: "3000",
							Usage: "Local port number to listen on",
						},
						cli.StringFlag{
							Name:  "host",
							Value: "127.0.0.1",
							Usage: "Local hostname or IP address to bind to",
						},
						cli.StringFlag{
							Name:  "env-vars, n",
							Usage: "Optional. JSON file containing values for Lambda function's environment variables. ",
						},
					},
				},
				cli.Command{
					Name:   "invoke",
					Action: invoke,
					Usage: "Invokes a local Lambda function once and quits after invocation completes. \n\n" +
						"Useful for developing serverless functions that handle asynchronous events (such as S3/Kinesis etc), or if you want to compose a script of test cases. " +
						"Event body can be passed in either by stdin (default), or by using the --event parameter. Runtime output (logs etc) will be outputted to stderr, and the Lambda function result will be outputted to stdout.\n",
					ArgsUsage: "<function-identifier>",
					Flags: []cli.Flag{
						cli.StringFlag{
							Name:   "template, t",
							Value:  "template.yaml",
							Usage:  "AWS SAM template file",
							EnvVar: "SAM_TEMPLATE_FILE",
						},
						cli.StringFlag{
							Name:  "log-file, l",
							Usage: "Optional. Logfile to send runtime logs to",
						},
						cli.StringFlag{
							Name:  "env-vars, n",
							Usage: "Optional. JSON file containing values for Lambda function's environment variables. ",
						},
						cli.StringFlag{
							Name:  "event, e",
							Usage: "JSON file containing event data passed to the Lambda function during invoke",
						},
						cli.StringFlag{
							Name:   "debug-port, d",
							Usage:  "Optional. When specified, Lambda function container will start in debug mode and will expose this port on localhost. "+
								"At this moment, this only works for java8 and nodejs* runtimes.",
							EnvVar: "SAM_DEBUG_PORT",
						},
					},
				},
				cli.Command{
					Name:  "generate-event",
					Usage: "Generates Lambda events (e.g. for S3/Kinesis etc) that can be piped to 'sam local invoke'",
					Subcommands: []cli.Command{
						cli.Command{
							Name:  "s3",
							Usage: "Generates a sample Amazon S3 event",
							Flags: []cli.Flag{
								cli.StringFlag{
									Name:  "region, r",
									Usage: "The region the event should come from",
									Value: "us-east-1",
								},
								cli.StringFlag{
									Name:  "bucket, b",
									Usage: "The S3 bucket the event should reference",
									Value: "example-bucket",
								},
								cli.StringFlag{
									Name:  "key, k",
									Usage: "The S3 key the event should reference",
									Value: "test/key",
								},
							},
							Action: func(c *cli.Context) {
								generate("S3", c)
							},
						},
						cli.Command{
							Name:  "sns",
							Usage: "Generates a sample Amazon SNS event",
							Flags: []cli.Flag{
								cli.StringFlag{
									Name:  "message, m",
									Usage: "The SNS message body",
									Value: "example message",
								},
								cli.StringFlag{
									Name:  "topic, t",
									Usage: "The SNS topic",
									Value: "arn:aws:sns:us-east-1:111122223333:ExampleTopic",
								},
								cli.StringFlag{
									Name:  "subject, s",
									Usage: "The SNS subject",
									Value: "example subject",
								},
							},
							Action: func(c *cli.Context) {
								generate("SNS", c)
							},
						},
						cli.Command{
							Name:  "kinesis",
							Usage: "Generates a sample Amazon Kinesis event",
							Flags: []cli.Flag{
								cli.StringFlag{
									Name:  "region, r",
									Usage: "The region the event should come from",
									Value: "us-east-1",
								},
								cli.StringFlag{
									Name:  "partition, p",
									Usage: "The Kinesis partition key",
									Value: "partitionKey-03",
								},
								cli.StringFlag{
									Name:  "sequence, s",
									Usage: "The Kinesis sequence number",
									Value: "49545115243490985018280067714973144582180062593244200961",
								},
								cli.StringFlag{
									Name:  "data, d",
									Usage: "The Kinesis message payload. There is no need to base64 this - sam will do this for you",
									Value: "Hello, this is a test 123.",
								},
							},
							Action: func(c *cli.Context) {
								generate("Kinesis", c)
							},
						},
						cli.Command{
							Name:  "dynamodb",
							Usage: "Generates a sample Amazon DynamoDB event",
							Flags: []cli.Flag{
								cli.StringFlag{
									Name:  "region, r",
									Usage: "The region the event should come from",
									Value: "us-east-1",
								},
							},
							Action: func(c *cli.Context) {
								generate("DynamoDB", c)
							},
						},
						cli.Command{
							Name:  "api",
							Usage: "Generates a sample Amazon API Gateway event",
							Flags: []cli.Flag{
								cli.StringFlag{
									Name:  "method, m",
									Usage: "HTTP method",
									Value: "POST",
								},
								cli.StringFlag{
									Name:  "body, b",
									Usage: "HTTP body",
									Value: `{ "test\": \"body\"}`,
								},
								cli.StringFlag{
									Name:  "resource, r",
									Usage: "API Gateway resource name",
									Value: "/{proxy+}",
								},
								cli.StringFlag{
									Name:  "path, p",
									Usage: "HTTP path",
									Value: "/examplepath",
								},
							},
							Action: func(c *cli.Context) {
								generate("Api", c)
							},
						},
						cli.Command{
							Name:  "schedule",
							Usage: "Generates a sample scheduled event",
							Flags: []cli.Flag{
								cli.StringFlag{
									Name:  "region, r",
									Usage: "The region the event should come from",
									Value: "us-east-1",
								},
							},
							Action: func(c *cli.Context) {
								generate("Schedule", c)
							},
						},
					},
				},
			},
		},

		cli.Command{
			Name:   "validate",
			Usage:  "Validates an AWS SAM template. If valid, will print a summary of the resources found within the SAM template. If the template is invalid, returns a non-zero exit code.",
			Action: validate,
			Flags: []cli.Flag{
				cli.StringFlag{
					Name:   "template, t",
					Value:  "template.yaml",
					Usage:  "AWS SAM template file",
					EnvVar: "SAM_TEMPLATE_FILE",
				},
			},
		},

		cli.Command{
			// This is just here for consistent usage and --help
			Name:   "package",
			Usage:  "Package an AWS SAM application. This is an alias for 'aws cloudformation package'.",
			Action: pkg,
		},

		cli.Command{
			// This is just here for consistent usage and --help
			Name:   "deploy",
			Usage:  "Deploy an AWS SAM application. This is an alias for 'aws cloudformation deploy'.",
			Action: deploy,
		},
	}

	// For 'package' and 'deploy' CLI options, we want to intercept
	// and just pass all arguments through to the AWS CLI commands.
	if len(os.Args) > 1 && os.Args[1] == "package" {
		pkg()
		return
	}

	// For 'package' and 'deploy' CLI options, we want to intercept
	// and just pass all arguments through to the AWS CLI commands.
	if len(os.Args) > 1 && os.Args[1] == "deploy" {
		deploy()
		return
	}

	app.Run(os.Args)

}

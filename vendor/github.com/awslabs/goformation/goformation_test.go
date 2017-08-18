package goformation_test

import (
	"github.com/awslabs/goformation"
	"github.com/awslabs/goformation/cloudformation"

	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"
	. "github.com/onsi/gomega/gstruct"
)

var _ = Describe("Goformation", func() {

	Context("with an AWS CloudFormation template that contains multiple resources", func() {

		Context("described as Go structs", func() {

			template := cloudformation.NewTemplate()

			template.Resources["MySNSTopic"] = cloudformation.AWSSNSTopic{
				DisplayName: "test-sns-topic-display-name",
				TopicName:   "test-sns-topic-name",
				Subscription: []cloudformation.AWSSNSTopic_Subscription{
					cloudformation.AWSSNSTopic_Subscription{
						Endpoint: "test-sns-topic-subscription-endpoint",
						Protocol: "test-sns-topic-subscription-protocol",
					},
				},
			}

			template.Resources["MyRoute53HostedZone"] = cloudformation.AWSRoute53HostedZone{
				Name: "example.com",
			}

			topics := template.GetAllAWSSNSTopicResources()
			It("should have one AWS::SNS::Topic resource", func() {
				Expect(topics).To(HaveLen(1))
				Expect(topics).To(HaveKey("MySNSTopic"))
			})

			topic, err := template.GetAWSSNSTopicWithName("MySNSTopic")
			It("should be able to find the AWS::SNS::Topic by name", func() {
				Expect(topic).ToNot(BeNil())
				Expect(err).To(BeNil())
			})

			It("should have the correct AWS::SNS::Topic values", func() {
				Expect(topic.DisplayName).To(Equal("test-sns-topic-display-name"))
				Expect(topic.TopicName).To(Equal("test-sns-topic-name"))
				Expect(topic.Subscription).To(HaveLen(1))
				Expect(topic.Subscription[0].Endpoint).To(Equal("test-sns-topic-subscription-endpoint"))
				Expect(topic.Subscription[0].Protocol).To(Equal("test-sns-topic-subscription-protocol"))
			})

			zones := template.GetAllAWSRoute53HostedZoneResources()
			It("should have one AWS::Route53::HostedZone resource", func() {
				Expect(zones).To(HaveLen(1))
				Expect(zones).To(HaveKey("MyRoute53HostedZone"))
			})

			zone, err := template.GetAWSRoute53HostedZoneWithName("MyRoute53HostedZone")
			It("should be able to find the AWS::Route53::HostedZone by name", func() {
				Expect(zone).ToNot(BeNil())
				Expect(err).To(BeNil())
			})

			It("should have the correct AWS::Route53::HostedZone values", func() {
				Expect(zone.Name).To(Equal("example.com"))
			})

		})

		Context("described as JSON", func() {

			template := []byte(`{"AWSTemplateFormatVersion":"2010-09-09","Resources":{"MyRoute53HostedZone":{"Type":"AWS::Route53::HostedZone","Properties":{"Name":"example.com"}},"MySNSTopic":{"Type":"AWS::SNS::Topic","Properties":{"DisplayName":"test-sns-topic-display-name","Subscription":[{"Endpoint":"test-sns-topic-subscription-endpoint","Protocol":"test-sns-topic-subscription-protocol"}],"TopicName":"test-sns-topic-name"}}}}`)

			expected := cloudformation.NewTemplate()

			expected.Resources["MySNSTopic"] = cloudformation.AWSSNSTopic{
				DisplayName: "test-sns-topic-display-name",
				TopicName:   "test-sns-topic-name",
				Subscription: []cloudformation.AWSSNSTopic_Subscription{
					cloudformation.AWSSNSTopic_Subscription{
						Endpoint: "test-sns-topic-subscription-endpoint",
						Protocol: "test-sns-topic-subscription-protocol",
					},
				},
			}

			expected.Resources["MyRoute53HostedZone"] = cloudformation.AWSRoute53HostedZone{
				Name: "example.com",
			}

			result, err := goformation.Parse(template)
			It("should marshal to Go structs successfully", func() {
				Expect(err).To(BeNil())
			})

			topics := result.GetAllAWSSNSTopicResources()
			It("should have one AWS::SNS::Topic resource", func() {
				Expect(topics).To(HaveLen(1))
				Expect(topics).To(HaveKey("MySNSTopic"))
			})

			topic, err := result.GetAWSSNSTopicWithName("MySNSTopic")
			It("should be able to find the AWS::SNS::Topic by name", func() {
				Expect(topic).ToNot(BeNil())
				Expect(err).To(BeNil())
			})

			It("should have the correct AWS::SNS::Topic values", func() {
				Expect(topic.DisplayName).To(Equal("test-sns-topic-display-name"))
				Expect(topic.TopicName).To(Equal("test-sns-topic-name"))
				Expect(topic.Subscription).To(HaveLen(1))
				Expect(topic.Subscription[0].Endpoint).To(Equal("test-sns-topic-subscription-endpoint"))
				Expect(topic.Subscription[0].Protocol).To(Equal("test-sns-topic-subscription-protocol"))
			})

			zones := result.GetAllAWSRoute53HostedZoneResources()
			It("should have one AWS::Route53::HostedZone resource", func() {
				Expect(zones).To(HaveLen(1))
				Expect(zones).To(HaveKey("MyRoute53HostedZone"))
			})

			zone, err := result.GetAWSRoute53HostedZoneWithName("MyRoute53HostedZone")
			It("should be able to find the AWS::Route53::HostedZone by name", func() {
				Expect(zone).ToNot(BeNil())
				Expect(err).To(BeNil())
			})

			It("should have the correct AWS::Route53::HostedZone values", func() {
				Expect(zone.Name).To(Equal("example.com"))
			})

		})

	})

	Context("with the official AWS SAM example templates", func() {

		inputs := []string{
			"test/yaml/sam-official-samples/alexa_skill/template.yaml",
			"test/yaml/sam-official-samples/api_backend/template.yaml",
			"test/yaml/sam-official-samples/api_swagger_cors/template.yaml",
			"test/yaml/sam-official-samples/encryption_proxy/template.yaml",
			"test/yaml/sam-official-samples/hello_world/template.yaml",
			"test/yaml/sam-official-samples/inline_swagger/template.yaml",
			"test/yaml/sam-official-samples/iot_backend/template.yaml",
			"test/yaml/sam-official-samples/s3_processor/template.yaml",
			"test/yaml/sam-official-samples/schedule/template.yaml",
			"test/yaml/sam-official-samples/stream_processor/template.yaml",
		}

		for _, filename := range inputs {
			Context("including "+filename, func() {
				template, err := goformation.Open(filename)
				It("should successfully parse the SAM template", func() {
					Expect(err).To(BeNil())
					Expect(template).ShouldNot(BeNil())
				})
			})
		}

	})

	Context("with the default AWS CodeStar templates", func() {

		inputs := []string{
			"test/yaml/codestar/nodejs.yml",
			"test/yaml/codestar/python.yml",
			"test/yaml/codestar/java.yml",
		}

		for _, filename := range inputs {
			Context("including "+filename, func() {
				template, err := goformation.Open(filename)
				It("should successfully validate the SAM template", func() {
					Expect(err).To(BeNil())
					Expect(template).ShouldNot(BeNil())
				})
			})
		}
	})

	Context("with a Serverless template containing different CodeUri formats", func() {

		template, err := goformation.Open("test/yaml/aws-serverless-function-string-or-s3-location.yaml")
		It("should successfully parse the template", func() {
			Expect(err).To(BeNil())
			Expect(template).ShouldNot(BeNil())
		})

		functions := template.GetAllAWSServerlessFunctionResources()

		It("should have exactly three functions", func() {
			Expect(functions).To(HaveLen(3))
			Expect(functions).To(HaveKey("CodeUriWithS3LocationSpecifiedAsString"))
			Expect(functions).To(HaveKey("CodeUriWithS3LocationSpecifiedAsObject"))
			Expect(functions).To(HaveKey("CodeUriWithString"))
		})

		f1 := functions["CodeUriWithS3LocationSpecifiedAsString"]
		It("should parse a CodeUri property with an S3 location specified as a string", func() {
			Expect(f1.CodeUri.String).To(PointTo(Equal("s3://testbucket/testkey.zip")))
		})

		f2 := functions["CodeUriWithS3LocationSpecifiedAsObject"]
		It("should parse a CodeUri property with an S3 location specified as an object", func() {
			Expect(f2.CodeUri.S3Location.Key).To(Equal("testkey.zip"))
			Expect(f2.CodeUri.S3Location.Version).To(Equal(5))
		})

		f3 := functions["CodeUriWithString"]
		It("should parse a CodeUri property with a string", func() {
			Expect(f3.CodeUri.String).To(PointTo(Equal("./testfolder")))
		})

	})

	Context("with a template defined as Go code", func() {

		template := &cloudformation.Template{
			Resources: map[string]interface{}{
				"MyLambdaFunction": cloudformation.AWSLambdaFunction{
					Handler: "nodejs6.10",
				},
			},
		}

		functions := template.GetAllAWSLambdaFunctionResources()
		It("should be able to retrieve all Lambda functions with GetAllAWSLambdaFunction(template)", func() {
			Expect(functions).To(HaveLen(1))
		})

		function, err := template.GetAWSLambdaFunctionWithName("MyLambdaFunction")
		It("should be able to retrieve a specific Lambda function with GetAWSLambdaFunctionWithName(template, name)", func() {
			Expect(err).To(BeNil())
			Expect(function).To(BeAssignableToTypeOf(cloudformation.AWSLambdaFunction{}))
		})

		It("should have the correct Handler property", func() {
			Expect(function.Handler).To(Equal("nodejs6.10"))
		})

	})

	Context("with a template that defines an AWS::Serverless::Function", func() {

		Context("that has a CodeUri property set as an S3 Location", func() {

			template := &cloudformation.Template{
				Resources: map[string]interface{}{
					"MySAMFunction": cloudformation.AWSServerlessFunction{
						Handler: "nodejs6.10",
						CodeUri: &cloudformation.AWSServerlessFunction_StringOrS3Location{
							S3Location: &cloudformation.AWSServerlessFunction_S3Location{
								Bucket:  "test-bucket",
								Key:     "test-key",
								Version: 100,
							},
						},
					},
				},
			}

			function, err := template.GetAWSServerlessFunctionWithName("MySAMFunction")
			It("should have an AWS::Serverless::Function called MySAMFunction", func() {
				Expect(function).ToNot(BeNil())
				Expect(err).To(BeNil())
			})

			It("should have the correct S3 bucket/key/version", func() {
				Expect(function.CodeUri.S3Location.Bucket).To(Equal("test-bucket"))
				Expect(function.CodeUri.S3Location.Key).To(Equal("test-key"))
				Expect(function.CodeUri.S3Location.Version).To(Equal(100))
			})

		})

		Context("that has a CodeUri property set as a string", func() {

			codeuri := "./some-folder"
			template := &cloudformation.Template{
				Resources: map[string]interface{}{
					"MySAMFunction": cloudformation.AWSServerlessFunction{
						Handler: "nodejs6.10",
						CodeUri: &cloudformation.AWSServerlessFunction_StringOrS3Location{
							String: &codeuri,
						},
					},
				},
			}

			function, err := template.GetAWSServerlessFunctionWithName("MySAMFunction")
			It("should have an AWS::Serverless::Function called MySAMFunction", func() {
				Expect(function).ToNot(BeNil())
				Expect(err).To(BeNil())
			})

			It("should have the correct CodeUri", func() {
				Expect(function.CodeUri.String).To(PointTo(Equal("./some-folder")))
			})

		})

	})

})

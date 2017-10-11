package main

import (
	"github.com/awslabs/goformation"
	"github.com/awslabs/goformation/cloudformation"
	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"
)

var _ = Describe("Convert Cloudformation Lambda functions to Serverless", func() {

	Context("with normal input", func() {

		It("converts an empty function", func() {
			f := cloudformation.AWSLambdaFunction{}
			expected := cloudformation.AWSServerlessFunction{}
			Expect(lambdaToServerless(f)).To(Equal(expected))
		})

		It("converts a function", func() {
			f := cloudformation.AWSLambdaFunction{
				FunctionName: "foo",
				Description:  "desc",
				Handler:      "index.js",
				Timeout:      30,
				Runtime:      "nodejs6.10",
				MemorySize:   300,
				Role:         "arn:aws:iam::123456789012:role/S3Access",
				KmsKeyArn:    "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012",
				DeadLetterConfig: &cloudformation.AWSLambdaFunction_DeadLetterConfig{
					TargetArn: "arn:aws:sns:us-east-1:123456789012:my_corporate_topic:02034b43-fefa-4e07-a5eb-3be56f8c54ce",
				},
				Tags: []cloudformation.Tag{{Key: "key", Value: "value"}},
				TracingConfig: &cloudformation.AWSLambdaFunction_TracingConfig{
					Mode: "PassThrough",
				},
				Environment: &cloudformation.AWSLambdaFunction_Environment{
					Variables: map[string]string{"k1": "v1"},
				},
				VpcConfig: &cloudformation.AWSLambdaFunction_VpcConfig{
					SecurityGroupIds: []string{"sg-edcd9784"},
					SubnetIds:        []string{"subnet"},
				},
			}
			expected := cloudformation.AWSServerlessFunction{
				CodeUri:      nil,
				Events:       nil,
				Policies:     nil,
				FunctionName: "foo",
				Description:  "desc",
				Handler:      "index.js",
				Timeout:      30,
				Runtime:      "nodejs6.10",
				MemorySize:   300,
				Role:         "arn:aws:iam::123456789012:role/S3Access",
				KmsKeyArn:    "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012",
				DeadLetterQueue: &cloudformation.AWSServerlessFunction_DeadLetterQueue{
					TargetArn: "arn:aws:sns:us-east-1:123456789012:my_corporate_topic:02034b43-fefa-4e07-a5eb-3be56f8c54ce",
					Type:      "SNS",
				},
				Tags:    map[string]string{"key": "value"},
				Tracing: "PassThrough",
				Environment: &cloudformation.AWSServerlessFunction_FunctionEnvironment{
					Variables: map[string]string{"k1": "v1"},
				},
				VpcConfig: &cloudformation.AWSServerlessFunction_VpcConfig{
					SecurityGroupIds: []string{"sg-edcd9784"},
					SubnetIds:        []string{"subnet"},
				},
			}

			Expect(lambdaToServerless(f)).To(Equal(expected))
		})

	})

	Context("with existing template", func() {

		functions := map[string]cloudformation.AWSServerlessFunction{
			"ExistingFunction": cloudformation.AWSServerlessFunction{},
		}
		const input = `{
            "Resources": {
              "ExistingFunction": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                  "FunctionName": "ExistingFunction",
                  "Handler": "com.foo.bar.Dispatcher::handleRequest"
                }
              },
              "Func1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                  "FunctionName": "Func1",
                  "Handler": "com.foo.bar.Dispatcher::handleRequest"
                }
              }
            }
          }`

		template, err := goformation.ParseJSON([]byte(input))

		It("parses correctly", func() {
			Expect(err).To(BeNil())
			Expect(template).To(Not(BeNil()))
			lambdas := template.GetAllAWSLambdaFunctionResources()
			Expect(lambdas).To(HaveLen(2))
			Expect(lambdas).To(HaveKey("Func1"))
			Expect(lambdas).To(HaveKey("ExistingFunction"))
		})

		if template != nil {
			addCloudformationLambdaFunctions(template, functions)
		}

		It("adds lambda functions that don't clash", func() {
			Expect(functions).To(HaveLen(2))
			Expect(functions).To(HaveKey("Func1"))
			Expect(functions).To(HaveKey("ExistingFunction"))
		})

		It("ignores lambda functions which already exist", func() {
			Expect(functions).To(HaveKeyWithValue("ExistingFunction", Equal(cloudformation.AWSServerlessFunction{})))
		})

	})
})

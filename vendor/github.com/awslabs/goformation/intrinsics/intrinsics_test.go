package intrinsics_test

import (
	"encoding/base64"
	"encoding/json"

	. "github.com/awslabs/goformation/intrinsics"

	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"
)

var _ = Describe("AWS CloudFormation intrinsic function processing", func() {

	Context("with a template that contains invalid JSON", func() {
		input := `{`
		processed, err := ProcessJSON([]byte(input), nil)
		It("should fail to process the template", func() {
			Expect(processed).To(BeNil())
			Expect(err).ToNot(BeNil())
		})
	})

	Context("with a template that contains a 'Ref' intrinsic function", func() {

		input := `{"Parameters":{"FunctionTimeout":{"Type":"Number","Default":120}},"Resources":{"MyServerlessFunction":{"Type":"AWS::Serverless::Function","Properties":{"Runtime":"nodejs6.10","Timeout":{"Ref":"FunctionTimeout"}}}}}`
		processed, err := ProcessJSON([]byte(input), nil)
		It("should successfully process the template", func() {
			Expect(processed).ShouldNot(BeNil())
			Expect(err).Should(BeNil())
		})

		var result interface{}
		err = json.Unmarshal(processed, &result)
		It("should be valid JSON, and marshal to a Go type", func() {
			Expect(processed).ToNot(BeNil())
			Expect(err).To(BeNil())
		})

		template := result.(map[string]interface{})
		resources := template["Resources"].(map[string]interface{})
		resource := resources["MyServerlessFunction"].(map[string]interface{})
		properties := resource["Properties"].(map[string]interface{})

		It("should have the correct values", func() {
			Expect(properties["Timeout"]).To(Equal(float64(120)))
			Expect(properties["Runtime"]).To(Equal("nodejs6.10"))
		})

	})

	Context("with a template that contains a 'Ref' intrinsic function with a 'Fn::Join' inside it", func() {

		input := `{"Parameters":{"FunctionTimeout":{"Type":"Number","Default":120}},"Resources":{"MyServerlessFunction":{"Type":"AWS::Serverless::Function","Properties":{"Runtime":"nodejs6.10","Timeout":{"Ref":{"Fn::Join":["Function","Timeout"]}}}}}}`
		processed, err := ProcessJSON([]byte(input), nil)
		It("should successfully process the template", func() {
			Expect(processed).ShouldNot(BeNil())
			Expect(err).Should(BeNil())
		})

		var result interface{}
		err = json.Unmarshal(processed, &result)
		It("should be valid JSON, and marshal to a Go type", func() {
			Expect(processed).ToNot(BeNil())
			Expect(err).To(BeNil())
		})

		template := result.(map[string]interface{})
		resources := template["Resources"].(map[string]interface{})
		resource := resources["MyServerlessFunction"].(map[string]interface{})
		properties := resource["Properties"].(map[string]interface{})

		It("should have the correct values", func() {
			Expect(properties["Timeout"]).To(Equal(float64(120)))
			Expect(properties["Runtime"]).To(Equal("nodejs6.10"))
		})

	})

	Context("with a YAML template that contains intrinsic functions in tag form", func() {

		t := "AWSTemplateFormatVersion: '2010-09-09'\n"
		t += "Transform: AWS::Serverless-2016-10-31\n"
		t += "Description: SAM template for testing intrinsic functions with YAML tags\n"
		t += "Parameters:\n"
		t += "  TestParameter:\n"
		t += "    Type: String\n"
		t += "    Default: test-parameter-value\n"
		t += "Resources:\n"
		t += "  CodeUriWithS3LocationSpecifiedAsString:\n"
		t += "    Type: AWS::Serverless::Function\n"
		t += "    Properties:\n"
		t += "      Runtime: !Sub test-${ThisWontResolve}\n"
		t += "      Timeout: !Ref ThisWontResolve\n"
		t += "      FunctionName: !Ref TestParameter\n"
		t += "      Handler: !Sub method.${TestParameter}.${ThisWontResolve}\n"
		t += "      CodeUri:\n"
		t += "        Fn::Sub:\n"
		t += "          - s3://${Bucket}/${Key}\n"
		t += "          - { \"Bucket\": \"test-bucket\", \"Key\": \"test-key\" }\n"

		processed, err := ProcessYAML([]byte(t), nil)
		It("should successfully process the template", func() {
			Expect(processed).ShouldNot(BeNil())
			Expect(err).Should(BeNil())
		})

		var result interface{}
		err = json.Unmarshal(processed, &result)
		It("should be valid JSON, and marshal to a Go type", func() {
			Expect(processed).ToNot(BeNil())
			Expect(err).To(BeNil())
		})

		template := result.(map[string]interface{})
		resources := template["Resources"].(map[string]interface{})
		resource := resources["CodeUriWithS3LocationSpecifiedAsString"].(map[string]interface{})
		properties := resource["Properties"].(map[string]interface{})

		It("should convert an unresolvable !Ref to nil", func() {
			Expect(properties["Timeout"]).To(BeNil())
		})

		It("should handle unresolvable references in !Sub", func() {
			Expect(properties["Runtime"]).To(Equal("test-"))
		})

		It("should handle Fn::Sub with an array of replacements", func() {
			Expect(properties["CodeUri"]).To(Equal("s3://test-bucket/test-key"))
		})

		It("should resolved a !Ref that points to a valid parameter", func() {
			Expect(properties["FunctionName"]).To(Equal("test-parameter-value"))
		})

		It("should resolve a reference within a !Sub", func() {
			Expect(properties["Handler"]).To(Equal("method.test-parameter-value."))
		})

	})

	Context("with a template that contains primitives, intrinsics, and nested intrinsics", func() {

		const template = `{
			"Mappings" : {
				"RegionMap" : {
					"us-east-1" : { "32" : "ami-6411e20d", "64" : "ami-7a11e213" },
					"us-west-1" : { "32" : "ami-c9c7978c", "64" : "ami-cfc7978a" },
					"eu-west-1" : { "32" : "ami-37c2f643", "64" : "ami-31c2f645" },
					"ap-southeast-1" : { "32" : "ami-66f28c34", "64" : "ami-60f28c32" },
					"ap-northeast-1" : { "32" : "ami-9c03a89d", "64" : "ami-a003a8a1" }
				}
			},
			"Resources": {
				"ExampleResource": {
					"Type": "AWS::Example::Resource",
					"Properties": {
						"StringProperty": "Simple string example",						
						"BooleanProperty": true,
						"NumberProperty": 123.45,
						"JoinIntrinsicProperty": { "Fn::Join": [ "some", "name" ] },				
						"JoinNestedIntrinsicProperty": { "Fn::Join": [ "some", { "Fn::Join": [ "joined", "value" ] } ] },
						"SubIntrinsicProperty": { "Fn::Sub": [ "some ${replaced}", { "replaced": "value" } ] },
						"SplitIntrinsicProperty": { "Fn::Split" : [ ",", "some,string,to,be,split" ] },
						"SelectIntrinsicProperty": { "Fn::Select" : [ 1, [ 0, 1, 2, 3 ] ] },
						"FindInMapIntrinsicProperty": { "Fn::FindInMap" : [ "RegionMap", "eu-west-1", "64"] },
						"Base64IntrinsicProperty": { "Fn::Base64" : "some-string-to-base64" },
						"RefAWSAccountId": { "Ref": "AWS::AccountId" },
						"RefAWSNotificationARNs": { "Ref": "AWS::NotificationARNs" },
						"RefNoValue": { "Ref": "AWS::NoValue" },
						"RefAWSRegion": { "Ref": "AWS::Region" },
						"RefAWSStackId": { "Ref": "AWS::StackId" },
						"RefAWSStackName": { "Ref": "AWS::StackName" }	
					}
				}
			}
		}`

		Context("with no processor options", func() {

			processed, err := ProcessJSON([]byte(template), nil)
			It("should successfully process the template", func() {
				Expect(processed).ShouldNot(BeNil())
				Expect(err).Should(BeNil())
			})

			var result interface{}
			err = json.Unmarshal(processed, &result)
			It("should be valid JSON, and marshal to a Go type", func() {
				Expect(processed).ToNot(BeNil())
				Expect(err).To(BeNil())
			})

			template := result.(map[string]interface{})
			resources := template["Resources"].(map[string]interface{})
			resource := resources["ExampleResource"].(map[string]interface{})
			properties := resource["Properties"].(map[string]interface{})

			It("should have the correct value for a primitive string property", func() {
				Expect(properties["StringProperty"]).To(Equal("Simple string example"))
			})

			It("should have the correct value for a primitive boolean property", func() {
				Expect(properties["BooleanProperty"]).To(Equal(true))
			})

			It("should have the correct value for a primitive number property", func() {
				Expect(properties["NumberProperty"]).To(Equal(123.45))
			})

			It("should have the correct value for a Fn::Join intrinsic property", func() {
				Expect(properties["JoinIntrinsicProperty"]).To(Equal("somename"))
			})

			It("should have the correct value for a nested Fn::Join intrinsic property", func() {
				Expect(properties["JoinNestedIntrinsicProperty"]).To(Equal("somejoinedvalue"))
			})

			It("should have the correct value for a Fn::Sub intrinsic property", func() {
				Expect(properties["SubIntrinsicProperty"]).To(Equal("some value"))
			})

			It("should have the correct value for a Fn::Split intrinsic property", func() {
				Expect(properties["SplitIntrinsicProperty"]).To(HaveLen(5))
				results := []string{}
				for _, element := range properties["SplitIntrinsicProperty"].([]interface{}) {
					if str, ok := element.(string); ok {
						results = append(results, str)
					}
				}
				Expect(results).To(Equal([]string{"some", "string", "to", "be", "split"}))
			})

			It("should have the correct value for a Fn::Select intrinsic property", func() {
				Expect(properties["SelectIntrinsicProperty"]).To(Equal(float64(1)))
			})

			It("should have the correct value for a Fn::FindInMap intrinsic property", func() {
				Expect(properties["FindInMapIntrinsicProperty"]).To(Equal("ami-31c2f645"))
			})

			It("should have the correct value for a Fn::Base64 intrinsic property", func() {
				encoded, ok := properties["Base64IntrinsicProperty"].(string)
				Expect(ok).ToNot(BeNil())
				decoded, err := base64.StdEncoding.DecodeString(encoded)
				Expect(string(decoded)).To(Equal("some-string-to-base64"))
				Expect(err).To(BeNil())
			})

			It("should have the correct value for a AWS::AccountId pseudo parameter intrinsic property", func() {
				Expect(properties["RefAWSAccountId"]).To(Equal("123456789012"))
			})

			It("should have the correct value for a AWS::NotificationARNs pseudo parameter intrinsic property", func() {
				Expect(properties["RefAWSNotificationARNs"]).To(ContainElement("arn:aws:sns:us-east-1:123456789012:MyTopic"))
			})

			It("should have the correct value for a AWS::NoValue pseudo parameter intrinsic property", func() {
				Expect(properties["RefAWSNoValue"]).To(BeNil())
			})

			It("should have the correct value for a AWS::Region pseudo parameter intrinsic property", func() {
				Expect(properties["RefAWSRegion"]).To(Equal("us-east-1"))
			})

			It("should have the correct value for a AWS::StackId pseudo parameter intrinsic property", func() {
				Expect(properties["RefAWSStackId"]).To(Equal("arn:aws:cloudformation:us-east-1:123456789012:stack/MyStack/1c2fa620-982a-11e3-aff7-50e2416294e0"))
			})

			It("should have the correct value for a AWS::StackName pseudo parameter intrinsic property", func() {
				Expect(properties["RefAWSStackName"]).To(Equal("goformation-stack"))
			})

		})

		Context("with a processor options override for the Fn::Join function", func() {

			opts := &ProcessorOptions{
				IntrinsicHandlerOverrides: map[string]IntrinsicHandler{
					"Fn::Join": func(name string, input interface{}, template interface{}) interface{} {
						return "overridden"
					},
				},
			}

			processed, err := ProcessJSON([]byte(template), opts)
			It("should successfully process the template", func() {
				Expect(processed).ShouldNot(BeNil())
				Expect(err).Should(BeNil())
			})

			result := map[string]interface{}{}
			err = json.Unmarshal(processed, &result)

			It("should be valid JSON, and marshal to a Go type", func() {
				Expect(processed).ToNot(BeNil())
				Expect(err).To(BeNil())
			})

			resources := result["Resources"].(map[string]interface{})
			resource := resources["ExampleResource"].(map[string]interface{})
			properties := resource["Properties"].(map[string]interface{})

			It("should have the correct value for a primitive string property", func() {
				Expect(properties["StringProperty"]).To(Equal("Simple string example"))
			})

			It("should have the correct value for a primitive boolean property", func() {
				Expect(properties["BooleanProperty"]).To(Equal(true))
			})

			It("should have the correct value for a primitive number property", func() {
				Expect(properties["NumberProperty"]).To(Equal(123.45))
			})

			It("should have the correct value for an intrinsic property", func() {
				Expect(properties["JoinIntrinsicProperty"]).To(Equal("overridden"))
			})

			It("should have the correct value for a nested intrinsic property", func() {
				Expect(properties["JoinNestedIntrinsicProperty"]).To(Equal("overridden"))
			})

			It("should have the correct value for an intrinsic property that's not supposed to be overridden", func() {
				Expect(properties["SubIntrinsicProperty"]).To(Equal("some value"))
			})

		})

	})
})

package goformation_test

// import (
// 	"log"

// 	. "github.com/onsi/ginkgo"
// 	. "github.com/onsi/gomega"
// )

// var _ = Describe("The Base Resource", func() {

// 	Context("Upon creation", func() {
// 		const resourceType = "AWS::Serverless::Function"
// 		var properties map[string]Property
// 		var returnValues map[string]func(interface{}) interface{}

// 		BeforeEach(func() {
// 			properties = make(map[string]Property)
// 			returnValues = make(map[string]func(interface{}) interface{})
// 		})

// 		It("Should validate that the given type is valid", func() {
// 			_, error := NewResource("wrong", properties, returnValues)
// 			Expect(error).ToNot(BeNil())
// 			Expect(error).To(Equal(ErrInvalidResourceType))
// 		})

// 		It("Should validate that at least there is one property present", func() {
// 			_, error := NewResource(resourceType, properties, returnValues)
// 			Expect(error).ToNot(BeNil())
// 			Expect(error).To(Equal(ErrResourceInvalidPropertyNumber))
// 		})

// 		It("Should create a valid Resource object", func() {
// 			properties["test"] = Property{}
// 			resource, error := NewResource(resourceType, properties, returnValues)
// 			Expect(error).To(BeNil())
// 			Expect(resource).ToNot(BeNil())
// 			Expect(resource.Properties).To(Equal(properties))
// 			Expect(resource.ReturnValues).To(Equal(returnValues))
// 		})

// 	})

// 	Describe("Upon definition", func() {

// 		It("Should validate that a type is given", func() {
// 			config := map[string]interface{}{}

// 			_, error := DefineResource(config)
// 			Expect(error).ToNot(BeNil())
// 			Expect(error).To(Equal(ErrInvalidResourceDefinition))
// 		})

// 		It("Should validate that the given type is valid", func() {
// 			config := map[string]interface{}{
// 				"Type": "wrong",
// 			}

// 			_, error := DefineResource(config)
// 			Expect(error).ToNot(BeNil())
// 			Expect(error).To(Equal(ErrInvalidResourceDefinition))
// 		})

// 		It("Should validate that a `properties` object is present", func() {
// 			config := map[string]interface{}{
// 				"Type": "AWS::Serverless::Function",
// 			}

// 			_, error := DefineResource(config)
// 			Expect(error).ToNot(BeNil())
// 			Expect(error).To(Equal(ErrInvalidResourceDefinition))
// 		})

// 		It("Should validate that a `returnValues` object is present", func() {
// 			config := map[string]interface{}{
// 				"Type":       "AWS::Serverless::Function",
// 				"Properties": map[string]map[string]interface{}{},
// 			}

// 			_, error := DefineResource(config)
// 			Expect(error).ToNot(BeNil())
// 			Expect(error).To(Equal(ErrInvalidResourceDefinition))
// 		})

// 		It("Should return a populated result if no errors", func() {
// 			config := map[string]interface{}{
// 				"Type": "AWS::Serverless::Function",
// 				"Properties": map[string]map[string]interface{}{
// 					"Test": map[string]interface{}{
// 						"Types":    "string",
// 						"Required": true,
// 						"Default":  "abc",
// 					},
// 				},
// 				"ReturnValues":       map[string]func(interface{}) interface{}{},
// 				"IntrinsicFunctions": map[string]func(interface{}) interface{}{},
// 			}

// 			resource, error := DefineResource(config)
// 			Expect(error).To(BeNil())
// 			Expect(resource).ToNot(BeNil())
// 			Expect(resource.Type).To(Equal(config["Type"]))
// 		})

// 	})

// 	Describe("Upon scaffolding", func() {
// 		var sampleResourceDef Resource

// 		Describe("Primitive values", func() {
// 			BeforeEach(func() {
// 				sampleResourceDefConfig := map[string]interface{}{
// 					"Type": "AWS::Serverless::Function",
// 					"Properties": map[string]map[string]interface{}{
// 						"RequiredValue": map[string]interface{}{
// 							"Types":    "string",
// 							"Required": true,
// 						},
// 						"OptionalValue": map[string]interface{}{
// 							"Types":    "int",
// 							"Required": false,
// 						},
// 						"StaticDefaultValue": map[string]interface{}{
// 							"Types":    "string",
// 							"Required": true,
// 							"Default":  "My default value",
// 						},
// 						"DynamicDefaultValue": map[string]interface{}{
// 							"Types":    "string",
// 							"Required": true,
// 							"Default": func(_ map[string]interface{}) interface{} {
// 								return "My dynamic value"
// 							},
// 						},
// 					},
// 					"ReturnValues": map[string]func(interface{}) interface{}{
// 						"Ref": func(function interface{}) interface{} {
// 							return "Whatever"
// 						},
// 						"Arn": func(function interface{}) interface{} {
// 							return "ARN"
// 						},
// 						"TheRequiredValue": func(function interface{}) interface{} {
// 							fn := function.(map[string]interface{})
// 							fnProperties := fn["Properties"].(map[string]interface{})

// 							return fnProperties["RequiredValue"]
// 						},
// 					},
// 				}

// 				var error error
// 				sampleResourceDef, error = DefineResource(sampleResourceDefConfig)
// 				if error != nil {
// 					log.Print(error.Error())
// 					log.Panic("Error defining test resource for scaffolding")
// 				}
// 			})

// 			It("Should validate that a `Type` property is given", func() {
// 				sampleResource := map[string]interface{}{}

// 				_, error := sampleResourceDef.Scaffold(sampleResource)
// 				Expect(error).ToNot(BeNil())
// 				Expect(error).To(Equal(ErrScaffoldUndefinedType))
// 			})

// 			It("Should validate that the resource type corresponds with the definition", func() {
// 				sampleResource := map[string]interface{}{
// 					"Type":       "AWS::TestResource::Scaffolding",
// 					"Properties": map[string]interface{}{},
// 				}

// 				_, error := sampleResourceDef.Scaffold(sampleResource)
// 				Expect(error).ToNot(BeNil())
// 				Expect(error).To(Equal(ErrScaffoldInvalidResourceType))
// 			})

// 			It("Should validate that a `Properties` property is given", func() {
// 				sampleResource := map[string]interface{}{
// 					"Type": "AWS::Serverless::Function",
// 				}

// 				_, error := sampleResourceDef.Scaffold(sampleResource)
// 				Expect(error).ToNot(BeNil())
// 				Expect(error).To(Equal(ErrScaffoldUndefinedProperties))
// 			})

// 			It("Should verify that required values are set", func() {
// 				sampleResource := map[string]interface{}{
// 					"Type":       "AWS::Serverless::Function",
// 					"Properties": map[string]interface{}{},
// 				}

// 				_, error := sampleResourceDef.Scaffold(sampleResource)
// 				Expect(error).ToNot(BeNil())
// 				Expect(error).To(Equal(ErrScaffoldRequiredValueNotSet))
// 			})

// 			It("Should return the resource parsed if everything is ok", func() {
// 				sampleResource := map[string]interface{}{
// 					"Type": "AWS::Serverless::Function",
// 					"Properties": map[string]interface{}{
// 						"RequiredValue": "Set",
// 						"OptionalValue": 1,
// 					},
// 				}

// 				resource, error := sampleResourceDef.Scaffold(sampleResource)
// 				Expect(error).To(BeNil())
// 				Expect(resource).ToNot(BeNil())
// 				Expect(resource["Type"]).To(Equal(sampleResource["Type"]))

// 				resourceProperties := resource["Properties"].(map[string]interface{})
// 				sampleResourceProperties := sampleResource["Properties"].(map[string]interface{})

// 				Expect(resourceProperties["RequiredValue"]).To(Equal(sampleResourceProperties["RequiredValue"]))
// 				Expect(resourceProperties["OptionalValue"]).To(Equal(sampleResourceProperties["OptionalValue"]))
// 				Expect(resourceProperties["StaticDefaultValue"]).To(Equal("My default value"))
// 				Expect(resourceProperties["DynamicDefaultValue"]).To(Equal("My dynamic value"))

// 				resourceReturnValues, returnValuesSet := resource["ReturnValues"]
// 				Expect(returnValuesSet).To(BeTrue())
// 				Expect(resourceReturnValues).ToNot(BeNil())

// 				returnValues := resourceReturnValues.(map[string]string)

// 				Expect(returnValues["Ref"]).To(Equal("Whatever"))
// 				Expect(returnValues["Arn"]).To(Equal("ARN"))
// 				Expect(returnValues["TheRequiredValue"]).To(Equal(sampleResourceProperties["RequiredValue"]))

// 			})
// 		})
// 	})

// })

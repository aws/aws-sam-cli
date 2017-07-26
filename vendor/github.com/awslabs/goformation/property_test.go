package goformation_test

// import (
// 	. "github.com/onsi/ginkgo"
// 	. "github.com/onsi/gomega"
// )

// var _ = Describe("Base properties", func() {

// 	Context("Upon creation", func() {

// 		It("Should validate they receive at least receive one type", func() {
// 			_, error := newProperty([]string{}, false, "", nil)
// 			Expect(error).ToNot(BeNil())
// 			Expect(error).To(Equal(ErrUnsetPropertyType))
// 		})

// 		It("Should validate that it receives either a String or an array as type", func() {
// 			_, error := newProperty(1, false, "", nil)
// 			Expect(error).ToNot(BeNil())
// 			Expect(error).To(Equal(ErrInvalidPropertyTypeObject))
// 		})

// 		It("Should validate the types given are valid", func() {
// 			_, error := newProperty("wrong", false, 1, nil)
// 			Expect(error).ToNot(BeNil())
// 			Expect(error).To(Equal(ErrInvalidPropertyType))
// 		})

// 		It("Should validate the default value is of a valid type", func() {
// 			_, error := newProperty("string", false, 1, nil)
// 			Expect(error).ToNot(BeNil())
// 			Expect(error).To(Equal(ErrInvalidPropertyDefaultValueType))
// 		})

// 		It("Should accept a valid property", func() {
// 			property, error := newProperty([]string{"string"}, false, "default", nil)
// 			Expect(error).To(BeNil())
// 			Expect(property).ToNot(BeNil())
// 			Expect(property.Types).To(BeEquivalentTo([]string{"string"}))
// 			Expect(property.Required).To(Equal(false))
// 			Expect(property.Default).To(Equal("default"))
// 		})

// 		Describe("For referenced types", func() {
// 			It("Should validate that a resource is given", func() {
// 				_, error := newProperty([]string{"Resource"}, false, "default", nil)
// 				Expect(error).ToNot(BeNil())
// 				Expect(error).To(Equal(ErrResourceNotSetForReferencedProperty))
// 			})

// 			It("Should associate the Resource with the Property", func() {
// 				resource := Resource{}
// 				property, error := NewReferenceProperty([]string{"Resource"}, false, resource, nil)
// 				Expect(error).To(BeNil())
// 				Expect(property.Resource).ToNot(BeNil())
// 				Expect(property.Resource).To(Equal(resource))
// 			})
// 		})
// 	})

// 	Context("Upon definition", func() {

// 		It("Should validate that the types object is set", func() {
// 			config := map[string]interface{}{}
// 			_, error := DefineProperty(config)
// 			Expect(error).ToNot(BeNil())
// 			Expect(error).To(Equal(ErrPropertyDefinitionUnsetType))
// 		})

// 		It("Should create a simple property if given correct input", func() {
// 			config := map[string]interface{}{
// 				"Types":    []string{"string"},
// 				"Required": true,
// 				"Default":  "abcd",
// 			}

// 			property, error := DefineProperty(config)
// 			Expect(error).To(BeNil())
// 			Expect(property).ToNot(BeNil())
// 			Expect(property.Types).To(Equal(config["Types"]))
// 			Expect(property.Required).To(Equal(config["Required"]))
// 			Expect(property.Default).To(Equal(config["Default"]))
// 		})

// 		It("Should create a referenced property if given correct input", func() {
// 			config := map[string]interface{}{
// 				"Types":    []string{"Resource"},
// 				"Required": true,
// 				"Resource": Resource{},
// 			}

// 			property, error := DefineProperty(config)
// 			Expect(error).To(BeNil())
// 			Expect(property).ToNot(BeNil())
// 			Expect(property.Types).To(Equal(config["Types"]))
// 			Expect(property.Required).To(Equal(config["Required"]))
// 			Expect(property.Resource).To(Equal(config["Resource"]))
// 		})
// 	})

// 	Context("Upon scaffolding", func() {
// 		var error error
// 		var property Property

// 		Describe("Primitive values", func() {

// 			BeforeEach(func() {
// 				property, error = newProperty("string", true, "def", nil)
// 				if error != nil {
// 					log.Panic("Property generation failed upon execution!")
// 				}
// 			})

// 			It("Should validate the data against the type", func() {
// 				var value int = 1
// 				_, error := property.Scaffold(value)
// 				Expect(error).ToNot(BeNil())
// 				Expect(error).To(Equal(ErrInvalidPropertyValueType))
// 			})

// 			It("Should return the value back if there are no errors", func() {
// 				var value string = "Test"
// 				result, error := property.Scaffold(value)
// 				Expect(error).To(BeNil())
// 				Expect(result).ToNot(BeNil())
// 				Expect(result).To(BeEquivalentTo(value))
// 			})
// 		})
// 	})

// })

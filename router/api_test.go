package router_test

import (
	"strings"

	"github.com/awslabs/aws-sam-local/router"
	"github.com/awslabs/goformation/cloudformation"

	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"
)

func getApiResourceFromTemplate(path string) *router.AWSServerlessApi {
	templateUri := &path
	apiResource := &router.AWSServerlessApi{
		AWSServerlessApi: &cloudformation.AWSServerlessApi{
			DefinitionUri: &cloudformation.AWSServerlessApi_DefinitionUri{
				String: templateUri,
			},
		},
	}
	return apiResource
}

var _ = Describe("Api", func() {

	Context("Load local Swagger definitions", func() {
		It("Succesfully loads the basic template", func() {
			apiResource := getApiResourceFromTemplate("../test/templates/open-api/pet-store-simple.json")

			mounts, err := apiResource.Mounts()

			Expect(err).Should(BeNil())
			Expect(mounts).ShouldNot(BeNil())

			Expect(mounts).ShouldNot(BeEmpty())
			Expect(len(mounts)).Should(BeIdenticalTo(4))
		})

		It("Succesfully reads integration definition", func() {
			apiResource := getApiResourceFromTemplate("../test/templates/open-api/pet-store-simple.json")

			mounts, err := apiResource.Mounts()

			Expect(err).Should(BeNil())
			Expect(mounts).ShouldNot(BeNil())

			for _, mount := range mounts {
				if mount.Method == "get" && mount.Path == "/pets" {
					Expect(mount.IntegrationArn.Arn).Should(BeIdenticalTo("arn:aws:lambda:us-west-2:123456789012:function:Calc"))
				}
			}
		})

		It("Loads the proxy template", func() {
			apiResource := getApiResourceFromTemplate("../test/templates/open-api/pet-store-proxy.json")

			mounts, err := apiResource.Mounts()

			Expect(err).Should(BeNil())
			Expect(mounts).ShouldNot(BeNil())
			// we expect 9 here because the any method should generate all 7
			Expect(len(mounts)).To(BeIdenticalTo(9))

			for _, mount := range mounts {
				if mount.Method == "post" && mount.Path == "/pets/{proxy+}" {
					Expect(mount.IntegrationArn.Arn).Should(ContainSubstring("AnyMethod"))
				}
				if mount.Method == "delete" && mount.Path == "/pets/{proxy+}" {
					Expect(mount.IntegrationArn.Arn).Should(ContainSubstring("Calc"))
				}
			}
		})

		It("Loads a YAML Swagger template", func() {
			apiResource := getApiResourceFromTemplate("../test/templates/open-api/simple-yaml.yaml")

			mounts, err := apiResource.Mounts()
			Expect(err).To(BeNil())
			Expect(mounts).ToNot(BeNil())
			Expect(1).To(Equal(len(mounts)))
			Expect("/").To(Equal(mounts[0].Path))
			Expect("post").To(Equal(strings.ToLower(mounts[0].Method)))
		})

	})
})

package main

import (
	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"
)

var _ = Describe("Parse Cloudformation parameters", func() {

	Context("with normal input", func() {

		It("returns empty map when input is missing", func() {
			p := parseParameters("")
			Expect(p).To(BeEmpty())
		})

		It("returns expected values when input is correct", func() {
			p := parseParameters("ParameterKey=KeyPairName,ParameterValue=MyKey ParameterKey=InstanceType,ParameterValue=t1.micro")
			Expect(p).To(HaveLen(2))
			Expect(p).To(HaveKeyWithValue("KeyPairName", "MyKey"))
			Expect(p).To(HaveKeyWithValue("InstanceType", "t1.micro"))
		})

		It("returns partial values when input is malformed", func() {
			p := parseParameters("ParameterKey=KeyPairName,ParameterValue=MyKey Para")
			Expect(p).To(HaveLen(1))
			Expect(p).To(HaveKeyWithValue("KeyPairName", "MyKey"))
		})
	})

	Context("with escaped input", func() {

		It("returns expected values when keys or values are quoted", func() {
			p := parseParameters(`ParameterKey="KeyPairName",ParameterValue="MyKey " ParameterKey=InstanceType,ParameterValue=t1\ mic\ ro`)
			Expect(p).To(HaveLen(2))
			Expect(p).To(HaveKeyWithValue("KeyPairName", "MyKey "))
			Expect(p).To(HaveKeyWithValue("InstanceType", "t1 mic ro"))
		})

		It("handles wrong quotings", func() {
			p := parseParameters(`ParameterKey="KeyPairName,ParameterValue="MyKey" ParameterKey=InstanceType,ParameterValue=t1\ micro`)
			Expect(p).To(HaveLen(1))
			Expect(p).To(HaveKeyWithValue("InstanceType", "t1 micro"))
		})

	})
})

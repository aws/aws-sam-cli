package main

import (
	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"

	"testing"
)

func TestAwsSamLocal(t *testing.T) {
	RegisterFailHandler(Fail)
	RunSpecs(t, "AwsSamLocal Suite")
}

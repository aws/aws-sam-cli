package intrinsics_test

import (
	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"

	"testing"
)

func TestIntrinsics(t *testing.T) {
	RegisterFailHandler(Fail)
	RunSpecs(t, "Intrinsics Suite")
}

package main

import (
	"io/ioutil"
	"time"

	"gopkg.in/yaml.v2"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/s3"
)

// checkVersionResult contains information on the current version of AWS SAM CLI, and
// whether there are any newer versions available to upgrade to.
type checkVersionResult struct {
	IsUpToDate    bool
	LatestVersion *versionManifest
}

// versionManifest mirrors the VERSION file generated for SAM CLI
// as part of the build process
type versionManifest struct {
	Version string    `yaml:"Version"`
	GitHash string    `yaml:"GitHash"`
	BuiltBy string    `yaml:"BuiltBy"`
	BuiltAt time.Time `yaml:"BuiltAt"`
}

// checkVersion checks whether the current version of AWS SAM CLI is the latest
func checkVersion() (*checkVersionResult, error) {

	// Get the latest version details from S3
	sess := session.Must(session.NewSession(&aws.Config{
		Region: aws.String("eu-west-1"),
	}))
	svc := s3.New(sess)

	obj, err := svc.GetObject(&s3.GetObjectInput{
		Bucket: aws.String("aws-sam-clii"),
		Key:    aws.String("releases/latest/VERSION"),
	})

	if err != nil {
		return &checkVersionResult{}, err
	}

	data, err := ioutil.ReadAll(obj.Body)
	if err != nil {
		return &checkVersionResult{}, err
	}

	vm := &versionManifest{}
	if err := yaml.Unmarshal(data, vm); err != nil {
		return &checkVersionResult{}, err
	}

	return &checkVersionResult{
		LatestVersion: vm,
		IsUpToDate:    Version == vm.Version,
	}, nil

}

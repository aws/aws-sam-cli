package main

import (
	"io/ioutil"
	"net/http"
	"time"

	"gopkg.in/yaml.v2"
)

// checkVersionResult contains information on the current version of AWS SAM CLI, and
// whether there are any newer versions available to upgrade to.
type checkVersionResult struct {
	IsUpToDate bool
	*versionManifest
}

// versionManifest mirrors the VERSION file generated for SAM CLI
// as part of the build process.
type versionManifest struct {
	Version string    `yaml:"Version"`
	GitHash string    `yaml:"GitHash"`
	BuiltBy string    `yaml:"BuiltBy"`
	BuiltAt time.Time `yaml:"BuiltAt"`
}

// checkVersion checks whether the current version of AWS SAM CLI is the latest
func checkVersion() (*checkVersionResult, error) {

	// Get the latest version details from S3
	var client = &http.Client{
		Timeout: time.Second * 10,
	}

	url := "https://aws-sam-cli.s3-eu-west-1.amazonaws.com/releases/latest/VERSION"
	response, err := client.Get(url)
	if err != nil {
		return &checkVersionResult{}, err
	}

	if err != nil {
		return &checkVersionResult{}, err
	}

	data, err := ioutil.ReadAll(response.Body)
	if err != nil {
		return &checkVersionResult{}, err
	}

	vm := &versionManifest{}
	if err := yaml.Unmarshal(data, vm); err != nil {
		return &checkVersionResult{}, err
	}

	return &checkVersionResult{
		versionManifest: vm,
		IsUpToDate:      Version == "SNAPSHOT" || Version == vm.Version,
	}, nil

}

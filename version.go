package main

import (
	"context"
	"log"

	"github.com/google/go-github/github"
)

// checkVersionResult contains information on the current version of AWS SAM CLI, and
// whether there are any newer versions available to upgrade to.
type checkVersionResult struct {
	IsUpToDate    bool
	LatestVersion string
}

// checkVersion checks whether the current version of AWS SAM CLI is the latest
func checkVersion() (*checkVersionResult, error) {

	const RepoOwner = "awslabs"
	const RepoName = "aws-sam-cli"

	// Get the latest version details from Github release
	gh := github.NewClient(nil)
	releases, _, err := gh.Repositories.ListReleases(context.Background(), RepoOwner, RepoName, nil)
	if err != nil {
		return &checkVersionResult{}, err
	}

	// Grab the latest release - without the first 'v' character from the tag
	// ie. v0.0.1 -> 0.0.1
	latest := releases[0]
	latestVersion := (*latest.TagName)[1:]
	log.Print(latestVersion)

	return &checkVersionResult{
		LatestVersion: latestVersion,
		IsUpToDate:    BuildVersion == latestVersion,
	}, nil

}

package main

import (
	"context"
	"net/http"
	"time"

	"github.com/google/go-github/github"
)

// githubTimeout defines how long to wait for a response from GitHub
// when checking for new SAM Local versions.
const githubTimeout = 3

// checkVersionResult contains information on the current version of AWS SAM CLI, and
// whether there are any newer versions available to upgrade to.
type checkVersionResult struct {
	IsUpToDate    bool
	LatestVersion string
}

// checkVersion checks whether the current version of AWS SAM CLI is the latest
func checkVersion() (*checkVersionResult, error) {

	const RepoOwner = "awslabs"
	const RepoName = "aws-sam-local"

	// Create a HTTP client with appropriate timeouts configured
	client := &http.Client{
		Timeout: time.Duration(githubTimeout * time.Second),
	}

	// Get the latest version details from Github release
	gh := github.NewClient(client)
	releases, _, err := gh.Repositories.ListReleases(context.Background(), RepoOwner, RepoName, nil)
	if err != nil || len(releases) == 0 {
		return &checkVersionResult{}, err
	}

	// Grab the latest release - without the first 'v' character from the tag
	// ie. v0.0.1 -> 0.0.1
	latest := releases[0]
	latestVersion := (*latest.TagName)[1:]

	return &checkVersionResult{
		LatestVersion: latestVersion,
		IsUpToDate:    version == latestVersion,
	}, nil

}

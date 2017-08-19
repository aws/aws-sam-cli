package main

import "strings"

// filename takes a resource or property name (e.g. AWS::CloudFront::Distribution.Restrictions)
// and returns an appropriate filename for the generated struct (e.g. aws-cloudfront-distribution_restrictions.go)
func filename(input string) string {

	// Convert to lowercase
	output := strings.ToLower(input)

	// Replace :: with -
	output = strings.Replace(output, "::", "-", -1)

	// Replace . with _
	output = strings.Replace(output, ".", "_", -1)

	// Suffix with .go
	output += ".go"

	return output

}

// structName takes a resource or property name (e.g. AWS::CloudFront::Distribution.Restrictions)
// and returns an appropriate struct name for the generated struct (e.g. AWSCloudfrontDistributionRestrictions)
func structName(input string) string {

	// Remove ::
	output := strings.Replace(input, "::", "", -1)

	// Remove .
	output = strings.Replace(output, ".", "_", -1)

	return output

}

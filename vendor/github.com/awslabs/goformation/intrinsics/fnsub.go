package intrinsics

import (
	"strings"
)

// FnSub resolves the 'Fn::Sub' AWS CloudFormation intrinsic function.
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-sub.html
func FnSub(name string, input interface{}, template interface{}) interface{} {

	// { "Fn::Sub": [ "some ${replaced}", { "replaced": "value" } ] }

	// Check the input is an array
	if arr, ok := input.([]interface{}); ok {
		// The first element is the source
		if src, ok := arr[0].(string); ok {
			// The seconds element is a map of variables to replace
			if replacements, ok := arr[1].(map[string]interface{}); ok {
				// Loop through the replacements
				for key, replacement := range replacements {
					// Check the replacement is a string
					if value, ok := replacement.(string); ok {
						src = strings.Replace(src, "${"+key+"}", value, -1)
					}
				}
				return src
			}
		}
	}

	return nil

}

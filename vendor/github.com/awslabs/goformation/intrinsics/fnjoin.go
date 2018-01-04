package intrinsics

// FnJoin resolves the 'Fn::Join' AWS CloudFormation intrinsic function.
// See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-join.html
func FnJoin(name string, input interface{}, template interface{}) interface{} {

	result := ""

	// Check the input is an array
	if arr, ok := input.([]interface{}); ok {
		for _, value := range arr {
			if str, ok := value.(string); ok {
				result += str
			}
		}
	}

	return result

}

package intrinsics

import (
	"encoding/json"
	"fmt"
)

// IntrinsicHandler is a function that applies an intrinsic function and returns
// the response that should be placed in it's place. An intrinsic handler function
// is passed the name of the intrinsic function (e.g. Fn::Join), and the object
// to apply it to (as an interface{}), and should return the resolved object (as an interface{}).
type IntrinsicHandler func(string, interface{}) interface{}

// IntrinsicFunctionHandlers is a map of all the possible AWS CloudFormation intrinsic
// functions, and a handler function that is invoked to resolve.
var defaultIntrinsicHandlers = map[string]IntrinsicHandler{
	"Fn::Base64":      nonResolvingHandler,
	"Fn::And":         nonResolvingHandler,
	"Fn::Equals":      nonResolvingHandler,
	"Fn::If":          nonResolvingHandler,
	"Fn::Not":         nonResolvingHandler,
	"Fn::Or":          nonResolvingHandler,
	"Fn::FindInMap":   nonResolvingHandler,
	"Fn::GetAtt":      nonResolvingHandler,
	"Fn::GetAZs":      nonResolvingHandler,
	"Fn::ImportValue": nonResolvingHandler,
	"Fn::Join":        nonResolvingHandler,
	"Fn::Select":      nonResolvingHandler,
	"Fn::Split":       nonResolvingHandler,
	"Fn::Sub":         nonResolvingHandler,
	"Ref":             nonResolvingHandler,
}

// ProcessorOptions allows customisation of the intrinsic function processor behaviour.
// Initially, this only allows overriding of the handlers for each intrinsic function type.
type ProcessorOptions struct {
	IntrinsicHandlerOverrides map[string]IntrinsicHandler
}

// nonResolvingHandler is a simple example of an intrinsic function handler function
// that refuses to resolve any intrinsic functions, and just returns a basic string.
func nonResolvingHandler(name string, input interface{}) interface{} {
	result := fmt.Sprintf("%s intrinsic function is unsupported", name)
	return result
}

// Process recursively searches through a byte array for all AWS CloudFormation
// intrinsic functions, resolves them, and then returns the resulting
// interface{} object.
func Process(input []byte, options *ProcessorOptions) ([]byte, error) {

	// First, unmarshal the JSON to a generic interface{} type
	var unmarshalled interface{}
	if err := json.Unmarshal(input, &unmarshalled); err != nil {
		return nil, fmt.Errorf("invalid JSON: %s", err)
	}

	// Process all of the intrinsic functions
	processed := search(unmarshalled, options)

	// And return the result back as a []byte of JSON
	result, err := json.MarshalIndent(processed, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("invalid JSON: %s", err)
	}

	return result, nil

}

// Search is a recursive function, that will search through an interface{} looking for
// an intrinsic function. If it finds one, it calls the provided handler function, passing
// it the type of intrinsic function (e.g. 'Fn::Join'), and the contents. The intrinsic
// handler is expected to return the value that is supposed to be there.
func search(input interface{}, options *ProcessorOptions) interface{} {

	switch value := input.(type) {

	case map[string]interface{}:

		// We've found an object in the JSON, it might be an intrinsic, it might not.
		// To check, we need to see if it contains a specific key that matches the name
		// of an intrinsic function. As golang maps do not guarentee ordering, we need
		// to check every key, not just the first.
		processed := map[string]interface{}{}
		for key, val := range value {

			// See if we have an intrinsic handler function for this object key provided in the
			if h, ok := handler(key, options); ok {
				// This is an intrinsic function, so replace the intrinsic function object
				// with the result of calling the intrinsic function handler for this type
				return h(key, search(val, options))
			}

			// This is not an intrinsic function, recurse through it normally
			processed[key] = search(val, options)

		}
		return processed

	case []interface{}:

		// We found an array in the JSON - recurse through it's elements looking for intrinsic functions
		processed := []interface{}{}
		for _, val := range value {
			processed = append(processed, search(val, options))
		}
		return processed

	case nil:
		return value
	case bool:
		return value
	case float64:
		return value
	case string:
		return value
	default:
		return nil

	}

}

// handler looks up the correct intrinsic function handler for an object key, if there is one.
// If not, it returns nil, false.
func handler(name string, options *ProcessorOptions) (IntrinsicHandler, bool) {

	// Check if we have a handler for this intrinsic type in the instrinsic handler
	// overrides in the options provided to Process()
	if options != nil {
		if h, ok := options.IntrinsicHandlerOverrides[name]; ok {
			return h, true
		}
	}

	if h, ok := defaultIntrinsicHandlers[name]; ok {
		return h, true
	}

	return nil, false

}

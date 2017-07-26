package resources

import (
	"strings"

	"github.com/awslabs/goformation/util"
)

// EventSource represents each of a function's event sources
// The properties are captures as a yaml.MapSlice so they can be
// unmarshalled at runtime into different event type structs depending
// on the event source Type.
type AWSServerlessFunctionEventSource interface {
	Type() string
	Properties() map[string]string
}

type eventSource struct {
	EType       string            `yaml:"Type"`
	EProperties map[string]string `yaml:"Properties"`
}

//
// AWSServerlessFunctionEventSource interface
//

func (e *eventSource) Type() string {
	return e.EType
}

func (e *eventSource) Properties() map[string]string {
	return e.EProperties
}

//
// End AWSServerlessFunctionEventSource interface
//

//
// Scaffoldable interface
//
func (e *eventSource) Scaffold(input Resource, propName string) (Resource, error) {
	// TODO Set proper event (API, SFN) if exists

	propRaw := input.Properties()[propName]
	prop := propRaw.Value().(map[string]interface{})
	e.EType = prop["Type"].(string)
	e.EProperties = prop["Properties"].(map[string]string)

	return input, nil
}

func scaffoldEventSourceMap(prop Property) map[string]AWSServerlessFunctionEventSource {
	propValue := prop.Value()
	if propValue == nil {
		return make(map[string]AWSServerlessFunctionEventSource)
	}

	events, eventsOk := propValue.(map[string]Property)
	if !eventsOk {
		evtString, evtStringOk := propValue.(string)
		if evtStringOk {
			util.LogDebug(-1, "AWS::Serverless::Function", "`Events` is a string: %s", evtString)
			return map[string]AWSServerlessFunctionEventSource{}
		}

	}
	resultEvents := make(map[string]AWSServerlessFunctionEventSource)
	for key, esProp := range events {
		propValue := esProp.Value().(map[string]Property)
		propType := propValue["Type"].Value().(string)
		propProperties := propValue["Properties"].Value()

		newProps := make(map[string]string)
		oldProps, oldPropsOk := propProperties.(map[interface{}]interface{})
		if oldPropsOk {
			for pKey, pValue := range oldProps {
				var ppKey string
				var ppValue string

				if keyPtr, keyPtrOk := pKey.(*string); keyPtrOk {
					ppKey = *keyPtr
				} else {
					ppKey = pKey.(string)
				}

				if pValueArray, pValueArrayOk := pValue.([]interface{}); pValueArrayOk {
					strArray := make([]string, len(pValueArray))
					for ppk, ppv := range pValueArray {
						strArray[ppk] = ppv.(string)
					}

					ppValue = strings.Join(strArray, ", ")
				} else if pValueMap, pValueMapOk := pValue.(map[interface{}]interface{}); pValueMapOk {
					strMap := make(map[string]string)
					for ppk, ppv := range pValueMap {
						strMap[ppk.(string)] = ppv.(string)
					}

					ppValue = "Temprarily unmapped"
				} else {
					ppValue = pValue.(string)
				}

				newProps[ppKey] = ppValue
			}
		} else if propProp, propPropOk := propProperties.(Property); propPropOk {
			propPropValue := propProp.Value()
			propertiesMap := propPropValue.(map[string]string)
			newProps = propertiesMap
		}

		var event AWSServerlessFunctionEventSource = &eventSource{
			EType:       propType,
			EProperties: newProps,
		}
		if propType == "Api" {
			apiEvent := scaffolfApiEventSource(event)
			event = apiEvent
		}

		resultEvents[key] = event

	}

	return resultEvents
}

//
// End AWSServerlessFunctionEventSource interface
//

// AWSServerlessFunctionAPIEventSource Represents Lambda event sources linked to an API Gateway.
type AWSServerlessFunctionAPIEventSource interface {
	Path() string
	Methods() []string
	Api() string
	Type() string
	Properties() map[string]string
}

type apiEventSource struct {
	FPath    string `yaml:"Path"`
	FMethod  string `yaml:"Method"`
	FRestAPI string `yaml:"RestApiId"`
	original AWSServerlessFunctionEventSource
}

func (a *apiEventSource) Type() string {
	return a.original.Type()
}

func (a *apiEventSource) Properties() map[string]string {
	return a.original.Properties()
}

// Path returns the HTTP path the function should be mounted at
func (a *apiEventSource) Path() string {
	return a.FPath
}

// Methods returns a list of HTTP methods for the event source
func (a *apiEventSource) Methods() []string {

	switch strings.ToLower(a.FMethod) {
	case "any":
		return []string{"OPTIONS", "GET", "HEAD", "POST", "PUT", "DELETE", "TRACE", "CONNECT"}
	default:
		return []string{strings.ToUpper(a.FMethod)}
	}
}

// Api returns the Rest API for this event source
func (a *apiEventSource) Api() string {
	return a.FRestAPI
}

func scaffolfApiEventSource(event AWSServerlessFunctionEventSource) AWSServerlessFunctionAPIEventSource {

	aes := &apiEventSource{}
	aes.original = event

	eventProps := event.Properties()
	aes.FPath = eventProps["Path"]
	aes.FMethod = eventProps["Method"]
	aes.FRestAPI = eventProps["RestApiId"]

	return aes
}

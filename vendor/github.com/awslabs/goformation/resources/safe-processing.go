package resources

import (
	"strconv"
	"strings"
)

func safeProcessInt(prop Property) int {
	value := prop.Value()
	if value == nil {
		return -99999
	}

	if valueInt, valueIntOk := value.(int); valueIntOk {
		return valueInt
	} else if valueStr, valueStrOk := value.(string); valueStrOk {
		ret, error := strconv.ParseInt(valueStr, 10, 32)
		if error != nil {
			// Something happened
			return -99999
		}

		return int(ret)
	}

	return value.(int)
}

func safeProcessString(prop Property) string {
	value := prop.Value()
	if value == nil {
		return ""
	} else if _, valueString := value.(string); !valueString {
		return ""
	}

	return value.(string)
}

func safeProcessStringArray(prop Property) []string {
	value := prop.Value()

	if valueArray, valueArrayOk := value.([]interface{}); valueArrayOk {
		ret := make([]string, len(valueArray))
		for pKey, pValue := range valueArray {
			ret[pKey] = pValue.(string)
		}

		return ret
	}

	return []string{}
}

func safeProcessStringMap(prop Property) map[string]string {
	value := prop.Value()

	if valueMap, valueMapOk := value.(map[interface{}]interface{}); valueMapOk {
		ret := make(map[string]string)
		for pKey, pValue := range valueMap {
			var pKeyParsed string
			var pValueParsed string
			if pKeyPtr, pKeyPtrOk := pKey.(*string); pKeyPtrOk {
				pKeyParsed = *pKeyPtr
			} else if pKeyStr, pKeyStrOk := pKey.(string); pKeyStrOk {
				pKeyParsed = pKeyStr
			}

			pValueParsed = ""
			if pValueString, pValueStringOk := pValue.(string); pValueStringOk {
				pValueParsed = pValueString
			} else {
				pValueParsed, _ = toStringMaybe(pValue)
			}

			ret[pKeyParsed] = pValueParsed
		}

		return ret
	}

	return map[string]string{}
}

func safeProcessRaw(prop Property) interface{} {
	value := prop.Value()

	switch value.(type) {
	case string:
		return safeProcessString(prop)
	case int:
		return safeProcessInt(prop)
	case []interface{}:
		return safeProcessStringArray(prop)
	case map[interface{}]interface{}:
		return safeProcessStringMap(prop)
	}

	return nil
}

func safeCastToString(prop Property) string {
	value := prop.Value()

	switch value.(type) {
	case string:
		return value.(string)
	case int:
		return string(value.(int))
	case []string:
		return strings.Join(value.([]string), ", ")
	case map[string]string:
		var ret = ""
		for k, v := range value.(map[string]string) {
			ret += k + `: ` + v + `, `
		}

		return ret
	}

	return ""
}

// Converts the input to string if it is a primitive type, Otherwise returns nil
func toStringMaybe(value interface{}) (string, bool) {

	switch value.(type) {
	case string:
		return value.(string), true
	case int:
		return strconv.Itoa(value.(int)), true
	case float32, float64:
		return strconv.FormatFloat(value.(float64), 'f', -1, 64), true
	case bool:
		return strconv.FormatBool(value.(bool)), true
	default:
		return "", false
	}
}

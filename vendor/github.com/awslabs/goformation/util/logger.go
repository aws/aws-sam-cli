package util

import (
	"log"
	"regexp"
	"strings"
)

var logs = map[string][]string{
	"DEBUG": []string{},
	"INFO":  []string{},
	"WARN":  []string{},
	"ERROR": []string{},
	"FATAL": []string{},
}

// GetLogs Returns the logs fetched during the parsing process of your template.
func GetLogs() map[string][]string {
	return logs
}

// LogDebug adds a line of DEBUG log
func LogDebug(line int, place string, message string, arguments ...interface{}) {
	logRaw("DEBUG", line, place, message, arguments)
}

// LogInfo adds a line of INFO log
func LogInfo(line int, place string, message string, arguments ...interface{}) {
	logRaw("INFO", line, place, message, arguments)
}

// LogWarning adds a line of WARNING log
func LogWarning(line int, place string, message string, arguments ...interface{}) {
	logRaw("WARN", line, place, message, arguments)
}

// LogError adds a line of ERROR log
func LogError(line int, place string, message string, arguments ...interface{}) {
	logRaw("ERROR", line, place, message, arguments)
}

// LogCritical adds a line of CRITICAL log
func logCritical(line int, place string, message string, arguments ...interface{}) {
	logRaw("FATAL", line, place, message, arguments)
}

func logRaw(logType string, line int, place string, message string, arguments []interface{}) {
	parameterRegex := regexp.MustCompile(`\%(s|d)`)
	var processedMessage = message

	occurrences := parameterRegex.FindAllString(message, -1)
	if len(occurrences) != len(arguments) {
		log.Panic("Trying to log with different argument and placeholder numbers")
	}

	for key, occurrence := range occurrences {
		value := arguments[key]

		var stringValue string
		switch value.(type) {
		case string:
			stringValue = value.(string)
		case int:
			stringValue = string(value.(int))
		case int64:
			stringValue = string(value.(int64))
		case []string:
			stringValue = strings.Join(value.([]string), ", ")
		default:
			stringValue = "Object [Object]"
		}

		messageSplit := strings.SplitN(processedMessage, occurrence, 2)
		processedMessage = strings.Join(messageSplit, stringValue)
	}

	strLog := ""
	if line != -1 {
		strLog = processedMessage + ` - ` + place + `(` + string(line) + `).`
	} else {
		strLog = processedMessage + ` - ` + place + `.`
	}

	logs[logType] = append(logs[logType], strLog)
}

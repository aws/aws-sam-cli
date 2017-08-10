package resources

import (
	"errors"
	"log"
	"regexp"
)

var (
	// ErrNoIntrinsicFunctionFound Launched when calling param processor without intrinsic.
	// This Doesn't propagate, and it just tells the marshaller to stop attempting to resolve.
	ErrNoIntrinsicFunctionFound = errors.New("No intrinsic function found")
)

func ProcessLineNumbers(input []byte) LineDictionary {
	level0Regex := regexp.MustCompile(`(Parameters|Resources|Outputs):`)
	keyValueRegex := regexp.MustCompile(`([\w]+):\s*(.*)`)
	awsFnValueRegex := regexp.MustCompile(`(Fn::)(Base64|FindInMap|GetAtt|GetAZs|ImportValue|Join|Select|Split|Sub):\s*(.*)`)
	arrayItemRegex := regexp.MustCompile(`\-\s*(.*)`)
	multilineRegex := regexp.MustCompile(`.+\|`)

	lineRegex := `\n([ \t]*)([A-Za-z0-9:\-_,\<\>\=\+\*\. \[\]\{\}\(\)\/\\\"\'$#!\|]+)?`
	compiledRegex := regexp.MustCompile(lineRegex)

	template := `\n` + string(input) // TODO Improve concat

	occurrences := compiledRegex.FindAllStringSubmatch(template, -1)

	// Create Root level
	var RootObj = &lineDictionary{
		_line:        0,
		_level:       -1,
		_indentLevel: -1,
		_value:       "ROOT",
		_type:        "TemplateRoot",
		_end:         false,
	}

	var tabsAreTabsRegex = `\t`
	var previousDictionary = RootObj
	var currentParent = RootObj
	parentHierarchy := map[int]*lineDictionary{
		-1: RootObj,
	}
	multilineActive := false
	multilineLevel := -1
	indentSpacing := -1
	for line, occurrence := range occurrences {
		var tabs = occurrence[1]
		var value = occurrence[2]

		multiLineMatch := multilineRegex.MatchString(value)

		// Ignore empty line
		if len(value) == 0 {
			continue
		}
		// TODO Ignore line with only spaces

		tabsAreTabs, _ := regexp.Match(tabsAreTabsRegex, []byte(tabs))
		level := len(tabs)

		if indentSpacing == -1 && !multilineActive && !multiLineMatch && level > 0 {
			indentSpacing = level
		}

		indentLevel := level
		if level > 0 && !tabsAreTabs {
			if indentSpacing == -1 {
				indentSpacing = 2
			}

			indentLevel = level / indentSpacing
		}

		if multilineActive {
			if indentLevel > multilineLevel {
				previousDictionary._value += value
				continue
			}

			multilineActive = false
			multilineLevel = -1
		}

		if multiLineMatch {
			multilineActive = true
			multilineLevel = indentLevel
		}

		dictionary := &lineDictionary{
			_line:        line + 2, // FIXME Line 1 is not yet being parsed (and +1 to start in 1.)
			_level:       level,
			_indentLevel: indentLevel,
			_value:       value,
		}

		// if !tabsAreTabs {
		// 	dictionary._level *= 2
		// }

		// Have we increased, decreased, or maintain level?
		levelDiff := indentLevel - previousDictionary.IndentLevel()

		if levelDiff == 0 {
			// If we maintain, we still don't know what to do. Let's just store the item and keep going.
			// That's done below.

			// My parent is the previous's parent, as I didn't change level.
			currentParent = previousDictionary._parent
		} else if levelDiff < 0 {
			// If the substraction is negative, it means we decreased one or more levels.
			// The parent has to change to this current, and the previous needs to be marked as End.
			openedParent, openedParentOk := parentHierarchy[indentLevel-1]
			if !openedParentOk {
				log.Panicf("PANIC: YAML contains malformed structures")
			}

			currentParent = openedParent
		} else {
			parentHierarchy[previousDictionary._indentLevel] = previousDictionary
			// Otherwise we have increased a level, and that means appending children to the previous
			// and set it up as a parent so we could keep adding children.

			// My parent is, obviously, the previous'.
			currentParent = previousDictionary
		}

		switch level {
		case 0:
			// We are either defining `Parameters`, `Resources`, or `Outputs`
			if level0Regex.MatchString(value) {
				// When parsing we found a non-valid level 1.
				// TODO What to do?
				attribute := level0Regex.FindStringSubmatch(value)
				dictionary._key = attribute[1]
			} else {
				// We are defining other things - e.g. Version, Transform, Description...
				dictionary._type = value
			}
		case 1:
			// We are either defining `Parameters`, `Resources`, or `Outputs`
			if keyValueRegex.MatchString(value) {
				// When parsing we found a non-valid level 1.
				// TODO What to do?
				attribute := keyValueRegex.FindStringSubmatch(value)
				dictionary._type = attribute[1]
				dictionary._key = attribute[1]
				dictionary._value = attribute[2]
			} else {
				dictionary._type = value
			}
		default:
			// Either properties or subproperties.
			// We'll call it all `Props`, to be cool.
			dictionary._type = "Props"

			if awsFnValueRegex.MatchString(value) {
				attribute := awsFnValueRegex.FindStringSubmatch(value)
				dictionary._key = attribute[1] + attribute[2]
				dictionary._value = attribute[3]
			} else if keyValueRegex.MatchString(value) {
				// When parsing we found a non-valid level 1.
				// TODO What to do?
				attribute := keyValueRegex.FindStringSubmatch(value)
				dictionary._key = attribute[1]
				dictionary._value = attribute[2]
			} else if arrayItemRegex.MatchString(value) {
				// Line is an array item. Process it like that

				attribute := arrayItemRegex.FindStringSubmatch(value)
				dictionary._key = attribute[1]
				if len(attribute) > 2 {
					dictionary._value = attribute[2]
				} else {
					dictionary._value = dictionary._key
				}
			}
		}

		// Append the element to the parent.
		currentParent.SetChildren(append(currentParent.Children(), dictionary))
		dictionary._parent = currentParent
		previousDictionary = dictionary

		if currentParent.IndentLevel() == -1 {
			// XXX I got no clue why this is needed.
			// FIXME Find why
			RootObj = currentParent
		}
	}

	return RootObj
}

// BEGIN lineDictionary definition

type lineDictionary struct {
	_line        int
	_level       int
	_indentLevel int
	_key         string
	_value       string
	_type        string
	_parent      *lineDictionary
	_children    []*lineDictionary
	_end         bool
}

func (l *lineDictionary) Line() int {
	return l._line
}
func (l *lineDictionary) Level() int {
	return l._level
}
func (l *lineDictionary) IndentLevel() int {
	return l._indentLevel
}
func (l *lineDictionary) Key() string {
	return l._key
}
func (l *lineDictionary) Value() string {
	return l._value
}
func (l *lineDictionary) Type() string {
	return l._type
}
func (l *lineDictionary) Parent() LineDictionary {
	return l._parent
}
func (l *lineDictionary) Children() []LineDictionary {
	if l == nil {
		return make([]LineDictionary, 0)
	}

	numChildren := 0
	if l._children != nil {
		numChildren = len(l._children)
	}
	ret := make([]LineDictionary, numChildren)
	for key, value := range l._children {
		ret[key] = value
	}
	return ret
}
func (l *lineDictionary) End() bool {
	return l._end
}
func (l *lineDictionary) SetChildren(input []LineDictionary) {
	l._children = make([]*lineDictionary, len(input))
	for key, value := range input {
		l._children[key] = value.(*lineDictionary)
	}
}

// END lineDictionary definition

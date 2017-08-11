package markup

import (
	"fmt"
	"strings"
)

type MarkupMarkDown struct {
}

// sectionHeader renders a title (level 1) or subtitle (level 2..5)
func (this *MarkupMarkDown) sectionHeader(level int, text string) string {
	return fmt.Sprintf("\n%s %s\n", strings.Repeat("#", level), text)
}

// numberedItem renders a bulleted item at the given level
func (this *MarkupMarkDown) numberedItem(level int, text string) string {
	return fmt.Sprintf("%s1. %s\n", strings.Repeat("    ", level-1), text)
}

// bulletedItem renders a bulleted item at the given level
func (this *MarkupMarkDown) bulletedItem(level int, text string) string {
	return fmt.Sprintf("%s* %s\n", strings.Repeat("    ", level-1), text)
}

// anchor renders a title (level 1) or subtitle (level 2..5)
func (this *MarkupMarkDown) anchor(anchorName string) string {
	return fmt.Sprintf("<a name=\"%s\"></a>\n", anchorName)
}

// link renders the linkText as a link to the specified anchorName. If linktext is "", then anchorName is used as the linkText.
func (this *MarkupMarkDown) link(anchorName, linkText string) string {
	if linkText == "" {
		return fmt.Sprintf("[%s](#%s)", anchorName, anchorName)
	}
	return fmt.Sprintf("[%s](#%s)", linkText, anchorName)
}

// tableHeader starts a table
func (this *MarkupMarkDown) tableHeader(tableTitle string) string {
	return "\n"
}

// tableHeaderRow issues a table header row
func (this *MarkupMarkDown) tableHeaderRow(args ...string) string {
	var retval string = ""
	var separator string = ""
	for _, arg := range args {
		retval += fmt.Sprintf("| %s ", arg)
		separator += "|-----"
	}
	return retval + "|\n" + separator + "|\n"
}

// tableRow issues a single table data row
func (this *MarkupMarkDown) tableRow(args ...string) string {
	var retval string = ""
	for _, arg := range args {
		retval += fmt.Sprintf("| %s ", arg)
	}
	return retval + "|\n"
}

// tableFooter ends a table
func (this *MarkupMarkDown) tableFooter() string {
	return "\n"
}

// Note: Github flavored markdown does not support colorization
func (this *MarkupMarkDown) colorSpan(content, foregroundColor, backgroundColor string) string {
	return content
}

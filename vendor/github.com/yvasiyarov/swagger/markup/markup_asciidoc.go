package markup

import (
	"fmt"
	"strings"
)

type MarkupAsciiDoc struct {
}

// anchor renders a title (level 1) or subtitle (level 2..5)
func (this *MarkupAsciiDoc) anchor(anchorName string) string {
	return fmt.Sprintf("[[%s]]\n", anchorName)
}

// sectionHeader renders a title (level 1) or subtitle (level 2..5)
func (this *MarkupAsciiDoc) sectionHeader(level int, text string) string {
	return fmt.Sprintf("%s %s\n", strings.Repeat("=", level), text)
}

// bullet renders a bulleted item at the given level
func (this *MarkupAsciiDoc) numberedItem(level int, text string) string {
	return fmt.Sprintf("%s %s\n", strings.Repeat(".", level), text)
}

// bullet renders a bulleted item at the given level
func (this *MarkupAsciiDoc) bulletedItem(level int, text string) string {
	return fmt.Sprintf("%s %s\n", strings.Repeat("*", level), text)
}

// link renders the linkText as a link to the specified anchorName. If linktext is "", then anchorName is used as the linkText.
func (this *MarkupAsciiDoc) link(anchorName, linkText string) string {
	if linkText == "" {
		return fmt.Sprintf("<<%s,%s>>", anchorName, anchorName)
	}
	return fmt.Sprintf("<<%s,%s>>", anchorName, linkText)
}

// tableHeader starts a table
func (this *MarkupAsciiDoc) tableHeader(tableTitle string) string {
	retval := "\n"
	if tableTitle != "" {
		retval += fmt.Sprintf(".%s\n", tableTitle)
	}
	return retval + "[width=\"60%\",options=\"header\"]\n|==========\n"
}

// tableHeader ends a table
func (this *MarkupAsciiDoc) tableFooter() string {
	return "|==========\n\n"
}

// tableRow issues a table header row
func (this *MarkupAsciiDoc) tableHeaderRow(args ...string) string {
	var retval string
	for _, arg := range args {
		retval += fmt.Sprintf("|%s ", arg)
	}
	return retval + "\n"
}

// tableRow issues a single table data row
func (this *MarkupAsciiDoc) tableRow(args ...string) string {
	var retval string
	for _, arg := range args {
		retval += fmt.Sprintf("|%s ", arg)
	}
	return retval + "\n"
}

func (this *MarkupAsciiDoc) colorSpan(content, foregroundColor, backgroundColor string) string {
	return fmt.Sprintf("[%s,%s-background]#%s#", foregroundColor, backgroundColor, content)
}

package markup

import (
	"fmt"
	"strings"
)

type MarkupConfluence struct {
}

// anchor renders a title (level 1) or subtitle (level 2..5)
func (this *MarkupConfluence) anchor(anchorName string) string {
	return fmt.Sprintf("{anchor:%s}\n", anchorName)
}

// sectionHeader renders a title (level 1) or subtitle (level 2..5)
func (this *MarkupConfluence) sectionHeader(level int, text string) string {
	return fmt.Sprintf("\nh%v. %s\n", level, text)
}

// bullet renders a bulleted item at the given level
func (this *MarkupConfluence) numberedItem(level int, text string) string {
	return fmt.Sprintf("%s %s\n", strings.Repeat("#", level), text)
}

// bullet renders a bulleted item at the given level
func (this *MarkupConfluence) bulletedItem(level int, text string) string {
	return fmt.Sprintf("%s %s\n", strings.Repeat("*", level), text)
}

// link renders the linkText as a link to the specified anchorName. If linktext is "", then anchorName is used as the linkText.
func (this *MarkupConfluence) link(anchorName, linkText string) string {
	if linkText == "" {
		return fmt.Sprintf("[#%s]", anchorName)
	}
	return fmt.Sprintf("[%s|#%s]", linkText, anchorName)
}

// tableHeader starts a table
func (this *MarkupConfluence) tableHeader(tableTitle string) string {
	return "\n"
}

// tableHeader ends a table
func (this *MarkupConfluence) tableFooter() string {
	return "\n"
}

// tableRow issues a table header row
func (this *MarkupConfluence) tableHeaderRow(args ...string) string {
	var retval string = ""
	for _, arg := range args {
		retval += fmt.Sprintf("||%s ", arg)
	}
	return retval + "||\n"
}

// tableRow issues a single table data row
func (this *MarkupConfluence) tableRow(args ...string) string {
	var retval string = ""
	for _, arg := range args {
		retval += fmt.Sprintf("|%s ", arg)
	}
	return retval + "|\n"
}

func (this *MarkupConfluence) colorSpan(content, foregroundColor, backgroundColor string) string {
	if foregroundColor == "black" && backgroundColor == "white" {
		return content
	}
	if foregroundColor == "black" {
		return fmt.Sprintf("{bgcolor:%s}%s{bgcolor}", backgroundColor, content)
	}
	if backgroundColor == "white" {
		return fmt.Sprintf("{color:%s}%s{color}", foregroundColor, content)
	}
	return fmt.Sprintf("{color:%s}{bgcolor:%s}%s{bgcolor}{color}", foregroundColor, backgroundColor, content)

}

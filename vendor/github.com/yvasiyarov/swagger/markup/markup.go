package markup

import (
	"bytes"
	"fmt"
	"os"
	"path"
	"sort"
	"strings"

	"github.com/yvasiyarov/swagger/parser"
)

const (
	color_NORMAL_TEXT             = "black"
	color_API_SECTION_HEADER_TEXT = "red"
	color_MODEL_TEXT              = "orange"
	color_NORMAL_BACKGROUND       = "white"
	color_GET                     = "cyan"
	color_POST                    = "green"
	color_PUT                     = "orange"
	color_DELETE                  = "cyan"
	color_PATCH                   = "purple"
	color_DEFAULT                 = "yellow"
)

type Markup interface {
	sectionHeader(level int, text string) string
	bulletedItem(level int, text string) string
	numberedItem(level int, text string) string
	anchor(anchorName string) string
	link(anchorName, linkText string) string
	tableHeader(tableTitle string) string
	tableHeaderRow(args ...string) string
	tableRow(args ...string) string
	tableFooter() string
	colorSpan(content, foregroundColor, backgroundColor string) string
}

func GenerateMarkup(parser *parser.Parser, markup Markup, outputSpec *string, defaultFileExtension string, tableContents bool, models bool) error {
	var filename string
	if *outputSpec == "" {
		filename = path.Join("./", "API") + defaultFileExtension
	} else {
		filename = path.Join(*outputSpec)
	}
	fd, err := os.Create(filename)
	if err != nil {
		return fmt.Errorf("Can not create document file: %v\n", err)
	}
	defer fd.Close()

	var buf bytes.Buffer

	/***************************************************************
	* Overall API
	***************************************************************/
	buf.WriteString(markup.sectionHeader(1, parser.Listing.Infos.Title))
	buf.WriteString(fmt.Sprintf("%s\n\n", parser.Listing.Infos.Description))

	/***************************************************************
	* Table of Contents (List of Sub-APIs)
	***************************************************************/
	if tableContents {
		buf.WriteString("Table of Contents\n\n")
		subApiKeys, subApiKeyIndex := alphabeticalKeysOfSubApis(parser.Listing.Apis)
		for _, subApiKey := range subApiKeys {
			buf.WriteString(markup.numberedItem(1, markup.link(subApiKey, parser.Listing.Apis[subApiKeyIndex[subApiKey]].Description)))
		}
		buf.WriteString("\n")
	}

	for _, apiKey := range alphabeticalKeysOfApiDeclaration(parser.TopLevelApis) {

		apiDescription := parser.TopLevelApis[apiKey]
		/***************************************************************
		* Sub-API Specifications
		***************************************************************/
		if tableContents {
			buf.WriteString(markup.anchor(apiKey))
		}
		buf.WriteString(markup.sectionHeader(2, markup.colorSpan(apiKey, color_API_SECTION_HEADER_TEXT, color_NORMAL_BACKGROUND)))

		buf.WriteString(markup.tableHeader(""))
		buf.WriteString(markup.tableHeaderRow("Specification", "Value"))
		buf.WriteString(markup.tableRow("Resource Path", apiDescription.ResourcePath))
		buf.WriteString(markup.tableRow("API Version", apiDescription.ApiVersion))
		buf.WriteString(markup.tableRow("BasePath for the API", apiDescription.BasePath))
		buf.WriteString(markup.tableRow("Consumes", strings.Join(apiDescription.Consumes, ", ")))
		buf.WriteString(markup.tableRow("Produces", strings.Join(apiDescription.Produces, ", ")))
		buf.WriteString(markup.tableFooter())

		/***************************************************************
		* Sub-API Operations (Summary)
		***************************************************************/
		buf.WriteString("\n")
		buf.WriteString(markup.sectionHeader(3, "Operations"))
		buf.WriteString("\n")

		buf.WriteString(markup.tableHeader(""))
		buf.WriteString(markup.tableHeaderRow("Resource Path", "Operation", "Description"))
		for _, subapi := range apiDescription.Apis {
			for _, op := range subapi.Operations {
				pathString := strings.Replace(strings.Replace(subapi.Path, "{", "\\{", -1), "}", "\\}", -1)
				buf.WriteString(markup.tableRow(pathString, markup.link(op.Nickname, op.HttpMethod), op.Summary))
			}
		}
		buf.WriteString(markup.tableFooter())
		buf.WriteString("\n")

		/***************************************************************
		* Sub-API Operations (Details)
		***************************************************************/
		for _, subapi := range apiDescription.Apis {
			for _, op := range subapi.Operations {
				buf.WriteString("\n")
				operationString := fmt.Sprintf("%s (%s)", strings.Replace(strings.Replace(subapi.Path, "{", "\\{", -1), "}", "\\}", -1), op.HttpMethod)
				if tableContents {
					buf.WriteString(markup.anchor(op.Nickname))
				}
				buf.WriteString(markup.sectionHeader(4, markup.colorSpan("API: "+operationString, color_NORMAL_TEXT, operationColor(op.HttpMethod))))
				buf.WriteString("\n\n" + op.Summary + "\n\n\n")

				if len(op.Parameters) > 0 {
					buf.WriteString(markup.tableHeader(""))
					buf.WriteString(markup.tableHeaderRow("Param Name", "Param Type", "Data Type", "Description", "Required?"))
					for _, param := range op.Parameters {
						isRequired := ""
						if param.Required {
							isRequired = "Yes"
						}
						buf.WriteString(markup.tableRow(param.Name, param.ParamType, modelText(markup, param.DataType), param.Description, isRequired))
					}
					buf.WriteString(markup.tableFooter())
				}

				if len(op.ResponseMessages) > 0 {
					buf.WriteString(markup.tableHeader(""))
					buf.WriteString(markup.tableHeaderRow("Code", "Type", "Model", "Message"))
					for _, msg := range op.ResponseMessages {
						buf.WriteString(markup.tableRow(fmt.Sprintf("%v", msg.Code), msg.ResponseType, modelText(markup, msg.ResponseModel), msg.Message))
					}
					buf.WriteString(markup.tableFooter())
				}
			}
		}
		buf.WriteString("\n")

		/***************************************************************
		* Models
		***************************************************************/
		if len(apiDescription.Models) > 0 && models {
			buf.WriteString("\n")
			buf.WriteString(markup.sectionHeader(3, "Models"))
			buf.WriteString("\n")
			for _, modelKey := range alphabeticalKeysOfModels(apiDescription.Models) {
				model := apiDescription.Models[modelKey]
				if tableContents {
					buf.WriteString(markup.anchor(modelKey))
				}
				buf.WriteString(markup.sectionHeader(4, markup.colorSpan(shortModelName(modelKey), color_MODEL_TEXT, color_NORMAL_BACKGROUND)))
				buf.WriteString(markup.tableHeader(""))
				buf.WriteString(markup.tableHeaderRow("Field Name (alphabetical)", "Field Type", "Description"))
				for _, fieldName := range alphabeticalKeysOfFields(model.Properties) {
					fieldProps := model.Properties[fieldName]
					buf.WriteString(markup.tableRow(fieldName, fieldProps.Type, fieldProps.Description))
				}
				buf.WriteString(markup.tableFooter())
			}
			buf.WriteString("\n")
		}
	}

	fd.WriteString(buf.String())

	return nil
}

func shortModelName(longModelName string) string {
	parts := strings.Split(longModelName, ".")
	return parts[len(parts)-1]
}

func modelText(markup Markup, fullyQualifiedModelName string) string {
	shortName := shortModelName(fullyQualifiedModelName)
	result := shortName
	if fullyQualifiedModelName != shortName {
		result = markup.link(fullyQualifiedModelName, shortName)
	}
	return result
}

func alphabeticalKeysOfSubApis(refs []*parser.ApiRef) ([]string, map[string]int) {
	index := map[string]int{}
	keys := make([]string, len(refs))
	for i, ref := range refs {
		subApiKey := ref.Path[1:]
		keys[i] = subApiKey
		index[subApiKey] = i
	}
	sort.Strings(keys)
	return keys, index
}
func alphabeticalKeysOfApiDeclaration(m map[string]*parser.ApiDeclaration) []string {
	keys := make([]string, len(m))
	i := 0
	for key, _ := range m {
		keys[i] = key
		i++
	}
	sort.Strings(keys)
	return keys
}
func alphabeticalKeysOfModels(m map[string]*parser.Model) []string {
	keys := make([]string, len(m))
	i := 0
	for key, _ := range m {
		keys[i] = key
		i++
	}
	sort.Strings(keys)
	return keys
}
func alphabeticalKeysOfFields(m map[string]*parser.ModelProperty) []string {
	keys := make([]string, len(m))
	i := 0
	for key, _ := range m {
		keys[i] = key
		i++
	}
	sort.Strings(keys)
	return keys
}

func operationColor(methodName string) string {
	switch methodName {
	case "GET":
		return color_GET
	case "POST":
		return color_POST
	case "PUT":
		return color_PUT
	case "DELETE":
		return color_DELETE
	case "PATCH":
		return color_PATCH
	default:
		return color_DEFAULT
	}
}

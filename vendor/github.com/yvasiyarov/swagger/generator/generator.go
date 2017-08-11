package generator

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"go/ast"
	"log"
	"os"
	"path"
	"regexp"
	"runtime"
	"strings"

	"github.com/yvasiyarov/swagger/markup"
	"github.com/yvasiyarov/swagger/parser"
)

const (
	AVAILABLE_FORMATS = "go|gopkg|swagger|asciidoc|markdown|confluence"
)

var generatedFileTemplate = `
package main
//This file is generated automatically. Do not try to edit it manually.

var resourceListingJson = {{resourceListing}}
var apiDescriptionsJson = {{apiDescriptions}}
`

var generatedPkgTemplate = `
package {{packageName}}
//This file is generated automatically. Do not try to edit it manually.

var ResourceListingJson = {{resourceListing}}
var ApiDescriptionsJson = {{apiDescriptions}}
`

// It must return true if funcDeclaration is controller. We will try to parse only comments before controllers
func IsController(funcDeclaration *ast.FuncDecl, controllerClass string) bool {
	if len(controllerClass) == 0 {
		// Search every method
		return true
	}
	if funcDeclaration.Recv != nil && len(funcDeclaration.Recv.List) > 0 {
		if starExpression, ok := funcDeclaration.Recv.List[0].Type.(*ast.StarExpr); ok {
			receiverName := fmt.Sprint(starExpression.X)
			matched, err := regexp.MatchString(string(controllerClass), receiverName)
			if err != nil {
				log.Fatalf("The -controllerClass argument is not a valid regular expression: %v\n", err)
			}
			return matched
		}
	}
	return false
}

func generateSwaggerDocs(parser *parser.Parser, outputSpec string, pkg bool) error {
	fd, err := os.Create(path.Join(outputSpec, "docs.go"))
	if err != nil {
		return fmt.Errorf("Can not create document file: %v\n", err)
	}
	defer fd.Close()

	var apiDescriptions bytes.Buffer
	for apiKey, apiDescription := range parser.TopLevelApis {
		apiDescriptions.WriteString("\"" + apiKey + "\":")

		apiDescriptions.WriteString("`")
		json, err := json.MarshalIndent(apiDescription, "", "    ")
		if err != nil {
			return fmt.Errorf("Can not serialise []ApiDescription to JSON: %v\n", err)
		}
		apiDescriptions.Write(json)
		apiDescriptions.WriteString("`,")
	}

	var doc string
	if pkg {
		doc = strings.Replace(generatedPkgTemplate, "{{resourceListing}}", "`"+string(parser.GetResourceListingJson())+"`", -1)
		doc = strings.Replace(doc, "{{apiDescriptions}}", "map[string]string{"+apiDescriptions.String()+"}", -1)
		packageName := strings.Split(outputSpec, "/")
		doc = strings.Replace(doc, "{{packageName}}", packageName[len(packageName)-1], -1)
	} else {
		doc = strings.Replace(generatedFileTemplate, "{{resourceListing}}", "`"+string(parser.GetResourceListingJson())+"`", -1)
		doc = strings.Replace(doc, "{{apiDescriptions}}", "map[string]string{"+apiDescriptions.String()+"}", -1)
	}

	fd.WriteString(doc)

	return nil
}

func generateSwaggerUiFiles(parser *parser.Parser, outputSpec string) error {
	fd, err := os.Create(path.Join(outputSpec, "index.json"))
	if err != nil {
		return fmt.Errorf("Can not create the master index.json file: %v\n", err)
	}
	defer fd.Close()
	fd.WriteString(string(parser.GetResourceListingJson()))

	for apiKey, apiDescription := range parser.TopLevelApis {
		err = os.MkdirAll(path.Join(outputSpec, apiKey), 0777)
		if err != nil {
			return err
		}

		fd, err = os.Create(path.Join(outputSpec, apiKey, "index.json"))
		if err != nil {
			return fmt.Errorf("Can not create the %s/index.json file: %v\n", apiKey, err)
		}
		defer fd.Close()

		json, err := json.MarshalIndent(apiDescription, "", "    ")
		if err != nil {
			return fmt.Errorf("Can not serialise []ApiDescription to JSON: %v\n", err)
		}

		fd.Write(json)
		log.Printf("Wrote %v/index.json", apiKey)
	}

	return nil
}

func InitParser(controllerClass, ignore string) *parser.Parser {
	parser := parser.NewParser()

	parser.ControllerClass = controllerClass
	parser.IsController = IsController
	parser.Ignore = ignore

	parser.TypesImplementingMarshalInterface["NullString"] = "string"
	parser.TypesImplementingMarshalInterface["NullInt64"] = "int"
	parser.TypesImplementingMarshalInterface["NullFloat64"] = "float"
	parser.TypesImplementingMarshalInterface["NullBool"] = "bool"

	return parser
}

type Params struct {
	ApiPackage, MainApiFile, OutputFormat, OutputSpec, ControllerClass, Ignore, VendoringPath string
	ContentsTable, Models                                                      bool
}

func Run(params Params) error {
	parser := InitParser(params.ControllerClass, params.Ignore)
	gopath := os.Getenv("GOPATH")
	if gopath == "" {
		return errors.New("Please, set $GOPATH environment variable\n")
	}

	log.Println("Start parsing")

	//Support gopaths with multiple directories
	dirs := strings.Split(gopath, ":")
	if runtime.GOOS == "windows" {
		dirs = strings.Split(gopath, ";")
	}
	found := false
	for _, d := range dirs {
		apifile := path.Join(d, "src", params.MainApiFile)
		if _, err := os.Stat(apifile); err == nil {
			parser.ParseGeneralApiInfo(apifile)
			found = true
			break // file found, exit the loop
		}
	}
	if found == false {
		if _, err := os.Stat(params.MainApiFile); err == nil {
			parser.ParseGeneralApiInfo(params.MainApiFile)
		} else {
			apifile := path.Join(gopath, "src", params.MainApiFile)
			return fmt.Errorf("Could not find apifile %s to parse\n", apifile)
		}
	}

	parser.ParseApi(params.ApiPackage, params.VendoringPath)
	log.Println("Finish parsing")

	var err error
	confirmMsg := ""
	format := strings.ToLower(params.OutputFormat)
	switch format {
	case "go":
		err = generateSwaggerDocs(parser, params.OutputSpec, false)
		confirmMsg = "Doc file generated"
	case "gopkg":
		err = generateSwaggerDocs(parser, params.OutputSpec, true)
		confirmMsg = "Doc package generated"
	case "asciidoc":
		err = markup.GenerateMarkup(parser, new(markup.MarkupAsciiDoc), &params.OutputSpec, ".adoc", params.ContentsTable, params.Models)
		confirmMsg = "AsciiDoc file generated"
	case "markdown":
		err = markup.GenerateMarkup(parser, new(markup.MarkupMarkDown), &params.OutputSpec, ".md", params.ContentsTable, params.Models)
		confirmMsg = "MarkDown file generated"
	case "confluence":
		err = markup.GenerateMarkup(parser, new(markup.MarkupConfluence), &params.OutputSpec, ".confluence", params.ContentsTable, params.Models)
		confirmMsg = "Confluence file generated"
	case "swagger":
		err = generateSwaggerUiFiles(parser, params.OutputSpec)
		confirmMsg = "Swagger UI files generated"
	default:
		err = fmt.Errorf("Invalid -format specified. Must be one of %v.", AVAILABLE_FORMATS)
	}

	if err != nil {
		return err
	}
	log.Println(confirmMsg)

	return nil
}

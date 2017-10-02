package main

import (
	"log"
	"github.com/codegangsta/cli"
	"strings"
	"fmt"
	"encoding/json"
	"regexp"
)

/**
    The go:generate tag is used to generate a binary go file that
    contains all data from the sample-events folder, which is used
    by this file to generate commands for generate-event. If any changes
    are made to the sample-events folder, the binary file will need to be
    re-generated via running
        'go generate'
    in the project root folder. This command requires go-bindata, which can be
    installed by running
        'go get -u github.com/jteeuwen/go-bindata/...'
 */
// ***DO NOT EDIT THE FOLLOWING COMMENT***
//go:generate go-bindata -o generated-event-binary.go sample-events/...

var nameToCommandMap map[string]string = make(map[string]string)
var nameToDescriptionMap map[string]string = make(map[string]string)
var nameToFlagListMap map[string][]Flag = make(map[string][]Flag)

type CommandMap struct {
	Commands []Command
}

type Command struct {
	Name        string `json:"name"`
	Command     string `json:"command"`
	Description string `json:"description"`
	Flags       []Flag `json:"flags"`
}

type Flag struct {
	Name    string `json:"name"`
	Usage   string `json:"usage"`
	Value   string `json:"value"`
}

// Generates top-level commands for generate-event for all
// categories under sample-events
func generateEventCategories() (categories []cli.Command) {
	mapFileToCommands()

	dirs, err := AssetDir("sample-events")
	if err != nil {
		log.Fatal(err)
	}

	for _, dir := range dirs {
		if (strings.Contains(dir, ".")) {
			// Skip names that are not directories
			continue
		}
		command := cli.Command{
			Name:  strings.Replace(strings.ToLower(dir), " ", "-", -1),
			Usage: "View available events for " + dir + "",
			Subcommands: generateCategorySubCommands(dir),
		}

		categories = append(categories, command)
	}

	return
}

func generateCategorySubCommands(subDir string) (subcommands []cli.Command){
	path := "sample-events/" + subDir
	files, err := AssetDir(path)
	if err != nil {
		log.Fatal(err)
	}

	for _, file := range files {
		name := strings.Split(file, ".")[0]

		command := cli.Command{
			Name:  nameToCommandMap[name],
			Usage: "Generates a sample " + nameToDescriptionMap[name] + " event",
			Flags: generateCommandFlags(name),
			Action: func(c *cli.Context) {
				b, err := Asset(path + "/" + name + ".json") // just pass the file name
				if err != nil {
					fmt.Print(err)
				}

				str := string(b) // convert content to a 'string'

				// parse flags
				str = parseFlags(c, str, name)

				fmt.Println(str)
			},
		}

		subcommands = append(subcommands, command)
	}
	return
}

func parseFlags(c *cli.Context, input string, command string) (result string) {
	result = input

	for _, f := range nameToFlagListMap[command] {
		flag := strings.Split(f.Name, ",")[0]
		expr := `\{\{\.` + flag + `\}\}`
		regex, err := regexp.Compile(expr)

		if err != nil {
			log.Fatal(err)
		}

		if c.String(flag) == "" {
			result = regex.ReplaceAllString(result, f.Value)
		} else {
			result = regex.ReplaceAllString(result, c.String(flag))
		}
	}

	return
}

func generateCommandFlags(command string) (flags []cli.Flag) {
	for _, f := range nameToFlagListMap[command] {
		flag := cli.StringFlag{
			Name: f.Name,
			Usage: f.Usage,
			Value: f.Value,
		}
		flags = append(flags, flag)
	}

	return
}

func mapFileToCommands() {
	data, err := Asset("sample-events/event-mapping.json")
	if err != nil {
		panic(err)
	}

	response := CommandMap{}
	json.Unmarshal(data, &response)


	for _, command := range response.Commands {
		nameToCommandMap[command.Name] = command.Command
		nameToDescriptionMap[command.Name] = command.Description
		nameToFlagListMap[command.Name] = command.Flags
	}
}

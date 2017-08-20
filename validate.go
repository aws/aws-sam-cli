package main

import (
	"fmt"
	"os"

	"github.com/awslabs/goformation"
	"github.com/codegangsta/cli"
)

func validate(c *cli.Context) {

	_, err := goformation.Open(getTemplateFilename(c.String("template")))

	if err != nil {
		fmt.Fprintf(os.Stderr, "%s\n", err)
		os.Exit(1)
	}

	fmt.Fprintf(os.Stderr, "Valid!\n")
	os.Exit(0)

}

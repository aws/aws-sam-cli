package main

import (
	"fmt"
	"os"

	"github.com/awslabs/goformation"
	"github.com/codegangsta/cli"
)

func validate(c *cli.Context) {

	_, _, errs := goformation.Open(c.String("template"))

	if len(errs) > 0 {
		for _, err := range errs {
			fmt.Fprintf(os.Stderr, "%s\n", err)
		}
		os.Exit(1)
	}

	fmt.Fprintf(os.Stderr, "Valid!\n")
	os.Exit(0)

}

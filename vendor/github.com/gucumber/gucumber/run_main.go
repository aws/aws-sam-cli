package gucumber

import (
	"flag"
	"fmt"
)

type filters []string

func (f *filters) String() string {
	return fmt.Sprint(*f)
}

func (f *filters) Set(value string) error {
	*f = append(*f, value)
	return nil
}

var filterFlag filters
var goBuildTags string

func init() {
	flag.Var(&filterFlag, "tags", "comma-separated list of tags to filter scenarios by")
	flag.StringVar(&goBuildTags, "go-tags", "", "space seperated list of tags, wrap in quotes to specify multiple tags")
}

func RunMain() {
	flag.Parse()

	var dir string
	if flag.NArg() == 0 {
		dir = "internal/features"
	} else {
		dir = flag.Arg(0)
	}

	filt := []string{}
	for _, f := range filterFlag {
		filt = append(filt, string(f))
	}
	if err := BuildAndRunDirWithGoBuildTags(dir, filt, goBuildTags); err != nil {
		panic(err)
	}
}

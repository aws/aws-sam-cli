package main

import (
	"io"
	"log"
	"os"
	"os/exec"
)

func deploy() {

	args := []string{"cloudformation", "deploy"}
	for _, arg := range os.Args[2:] {
		args = append(args, arg)
	}

	cmd := exec.Command("aws", args...)

	stderr, err := cmd.StderrPipe()
	if err != nil {
		log.Fatal(err)
	}

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		log.Fatal(err)
	}

	if err := cmd.Start(); err != nil {
		log.Fatal(err)
	}

	go io.Copy(os.Stderr, stderr)
	go io.Copy(os.Stdout, stdout)

	cmd.Wait()

}

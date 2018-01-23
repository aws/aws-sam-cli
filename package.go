package main

import (
	"io"
	"log"
	"os"
	"os/exec"
)

func pkg() {

	args := []string{"cloudformation", "package"}
	args = append(args, os.Args[2:]...)

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

	if err := cmd.Wait(); err != nil {
		os.Exit(1)
	}
}

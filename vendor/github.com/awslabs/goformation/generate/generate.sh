#!/bin/bash

# Quit on any errors
set -e

# Build the generator
GENERATOR=$(mktemp)
go build -o $GENERATOR ./generate

# Run the generator
$GENERATOR

# Remove it afterwards
rm $GENERATOR

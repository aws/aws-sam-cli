#!/usr/bin/env bash

HOME="$(getent passwd "${USER}" | cut -d: -f6)"

exec "${@}"

#!/bin/sh

GPG="$1"
shift

$GPG "$@"
exitCode=$?

sleep 1
exit $exitCode

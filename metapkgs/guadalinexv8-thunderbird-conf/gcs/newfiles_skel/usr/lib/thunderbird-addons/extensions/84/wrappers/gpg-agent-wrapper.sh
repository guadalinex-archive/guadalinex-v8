#!/bin/sh

action=$1
shift

if [ $action = "start" ]; then
  GPGAGENT="$1"
  shift
  exec "$GPGAGENT" "$@"
fi

if [ $action = "stop" ]; then
  kill $1
fi

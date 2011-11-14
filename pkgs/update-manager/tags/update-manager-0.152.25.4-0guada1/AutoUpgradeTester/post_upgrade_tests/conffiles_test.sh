#!/bin/sh

set -e

find /etc -name "*.dpkg-dist" -exec cp '{}' /tmp \;

# check if we have a dpkg-dist file
if ls /tmp/*.dpkg-dist 2>/dev/null; then
   exit 1
fi

exit 0
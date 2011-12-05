#!/bin/bash

logs=/target/var/log/installer/debug

exec >> $logs 2>&1

function error() {
	echo "Error: $*"
}

rm -rf /etc/apt/sources.list*
cp -v /etc/apt/sources.list /target/etc/apt/sources.list || error "copying sources.list"


# detecting if our processor has pae ability
cat /proc/cpuinfo | grep -q pae

# if it has
if [ $? -eq 0 ]
then
	chroot /target apt-get install --assume-yes --force-yes linux-image-pae
fi

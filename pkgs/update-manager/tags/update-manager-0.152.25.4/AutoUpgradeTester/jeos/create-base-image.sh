#!/bin/sh

set -e

DIST=$(lsb_release -c -s)

if [ -z "$1" ]; then
    echo "need distro codename to create as first argument "
    exit 1
fi

# check depends
if [ ! -f /usr/bin/ubuntu-vm-builder ]; then
    apt-get install -y ubuntu-vm-builder
fi

if [ ! -f /usr/bin/kvm ]; then
    apt-get install -y kvm
fi

# create a default ssh key
if [ ! -e ssh-key ]; then
    ssh-keygen -N '' -f ssh-key
fi

KERNEL=generic
if [ "$1" = "dapper" ]; then
	KERNEL=386
fi

# create the image
ubuntu-vm-builder kvm $1 --kernel-flavour $KERNEL --ssh-key $(pwd)/ssh-key.pub \
    --components main,restricted --rootsize 80000 --arch i386 --dest ubuntu-$1

# move into place
mv ubuntu-$1/*.qcow2 $1-i386.qcow2

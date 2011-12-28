#!/bin/bash

logs=/target/var/log/installer/debug

exec >> $logs 2>&1

function error() {
        echo "Error: $*"
}

cp -v /usr/share/guadalinex-system-conf/apt-archives/sources.list /target/etc/apt/sources.list || error "copying sources.list"

rm -f /target/etc/apt/sources.list.d/*


# detecting if our processor has pae ability
cat /proc/cpuinfo | grep -q pae

# if it has
if [ $? -eq 0 ]
then
        chroot /target apt-get install --assume-yes --force-yes linux-image-pae
fi

# set default-display-manager to gdm
#echo '/usr/sbin/gdm' > /etc/X11/default-display-manager


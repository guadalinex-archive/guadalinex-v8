#!/bin/sh

# check for required base-installer dir (this will be get automatically
# from the build-tarball script)
if [ ! -d ./base-installer ]; then
	echo "required directory "base-installer" missing"
	echo "get it with:"
        echo "bzr co --lightweight lp:~ubuntu-core-dev/base-installer/ubuntu base-installer"
	exit 1
fi

# setup vars
ARCH=$(dpkg --print-architecture)
CPUINFO=/proc/cpuinfo
MACHINE=$(uname -m)
KERNEL_MAJOR=2.6

# source arch
. base-installer/kernel/$ARCH.sh

# get flavour
FLAVOUR=$(arch_get_kernel_flavour)

# get kernel for flavour
KERNELS=$(arch_get_kernel $FLAVOUR)

for kernel in $KERNELS; do
	echo $kernel
done

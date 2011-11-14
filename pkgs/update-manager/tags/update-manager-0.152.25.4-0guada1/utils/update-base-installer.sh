#!/bin/sh
#
# Include the latest base-installer version into the DistUpgrader/
# directory (this is used for the kernel selection)
#

set -e

DIST="$(lsb_release -c -s)"
BASEDIR=./apt

APT_OPTS="\
   -o Dir::State=./apt                \
   -o Dir::Cache=./apt                \
   -o Dir::Etc=./apt                  \
   -o Dir::State::Status=./apt/status \
"

# cleanup base-installer first
rm -rf base-installer*

# create dirs
if [ ! -d $BASEDIR/archives/partial ]; then
    mkdir -p $BASEDIR/archives/partial
fi

# put right sources.list in
echo "deb-src http://archive.ubuntu.com/ubuntu $DIST main" > $BASEDIR/sources.list

# run apt-get update
apt-get $APT_OPTS update 

# get the latest base-installer
apt-get $APT_OPTS source base-installer

# move kernel/ lib into place
mkdir -p ../DistUpgrade/base-installer
mv base-installer-*/kernel ../DistUpgrade/base-installer/
# get changelog subset
head -n 500 base-installer-*/debian/changelog > ../DistUpgrade/base-installer/VERSION

# cleanup
rm -rf base-installer-* base-installer_*

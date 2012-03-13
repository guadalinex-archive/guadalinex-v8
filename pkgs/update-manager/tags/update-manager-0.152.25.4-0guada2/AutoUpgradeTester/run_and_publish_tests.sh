#!/bin/sh

# -------------------------------------------------------------- config
# link to the ssh key to publish the results
SSHKEY="-oIdentityFile=link-to-ssh-key"
PUBLISH="mvo@people.ubuntu.com"
#PUBLISH=""

RESULTDIR=/var/cache/auto-upgrade-tester/result/

# output
DATE=$(date +"%F-%T")
HTML_BASEDIR=~/public_html/automatic-upgrade-testing
HTMLDIR=$HTML_BASEDIR/$DATE

PROFILES="server server-tasks ubuntu kubuntu main-all"
#PROFILES="lts-server server"
#PROFILES="server"

UPGRADE_TESTER_ARGS="--quiet --html-output-dir $HTMLDIR"
#UPGRADE_TESTER_ARGS="$UPGRADE_TESTER_ARGS -b UpgradeTestBackendSimulate "
#UPGRADE_TESTER_ARGS="$UPGRADE_TESTER_ARGS --tests-only"

upload_files() {
    profile=$1
    SSHKEY=$2
    PUBLISH=$3
    DATE=$4
    cat > sftp-upload <<EOF
cd public_html
cd automatic-upgrade-testing
-mkdir $DATE
cd $DATE
-mkdir $profile
cd $profile
put /var/cache/auto-upgrade-tester/result/$profile/*
chmod 644 *
EOF
    sftp $SSHKEY -b sftp-upload $PUBLISH >/dev/null
}

upload_index_html() {
    SSHKEY=$1
    PUBLISH=$2
    DATE=$3
    # upload index
    cat > sftp-upload <<EOF
cd public_html
cd automatic-upgrade-testing
cd $DATE
put index.html
EOF
    sftp $SSHKEY -b sftp-upload $PUBLISH >/dev/null
}

update_current_symlink() {
    SSHKEY=$1
    PUBLISH=$2
    cat > sftp-upload <<EOF
cd public_html
cd automatic-upgrade-testing
-rm current
symlink $DATE current
EOF
    sftp $SSHKEY -b sftp-upload $PUBLISH >/dev/null
}

# ------------------------------------------------------------- main()

bzr up

FAIL=""

PROFILES_ARG=""
for p in $PROFILES; do
    # clear log dir first
    rm -f $RESULTDIR/$p/*
    # do it
    PROFILES_ARG=" $PROFILES_ARG profile/$p"
done

# run with the profiles we have
./auto-upgrade-tester $UPGRADE_TESTER_ARGS $PROFILES_ARG

# update current symlink
rm -f $HTML_BASEDIR/current
ln -s $DATE $HTML_BASEDIR/current

# FIXME: portme
#upload_index_html $SSHKEY $PUBLISH $DATE
#update_current_symlink $SSHKEY $PUBLISH


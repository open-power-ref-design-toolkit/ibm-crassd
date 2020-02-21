#!/usr/bin/bash

### Generates the required rpms for the example docker file
##  Based on the openbmctool build script

# openbmctool rpm
START_DIR=$(pwd)
git clone https://github.com/openbmc/openbmc-tools.git

# openbmc will eventually have its buildscripts included in the repo, uncomment and replace the rest of this section when that happens
#cd openbmc-tools/thalerj/RPMbuildfiles
#chmod +x buildOpenbmctool.sh
#./buildOpenbmctool.sh
#cp /root/rpmbuild/RPMS/noarch/openbmctool-*.rpm ./

cd openbmc-tools/thalerj/build-scripts
echo "Openbmctool Version: ex 1.0"
read version
echo "Openbmctool Release: ex 4"
read release
OBMC_DIR=openbmctool-$version-$release
mkdir -p /tmp/$OBMC_DIR
rm -rf /tmp/$OBMC_DIR/*
cp -r ../* /tmp/$OBMC_DIR
tar -cvzf /root/rpmbuild/SOURCES/$OBMC_DIR.tgz -C /tmp $OBMC_DIR
rpmbuild -ba --define "_version $version" --define "_release $release" /tmp/$OBMC_DIR/build-scripts/openbmctool-rhel8.spec
cp /root/rpmbuild/RPMS/noarch/$OBMC_DIR.noarch.rpm $START_DIR/

# crassd rpm
cd $START_DIR
echo "ibm-crassd Version: ex 1.0"
read version
echo "ibm-crassd Release: ex 4"
read release

DIR_NAME=ibm-crassd-$version
mkdir -p /tmp/$DIR_NAME
rm -rf /tmp/$DIR_NAME/*
cp -r ../* /tmp/$DIR_NAME
tar -cvzf /root/rpmbuild/SOURCES/$DIR_NAME.tgz -C /tmp $DIR_NAME
rpmbuild -ba --define "_version $version" --define "_release $release" ../ibm-crassd.spec
cp /root/rpmbuild/RPMS/noarch/$DIR_NAME-$release.el*.noarch.rpm ./


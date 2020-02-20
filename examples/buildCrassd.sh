#!/usr/bin/bash

echo "Version: ex 1.0"
read version
echo "Release: ex 4"
read release

DIR_NAME=ibm-crassd-$version-$release
mkdir -p /tmp/$DIR_NAME
rm -rf /tmp/$DIR_NAME/*
cp -r ../* /tmp/$DIR_NAME
tar -cvzf /root/rpmbuild/SOURCES/$DIR_NAME.tgz -C /tmp $DIR_NAME
rpmbuild -ba --define "_version $version" --define "_release $release" ../ibm-crassd.spec
cp /root/rpmbuild/RPMS/noarch/$DIR_NAME.noarch.rpm ./


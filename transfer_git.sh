#!/bin/bash

set -e

if [ -z $DAALA_ROOT ]; then
  echo "Please set DAALA_ROOT to the location of your libvpx git clone"
  exit 1
fi

echo Testing server...
ssh -i $DAALA_ROOT/tools/daala.pem ec2-user@$1 -o StrictHostKeyChecking=no "echo Available"

echo Cleaning server...
ssh -i $DAALA_ROOT/tools/daala.pem ec2-user@$1 -o StrictHostKeyChecking=no "rm -rf *.png"

#echo Importing ssh keys...

#ssh-keyscan -H $1 >> ~/.ssh/known_hosts

branch=`git rev-parse --abbrev-ref HEAD`

echo Uploading local git repository...

rsync -r -e "ssh -i $DAALA_ROOT/tools/daala.pem -o StrictHostKeyChecking=no" $DAALA_ROOT/.git/ ec2-user@$1:/home/ec2-user/daala/.git/

echo Checking out branch $branch remotely...

ssh -i $DAALA_ROOT/tools/daala.pem ec2-user@$1 -o StrictHostKeyChecking=no "cd daala; git reset --hard; git checkout $branch" > /dev/null

echo Building...

ssh -i $DAALA_ROOT/tools/daala.pem ec2-user@$1 -o StrictHostKeyChecking=no "cd daala ; ./autogen.sh ; PKG_CONFIG_PATH=/usr/local/lib/pkgconfig ./configure --disable-player --enable-logging --enable-dump-images ; make -j4 ; make tools -j4" > /dev/null

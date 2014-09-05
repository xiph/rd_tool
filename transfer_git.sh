#!/bin/bash

set -e

SSH="ssh -i daala.pem -o StrictHostKeyChecking=no"


if [ -z $DAALA_ROOT ]; then
  echo "Please set DAALA_ROOT to the location of your libvpx git clone"
  exit 1
fi

echo Testing server...
$SSH ec2-user@$1 "echo Available"

echo "Checking for other users..."
if $SSH ec2-user@$1 "pgrep encoder"
then
  echo "The server is already running encoder_example processes."
  exit 1
fi

echo Cleaning server...
$SSH ec2-user@$1 "rm -rf *.png"

#echo Importing ssh keys...

#ssh-keyscan -H $1 >> ~/.ssh/known_hosts

branch=`git --git-dir $DAALA_ROOT/.git rev-parse --abbrev-ref HEAD`

echo Uploading tools...

rsync -r -e "$SSH" ./ ec2-user@$1:/home/ec2-user/rd_tool/

echo Uploading local git repository...

rsync -r -e "$SSH" $DAALA_ROOT/.git/ ec2-user@$1:/home/ec2-user/daala/.git/

echo Checking out branch $branch remotely...

$SSH ec2-user@$1 "cd daala; git reset --hard; git checkout $branch" > /dev/null

echo Building...

$SSH ec2-user@$1 "cd daala ; ./autogen.sh ; PKG_CONFIG_PATH=/usr/local/lib/pkgconfig ./configure --disable-player --disable-dump-images --enable-encoder-check --enable-logging --enable-dump-recons ; make -j16 ; make tools -j16" > /dev/null

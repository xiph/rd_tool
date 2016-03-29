#!/bin/bash

set -e

SSH="ssh -i daala.pem -o StrictHostKeyChecking=no"
export PATH=/sbin:/bin:/usr/sbin:/usr/bin

if [ -z "$3" ]; then
  export WORK_ROOT=/home/ec2-user
else
  export WORK_ROOT="$3"
fi

if [ -z $DAALA_ROOT ]; then
  echo "Please set DAALA_ROOT to the location of your libvpx git clone"
  exit 1
fi

if [ -z $2 ]; then
  echo "Please specify a codec"
  exit 1
fi

echo Testing server...
$SSH ec2-user@$1 "echo Available"

$SSH ec2-user@$1 "mkdir -p $WORK_ROOT"

echo Cleaning server...
$SSH ec2-user@$1 "rm -rf $WORK_ROOT/*.png"

#echo Importing ssh keys...

#ssh-keyscan -H $1 >> ~/.ssh/known_hosts

echo Uploading tools...

rsync -r -e "$SSH" ./ ec2-user@$1:$WORK_ROOT/rd_tool/

echo Uploading local build...

rsync -r -e "$SSH" ../$2/ ec2-user@$1:$WORK_ROOT/$2/

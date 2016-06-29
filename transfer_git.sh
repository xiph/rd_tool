#!/bin/bash

set -e

SSH="ssh -i daala.pem -o StrictHostKeyChecking=no -p $5"
export PATH=/sbin:/bin:/usr/sbin:/usr/bin

if [ -z $DAALA_ROOT ]; then
  echo "Please set DAALA_ROOT to the location of your libvpx git clone"
  exit 1
fi

if [ -z $2 ]; then
  echo "Please specify a codec"
  exit 1
fi

echo Testing server...
$SSH $3@$1 "echo Available"

echo "Checking for other users..."
if $SSH $3@$1 "pgrep encoder"
then
  echo "The server is already running encoder_example processes. Killing."
  $SSH $3@$1 "killall -9 encoder_example"
fi

echo Cleaning server...
$SSH $3@$1 "rm -rf $4/*.png"

#echo Importing ssh keys...

#ssh-keyscan -H $1 >> ~/.ssh/known_hosts

echo Uploading tools...

rsync -r -e "$SSH" ./ $3@$1:$4/rd_tool/

echo Uploading local build...

rsync -r -e "$SSH" ../$2/ $3@$1:$4/$2/

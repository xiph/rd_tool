#!/bin/bash

set -e

SSH="ssh -i daala.pem -o StrictHostKeyChecking=no"
export PATH=/sbin:/bin:/usr/sbin:/usr/bin

if [ -z "$3" ]; then
  export WORK_ROOT=/home/ec2-user
else
  export WORK_ROOT="$3"
fi

if [ -z $2 ]; then
  echo "Please specify a codec"
  exit 1
fi

$SSH ec2-user@$1 "mkdir -p $WORK_ROOT"

$SSH ec2-user@$1 "rm -rf $WORK_ROOT/*.png"

rsync -r -q -e "$SSH" ./ ec2-user@$1:$WORK_ROOT/rd_tool/

rsync -r -q -e "$SSH" ../$2/ ec2-user@$1:$WORK_ROOT/$2/

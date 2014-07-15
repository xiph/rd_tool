#!/bin/bash

set -e

if [ -z "$ENCODER_EXAMPLE" ]; then
  export ENCODER_EXAMPLE=$DAALA_ROOT/examples/encoder_example
fi

if [ -z "$DUMP_PSNR" ]; then
  export DUMP_PSNR=$DAALA_ROOT/tools/dump_psnr
fi

if [ -z "$DUMP_PSNRHVS" ]; then
  export DUMP_PSNRHVS=$DAALA_ROOT/tools/dump_psnrhvs
fi

if [ -z "$DUMP_SSIM" ]; then
  export DUMP_SSIM=$DAALA_ROOT/tools/dump_ssim
fi

if [ -z "$DUMP_FASTSSIM" ]; then
  export DUMP_FASTSSIM=$DAALA_ROOT/tools/dump_fastssim
fi

FILE=$1

BASENAME=$(basename $FILE)-$x
rm $BASENAME.out 2> /dev/null || true

WIDTH=$(head -1 $FILE | cut -d\  -f 2 | tr -d 'W')
HEIGHT=$(head -1 $FILE | cut -d\  -f 3 | tr -d 'H')

OD_LOG_MODULES='encoder:10' OD_DUMP_IMAGES_SUFFIX=$BASENAME $ENCODER_EXAMPLE -k 256 -v $x $FILE -o $BASENAME.ogv 2> $BASENAME-enc.out
  SIZE=$(stat -c %s $BASENAME.ogv)
  $DUMP_PSNR $FILE 00000000out-$BASENAME.y4m > $BASENAME-psnr.out 2> /dev/null
  FRAMES=$(cat $BASENAME-psnr.out | grep ^0 | wc -l)
  PIXELS=$(($WIDTH*$HEIGHT*$FRAMES))
  PSNR=$(cat $BASENAME-psnr.out | grep Total)
  PSNRHVS=$($DUMP_PSNRHVS $FILE 00000000out-$BASENAME.y4m 2> /dev/null | grep Total)
  SSIM=$($DUMP_SSIM $FILE 00000000out-$BASENAME.y4m 2> /dev/null | grep Total)
  FASTSSIM=$($DUMP_FASTSSIM -c $FILE 00000000out-$BASENAME.y4m 2> /dev/null | grep Total)
  rm 00000000out-$BASENAME.y4m $BASENAME.ogv $BASENAME-enc.out $BASENAME-psnr.out
  echo $x $PIXELS $SIZE
  echo $PSNR
  echo $PSNRHVS
  echo $SSIM
  echo $FASTSSIM


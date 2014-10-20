#!/bin/bash

set -e

export X264=/home/ec2-user/x264/x264
export X265=/home/ec2-user/x265/build/linux/x265
export VPXENC=/home/ec2-user/libvpx/vpxenc
export VPXDEC=/home/ec2-user/libvpx/vpxdec
export YUV2YUV4MPEG=$DAALA_ROOT/tools/yuv2yuv4mpeg

if [ -z "$ENCODER_EXAMPLE" ]; then
  export ENCODER_EXAMPLE="$DAALA_ROOT/examples/encoder_example"
fi

if [ -z "$DUMP_PSNR" ]; then
  export DUMP_PSNR="$DAALA_ROOT/tools/dump_psnr"
fi

if [ -z "$DUMP_PSNRHVS" ]; then
  export DUMP_PSNRHVS="$DAALA_ROOT/tools/dump_psnrhvs"
fi

if [ -z "$DUMP_SSIM" ]; then
  export DUMP_SSIM="$DAALA_ROOT/tools/dump_ssim"
fi

if [ -z "$DUMP_FASTSSIM" ]; then
  export DUMP_FASTSSIM="$DAALA_ROOT/tools/dump_fastssim"
fi

if [ -z "$CODEC" ]; then
  export CODEC=daala
fi

FILE=$1

BASENAME="$(basename $FILE)-$x"
rm "$BASENAME.out" 2> /dev/null || true

WIDTH="$(head -1 $FILE | cut -d\  -f 2 | tr -d 'W')"
HEIGHT="$(head -1 $FILE | cut -d\  -f 3 | tr -d 'H')"

case $CODEC in
daala)
  OD_LOG_MODULES='encoder:10' OD_DUMP_IMAGES_SUFFIX="$BASENAME" "$ENCODER_EXAMPLE" -k 256 -v "$x" "$FILE" -o "$BASENAME.ogv" 2> "$BASENAME-enc.out"
  if [ ! -f "$BASENAME.ogv" ]
  then
    echo Failed to produce "$BASENAME.ogv"
    exit 1
  fi
  SIZE=$(stat -c %s "$BASENAME.ogv")
  mv "00000000out-$BASENAME.y4m" "$BASENAME.y4m"
  ;;
x264)
  QSTR="--preset placebo --min-keyint 256 --keyint 256 --no-scenecut --crf=\$x"
  $X264 --dump-yuv $BASENAME.yuv $(echo $QSTR | sed 's/\$x/'$x'/g') -o $BASENAME.x264 $FILE 2> $BASENAME-enc.out > /dev/null
  $YUV2YUV4MPEG $BASENAME -w$WIDTH -h$HEIGHT -an0 -ad0 -c420mpeg2
  SIZE=$(stat -c %s $BASENAME.x264)
  ;;
x265)
  QSTR="--preset slow --threads 1 --min-keyint 256 --keyint 256 --no-scenecut --crf=\$x"
  $X265 -r $BASENAME.y4m $(echo $QSTR | sed 's/\$x/'$x'/g') -o $BASENAME.x265 $FILE 2> $BASENAME-enc.out > /dev/null
  SIZE=$(stat -c %s $BASENAME.x265)
  ;;
x265-rt)
  QSTR="--preset slow --tune zerolatency --threads 1 --min-keyint 256 --keyint 256 --no-scenecut --crf=\$x"
  $X265 -r $BASENAME.y4m $(echo $QSTR | sed 's/\$x/'$x'/g') -o $BASENAME.x265 $FILE 2> $BASENAME-enc.out > /dev/null
  SIZE=$(stat -c %s $BASENAME.x265)
  ;;
vp8)
  QSTR="--target-bitrate=100M --cq-level=\$x"
  $VPXENC --codec=$CODEC --best --cpu-used=0 --kf-min-dist=256 --kf-max-dist=256 $(echo $QSTR | sed 's/\$x/'$x'/g') -o $BASENAME.vpx $FILE 2> $BASENAME-enc.out
  $VPXDEC --codec=$CODEC -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
vp9)
  QSTR="--target-bitrate=100M --cq-level=\$x"
  $VPXENC --codec=$CODEC --best --end-usage=q --cpu-used=0 --kf-min-dist=256 --kf-max-dist=256 $(echo $QSTR | sed 's/\$x/'$x'/g') -o $BASENAME.vpx $FILE 2> $BASENAME-enc.out
  $VPXDEC --codec=$CODEC -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
esac
  "$DUMP_PSNR" "$FILE" "$BASENAME.y4m" > "$BASENAME-psnr.out" 2> /dev/null
  FRAMES=$(cat "$BASENAME-psnr.out" | grep ^0 | wc -l)
  PIXELS=$(($WIDTH*$HEIGHT*$FRAMES))
  PSNR=$(cat "$BASENAME-psnr.out" | grep Total)
  PSNRHVS=$("$DUMP_PSNRHVS" "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)
  SSIM=$("$DUMP_SSIM" "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)
  FASTSSIM=$("$DUMP_FASTSSIM" -c "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)
  rm -f "$BASENAME.y4m" "$BASENAME.ogv" "$BASENAME.x264" "$BASENAME.x265" "$BASENAME.vpx" "$BASENAME-enc.out" "$BASENAME-psnr.out" 2> /dev/null
  echo "$x" "$PIXELS" "$SIZE"
  echo "$PSNR"
  echo "$PSNRHVS"
  echo "$SSIM"
  echo "$FASTSSIM"


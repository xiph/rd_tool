#!/bin/bash

set -e

export LD_LIBRARY_PATH=/usr/local/lib/
export DAALATOOL_ROOT=/home/ec2-user/daalatool/
export X264=/home/ec2-user/x264/x264
export X265=/home/ec2-user/x265/build/linux/x265
export VPXENC=/home/ec2-user/$CODEC/vpxenc
export VPXDEC=/home/ec2-user/$CODEC/vpxdec
export THORENC=/home/ec2-user/thor/build/Thorenc
export ENCODER_EXAMPLE=/home/ec2-user/daala/examples/encoder_example
export YUV2YUV4MPEG=$DAALATOOL_ROOT/tools/yuv2yuv4mpeg

if [ -z "$DUMP_VIDEO" ]; then
  export DUMP_VIDEO="$DAALA_ROOT/examples/dump_video"
fi

if [ -z "$DUMP_PSNR" ]; then
  export DUMP_PSNR="$DAALATOOL_ROOT/tools/dump_psnr"
fi

if [ -z "$DUMP_PSNRHVS" ]; then
  export DUMP_PSNRHVS="$DAALATOOL_ROOT/tools/dump_psnrhvs"
fi

if [ -z "$DUMP_SSIM" ]; then
  export DUMP_SSIM="$DAALATOOL_ROOT/tools/dump_ssim"
fi

if [ -z "$DUMP_FASTSSIM" ]; then
  export DUMP_FASTSSIM="$DAALATOOL_ROOT/tools/dump_fastssim"
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
  OD_LOG_MODULES='encoder:10' OD_DUMP_IMAGES_SUFFIX="$BASENAME" "$ENCODER_EXAMPLE" -k 256 -v "$x" $EXTRA_OPTIONS "$FILE" -o "$BASENAME.ogv" > /dev/null 2> "$BASENAME-enc.out"
  if [ ! -f "$BASENAME.ogv" ]
  then
    echo Failed to produce "$BASENAME.ogv"
    exit 1
  fi
  SIZE=$(stat -c %s "$BASENAME.ogv")
  mv "00000000out-$BASENAME.y4m" "$BASENAME.y4m"
  ;;
x264)
  $X264 --dump-yuv $BASENAME.yuv --preset placebo --min-keyint 256 --keyint 256 --no-scenecut --crf=$x -o $BASENAME.x264 $FILE 2> $BASENAME-enc.out > /dev/null
  $YUV2YUV4MPEG $BASENAME -w$WIDTH -h$HEIGHT -an0 -ad0 -c420mpeg2
  SIZE=$(stat -c %s $BASENAME.x264)
  ;;
x265)
  $X265 -r $BASENAME.y4m --preset slow --frame-threads 1 --min-keyint 256 --keyint 256 --no-scenecut --crf=$x -o $BASENAME.x265 $FILE 2> $BASENAME-enc.out > /dev/null
  SIZE=$(stat -c %s $BASENAME.x265)
  ;;
x265-rt)
  $X265 -r $BASENAME.y4m --preset slow --tune zerolatency --rc-lookahead 0 --bframes 0 --frame-threads 1 --min-keyint 256 --keyint 256 --no-scenecut --crf=$x --csv $BASENAME.csv -o $BASENAME.x265 $FILE 2> $BASENAME-enc.out > /dev/null
  SIZE=$(stat -c %s $BASENAME.x265)
  ;;
vp8)
  $VPXENC --codec=$CODEC --threads=1 --cpu-used=0 --kf-min-dist=256 --kf-max-dist=256 --end-usage=cq --target-bitrate=100000 --cq-level=$x -o $BASENAME.vpx $FILE 2> $BASENAME-enc.out > /dev/null
  $VPXDEC --codec=$CODEC -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
vp9)
  $VPXENC --codec=$CODEC --cpu-used=0 --threads=1 --auto-alt-ref=1 --kf-min-dist=256 --kf-max-dist=256 --end-usage=q --cq-level=$x -o $BASENAME.vpx $FILE 2> $BASENAME-enc.out > /dev/null
  $VPXDEC --codec=$CODEC -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
vp9-rt)
  $VPXENC --codec=$CODEC --cpu-used=0 --threads=1 --kf-min-dist=256 --kf-max-dist=256 -p 1 --lag-in-frames=0 --end-usage=q --cq-level=$x -o $BASENAME.vpx $FILE 2> $BASENAME-enc.out > /dev/null
  $VPXDEC --codec=$CODEC -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
vp10)
  $VPXENC --codec=$CODEC --cpu-used=0 --passes=2 --threads=1 --kf-min-dist=256 --kf-max-dist=256 --min-q=0 --max-q=63 --end-usage=q --cq-level=$x -o $BASENAME.vpx $FILE 2> $BASENAME-enc.out > /dev/null
  $VPXDEC --codec=$CODEC -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
vp10-rt)
  $VPXENC --codec=$CODEC --cpu-used=0 --threads=1 --kf-min-dist=256 --kf-max-dist=256 -p 1 --lag-in-frames=0 --end-usage=q --cq-level=$x -o $BASENAME.vpx $FILE 2> $BASENAME-enc.out > /dev/null
  $VPXDEC --codec=$CODEC -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
thor)
  $THORENC -qp $x -cf /home/ec2-user/thor/config_HDB16_high_efficiency.txt -if $FILE -of $BASENAME.thor -rf $BASENAME.y4m > $BASENAME-enc.out
  SIZE=$(stat -c %s $BASENAME.thor)
  ;;
esac

"$DUMP_PSNR" "$FILE" "$BASENAME.y4m" > "$BASENAME-psnr.out" 2> /dev/null

FRAMES=$(cat "$BASENAME-psnr.out" | grep ^0 | wc -l)
PIXELS=$(($WIDTH*$HEIGHT*$FRAMES))
PSNR=$(cat "$BASENAME-psnr.out" | grep Total)
PSNRHVS=$("$DUMP_PSNRHVS" "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)
SSIM=$("$DUMP_SSIM" "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)
FASTSSIM=$("$DUMP_FASTSSIM" -c "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)

rm -f "$BASENAME.y4m" "$BASENAME.ogv" "$BASENAME.x264" "$BASENAME.x265" "$BASENAME.vpx" "$BASENAME-enc.out" "$BASENAME-psnr.out" "$BASENAME.thor" 2> /dev/null

echo "$x" "$PIXELS" "$SIZE"
echo "$PSNR"
echo "$PSNRHVS"
echo "$SSIM"
echo "$FASTSSIM"

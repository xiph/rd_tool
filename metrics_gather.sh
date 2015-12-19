#!/bin/bash

set -e

export LD_LIBRARY_PATH=/usr/local/lib/

if [ -z "$DAALATOOL_ROOT" ]; then
  export DAALATOOL_ROOT=/home/ec2-user/daalatool/
fi
export X264=/home/ec2-user/x264/x264
export X265=/home/ec2-user/x265/build/linux/x265
export VPXENC=/home/ec2-user/$CODEC/vpxenc
export VPXDEC=/home/ec2-user/$CODEC/vpxdec
if [ -z "$THORENC" ]; then
  export THORENC="/home/ec2-user/$CODEC/build/Thorenc"
fi
if [ -z "$THORDIR" ]; then
  export THORDIR="$(dirname $THORENC)/../"
fi
if [ -z "$THORDEC" ]; then
  export THORDEC="$(dirname $THORENC)/Thordec"
fi
if [ -z "$ENCODER_EXAMPLE" ]; then
  export ENCODER_EXAMPLE=/home/ec2-user/daala/examples/encoder_example
fi
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

if [ -z "$DUMP_CIEDE" ]; then
  export DUMP_CIEDE="$DAALATOOL_ROOT/tools/dump_ciede2000.py"
fi

if [ -z "$YUV2YUV4MPEG" ]; then
  export DUMP_CIEDE="$DAALATOOL_ROOT/tools/yuv2yuv4mpeg"
fi

if [ -z "$CODEC" ]; then
  export CODEC=daala
fi

FILE=$1

BASENAME="$(basename $FILE)-$x"
rm "$BASENAME.out" 2> /dev/null || true

WIDTH="$(head -1 $FILE | cut -d\  -f 2 | tr -d 'W')"
HEIGHT="$(head -1 $FILE | cut -d\  -f 3 | tr -d 'H')"

# used for libvpx vbr
RATE=$(echo $x*$WIDTH*$HEIGHT*30/1000 | bc)

KFINT=1000

case $CODEC in
daala)
  OD_LOG_MODULES='encoder:10' OD_DUMP_IMAGES_SUFFIX="$BASENAME" "$ENCODER_EXAMPLE" -k $KFINT -v "$x" $EXTRA_OPTIONS "$FILE" -o "$BASENAME.ogv" > /dev/null 2> "$BASENAME-enc.out"
  if [ ! -f "$BASENAME.ogv" ]
  then
    echo Failed to produce "$BASENAME.ogv"
    cat "$BASENAME-enc.out"
    exit 1
  fi
  SIZE=$(stat -c %s "$BASENAME.ogv")
  mv "00000000out-$BASENAME.y4m" "$BASENAME.y4m"
  ;;
x264)
  $X264 --dump-yuv $BASENAME.yuv --preset placebo --min-keyint $KFINT --keyint $KFINT --no-scenecut --crf=$x -o $BASENAME.x264 $EXTRA_OPTIONS $FILE 2> $BASENAME-enc.out > /dev/null
  $YUV2YUV4MPEG $BASENAME -w$WIDTH -h$HEIGHT -an0 -ad0 -c420mpeg2
  SIZE=$(stat -c %s $BASENAME.x264)
  ;;
x265)
  $X265 -r $BASENAME.y4m --preset slow --frame-threads 1 --min-keyint $KFINT --keyint $KFINT --no-scenecut --crf=$x -o $BASENAME.x265 $EXTRA_OPTIONS $FILE 2> $BASENAME-enc.out > /dev/null
  SIZE=$(stat -c %s $BASENAME.x265)
  ;;
x265-rt)
  $X265 -r $BASENAME.y4m --preset slow --tune zerolatency --rc-lookahead 0 --bframes 0 --frame-threads 1 --min-keyint $KFINT --keyint $KFINT --no-scenecut --crf=$x --csv $BASENAME.csv -o $BASENAME.x265 $EXTRA_OPTIONS $FILE 2> $BASENAME-enc.out > /dev/null
  SIZE=$(stat -c %s $BASENAME.x265)
  ;;
vp8)
  $VPXENC --codec=$CODEC --threads=1 --cpu-used=0 --kf-min-dist=$KFINT --kf-max-dist=$KFINT --end-usage=cq --target-bitrate=100000 --cq-level=$x -o $BASENAME.vpx $EXTRA_OPTIONS $FILE 2> $BASENAME-enc.out > /dev/null
  $VPXDEC --codec=$CODEC -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
vp9)
  $VPXENC --codec=$CODEC --frame-parallel=0 --tile-columns=0 --cpu-used=0 --threads=1 --kf-min-dist=$KFINT --kf-max-dist=$KFINT --end-usage=q --cq-level=$x -o $BASENAME.vpx $EXTRA_OPTIONS $FILE 2> $BASENAME-enc.out > /dev/null
  $VPXDEC --codec=$CODEC -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
vp9-rt)
  $VPXENC --codec=vp9 --frame-parallel=0 --tile-columns=0 -cpu-used=0 --threads=1 --kf-min-dist=$KFINT --kf-max-dist=$KFINT -p 1 --lag-in-frames=0 --end-usage=q --cq-level=$x -o $BASENAME.vpx $EXTRA_OPTIONS $FILE 2> $BASENAME-enc.out > /dev/null
  $VPXDEC --codec=vp9 -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
vp10)
  $VPXENC --codec=$CODEC --ivf --frame-parallel=0 --tile-columns=0 --auto-alt-ref=2 --cpu-used=0 --passes=2 --threads=1 --kf-min-dist=$KFINT --kf-max-dist=$KFINT --lag-in-frames=25 --end-usage=q --cq-level=$x -o $BASENAME.vpx $EXTRA_OPTIONS $FILE 2> $BASENAME-enc.out > /dev/null
  $VPXDEC --codec=$CODEC -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
vp10-rt)
  $VPXENC --codec=vp10 --ivf --frame-parallel=0 --tile-columns=0 --cpu-used=0 --passes=1 --threads=1 --kf-min-dist=$KFINT --kf-max-dist=$KFINT --lag-in-frames=0 --end-usage=q --cq-level=$x -o $BASENAME.vpx $EXTRA_OPTIONS $FILE 2> $BASENAME-enc.out > /dev/null
  $VPXDEC --codec=vp10 -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
thor)
  $THORENC -qp $x -cf "$THORDIR/config_HDB16_high_efficiency.txt" -if $FILE -of $BASENAME.thor $EXTRA_OPTIONS > $BASENAME-enc.out
  SIZE=$(stat -c %s $BASENAME.thor)
  # using reconstruction is currently broken with HDB
  $THORDEC $BASENAME.thor $BASENAME.yuv
  $YUV2YUV4MPEG $BASENAME -w$WIDTH -h$HEIGHT
  ;;
thor-rt)
  $THORENC -qp $x -cf "$THORDIR/config_LDB_high_efficiency.txt" -if $FILE -of $BASENAME.thor -rf $BASENAME.y4m $EXTRA_OPTIONS > $BASENAME-enc.out
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
CIEDE=$("$DUMP_CIEDE" "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)

rm -f "$BASENAME.y4m" "$BASENAME.yuv" "$BASENAME.ogv" "$BASENAME.x264" "$BASENAME.x265" "$BASENAME.vpx" "$BASENAME-enc.out" "$BASENAME-psnr.out" "$BASENAME.thor" 2> /dev/null

echo "$x" "$PIXELS" "$SIZE"
echo "$PSNR"
echo "$PSNRHVS"
echo "$SSIM"
echo "$FASTSSIM"
echo "$CIEDE"

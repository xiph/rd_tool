#!/bin/bash

set -e

export LD_LIBRARY_PATH=/usr/local/lib/

#3GB RAM limit
ulimit -m 3000000

#enable core dumps (warning - uses up to 3GB per slot!)
#requires /proc/sys/kernel/core_pattern = core
#switch to using gdb at some point
#ulimit -S -c unlimited

if [ -z "$WORK_ROOT" ]; then
  export WORK_ROOT=/home/ec2-user
fi

cd "$WORK_ROOT"

if [ -z "$DAALATOOL_ROOT" ]; then
  export DAALATOOL_ROOT="$WORK_ROOT/daalatool/"
fi
export X264="$WORK_ROOT/x264/x264"
export X265="$WORK_ROOT/x265/build/linux/x265"
export XVCENC="$WORK_ROOT/xvc/build/app/xvcenc"
export XVCDEC="$WORK_ROOT/xvc/build/app/xvcdec"
export VPXENC="$WORK_ROOT/$CODEC/vpxenc"
export VPXDEC="$WORK_ROOT/$CODEC/vpxdec"
if [ -z "$AOMENC" ]; then
  export AOMENC="$WORK_ROOT/$CODEC/aomenc"
fi
if [ -z "$AOMDEC" ]; then
  export AOMDEC="$WORK_ROOT/$CODEC/aomdec"
fi
if [ -z "$THORENC" ]; then
  export THORENC="$WORK_ROOT/$CODEC/build/Thorenc"
fi
if [ -z "$THORDIR" ]; then
  export THORDIR="$(dirname $THORENC)/../"
fi
if [ -z "$THORDEC" ]; then
  export THORDEC="$(dirname $THORENC)/Thordec"
fi
if [ -z "$RAV1E" ]; then
  export RAV1E="$WORK_ROOT/$CODEC/target/release/rav1e"
fi
if [ -z "$SVTAV1" ]; then
  export SVTAV1="$WORK_ROOT/$CODEC/Bin/Release/SvtAv1EncApp"
fi
if [ -z "$ENCODER_EXAMPLE" ]; then
  export ENCODER_EXAMPLE="$WORK_ROOT/daala/examples/encoder_example"
fi
export YUV2YUV4MPEG="$DAALATOOL_ROOT/tools/yuv2yuv4mpeg"
export Y4M2YUV="$DAALATOOL_ROOT/tools/y4m2yuv"
if [ -z "$DUMP_VIDEO" ]; then
  export DUMP_VIDEO="$WORK_ROOT/daala/examples/dump_video"
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

if [ -z "$DUMP_MSSSIM" ]; then
  export DUMP_MSSSIM="$DAALATOOL_ROOT/tools/dump_msssim"
fi

if [ -z "$DUMP_CIEDE" ]; then
  export DUMP_CIEDE="$DAALATOOL_ROOT/../dump_ciede2000/target/release/dump_ciede2000"
fi

if [ -z "$VMAF_ROOT" ]; then
  export VMAF_ROOT="$DAALATOOL_ROOT/../vmaf"
fi

if [ -z "$VMAFOSSEXEC" ]; then
  export VMAFOSSEXEC="$VMAF_ROOT/libvmaf/build/tools/vmafossexec"
fi

if [ -z "$VMAFMODEL" ]; then
  export VMAFMODEL="vmaf_v0.6.1.pkl" # File name in $VMAFROOT/model
fi

if [ -z "$YUV2YUV4MPEG" ]; then
  export YUV2YUV4MPEG="$DAALATOOL_ROOT/tools/yuv2yuv4mpeg"
fi

if [ -z "$CODEC" ]; then
  export CODEC=daala
fi

if [ -z "$x" ]; then
  echo Missing quality setting
  exit 1
fi

if [ -e pid ]; then
  kill -9 -$(cat pid) || true
fi

echo $$ > pid

FILE=$1

BASENAME="$(basename $FILE)-$x"
rm "$BASENAME.out" 2> /dev/null || true

WIDTH="$(head -1 $FILE | cut -d\  -f 2 | tr -d 'W')"
HEIGHT="$(head -1 $FILE | cut -d\  -f 3 | tr -d 'H')"
CHROMA="$(head -1 $FILE | cut -d\  -f 7 | tr -d 'C')"
DEPTH=8
case $CHROMA in
444p10)
  DEPTH=10
  ;;
420p10)
  DEPTH=10
  ;;
esac

# used for libvpx vbr
RATE=$(echo $x*$WIDTH*$HEIGHT*30/1000 | bc)

KFINT=1000
TIMEROUT=$BASENAME-enctime.out
TIMERDECOUT=$BASENAME-dectime.out
TIMER='time -v --output='"$TIMEROUT"
TIMERDEC='time -v --output='"$TIMERDECOUT"
AOMDEC_OPTS='-S'

case $CODEC in
daala)
  $(OD_LOG_MODULES='encoder:10' OD_DUMP_IMAGES_SUFFIX="$BASENAME" $TIMER "$ENCODER_EXAMPLE" -k $KFINT -v "$x" $EXTRA_OPTIONS "$FILE" -o "$BASENAME.ogv" > "$BASENAME-stdout.txt" 2> "$BASENAME-enc.out")
  if [ ! -f "$BASENAME.ogv" ]
  then
    echo Failed to produce "$BASENAME.ogv"
    cat "$BASENAME-enc.out"
    exit 1
  fi
  SIZE=$(stat -c %s "$BASENAME.ogv")
  #mv "00000000out-$BASENAME.y4m" "$BASENAME.y4m"
  rm -f "00000000out-$BASENAME.y4m"
  "$DUMP_VIDEO" "$BASENAME.ogv" -o "$BASENAME.y4m"
  ;;
x264)
  $($TIMER $X264 --dump-yuv $BASENAME.yuv --preset placebo --min-keyint $KFINT --keyint $KFINT --no-scenecut --crf=$x -o $BASENAME.x264 $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  $YUV2YUV4MPEG $BASENAME -w$WIDTH -h$HEIGHT -an0 -ad0 -c420mpeg2
  SIZE=$(stat -c %s $BASENAME.x264)
  ;;
x265)
  $($TIMER $X265 -r $BASENAME.y4m --preset slow --frame-threads 1 --min-keyint $KFINT --keyint $KFINT --no-scenecut --crf=$x -o $BASENAME.x265 $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  SIZE=$(stat -c %s $BASENAME.x265)
  ;;
x265-rt)
  $($TIMER $X265 -r $BASENAME.y4m --preset slow --tune zerolatency --rc-lookahead 0 --bframes 0 --frame-threads 1 --min-keyint $KFINT --keyint $KFINT --no-scenecut --crf=$x --csv $BASENAME.csv -o $BASENAME.x265 $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  SIZE=$(stat -c %s $BASENAME.x265)
  ;;
xvc)
  $($TIMER $XVCENC -max-keypic-distance $KFINT -qp $x -output-file $BASENAME.xvc $EXTRA_OPTIONS -input-file $FILE > "$BASENAME-stdout.txt")
  $($TIMERDEC $XVCDEC -output-bitdepth $DEPTH -dither 0 -output-file $BASENAME.yuv -bitstream-file $BASENAME.xvc >> $BASENAME-stdout.txt)
  $YUV2YUV4MPEG $BASENAME -w$WIDTH -h$HEIGHT -an0 -ad0 -c420mpeg2
  SIZE=$(stat -c %s $BASENAME.xvc)
  ;;
vp8)
  $($TIMER $VPXENC --codec=$CODEC --threads=1 --cpu-used=0 --kf-min-dist=$KFINT --kf-max-dist=$KFINT --end-usage=cq --target-bitrate=100000 --cq-level=$x -o $BASENAME.vpx $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  $VPXDEC --codec=$CODEC -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
vp9)
  $($TIMER $VPXENC --codec=$CODEC --ivf --frame-parallel=0 --tile-columns=0 --auto-alt-ref=2 --cpu-used=0 --passes=2 --threads=1 --kf-min-dist=$KFINT --kf-max-dist=$KFINT --lag-in-frames=25 --end-usage=q --cq-level=$x -o $BASENAME.vpx $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  $VPXDEC --codec=$CODEC -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
vp9-rt)
  $($TIMER $VPXENC --codec=vp9 --ivf --frame-parallel=0 --tile-columns=0 --cpu-used=0 --threads=1 --kf-min-dist=$KFINT --kf-max-dist=$KFINT -p 1 --lag-in-frames=0 --end-usage=q --cq-level=$x -o $BASENAME.vpx $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  $VPXDEC --codec=vp9 -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
vp10)
  $($TIMER $VPXENC --codec=$CODEC --ivf --frame-parallel=0 --tile-columns=0 --auto-alt-ref=2 --cpu-used=0 --passes=2 --threads=1 --kf-min-dist=$KFINT --kf-max-dist=$KFINT --lag-in-frames=25 --end-usage=q --cq-level=$x -o $BASENAME.vpx $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  $VPXDEC --codec=$CODEC -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
vp10-rt)
  $($TIMER $VPXENC --codec=vp10 --ivf --frame-parallel=0 --tile-columns=0 --cpu-used=0 --passes=1 --threads=1 --kf-min-dist=$KFINT --kf-max-dist=$KFINT --lag-in-frames=0 --end-usage=q --cq-level=$x -o $BASENAME.vpx $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  $VPXDEC --codec=vp10 -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ;;
av1)
  $($TIMER $AOMENC --codec=$CODEC --ivf --frame-parallel=0 --tile-columns=0 --auto-alt-ref=2 --cpu-used=0 --passes=2 --threads=1 --kf-min-dist=$KFINT --kf-max-dist=$KFINT --lag-in-frames=25 --end-usage=q --cq-level=$x --test-decode=fatal -o $BASENAME.ivf $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  if $AOMDEC --help 2>&1 | grep output-bit-depth > /dev/null; then
    AOMDEC_OPTS+=" --output-bit-depth=$DEPTH"
  fi
  $($TIMERDEC $AOMDEC --codec=$CODEC $AOMDEC_OPTS -o $BASENAME.y4m $BASENAME.ivf)
  SIZE=$(stat -c %s $BASENAME.ivf)
  ;;
av1-rt)
  $($TIMER $AOMENC --codec=av1 --ivf --frame-parallel=0 --tile-columns=0 --cpu-used=0 --passes=1 --threads=1 --kf-min-dist=$KFINT --kf-max-dist=$KFINT --lag-in-frames=0 --end-usage=q --cq-level=$x --test-decode=fatal -o $BASENAME.ivf $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  if $AOMDEC --help 2>&1 | grep output-bit-depth > /dev/null; then
    AOMDEC_OPTS+=" --output-bit-depth=$DEPTH"
  fi
  $($TIMERDEC $AOMDEC --codec=av1 $AOMDEC_OPTS -o $BASENAME.y4m $BASENAME.ivf)
  SIZE=$(stat -c %s $BASENAME.ivf)
  ;;
thor)
  $($TIMER $THORENC -qp $x -cf "$THORDIR/config_HDB16_high_efficiency.txt" -if $FILE -of $BASENAME.thor $EXTRA_OPTIONS > $BASENAME-enc.out)
  SIZE=$(stat -c %s $BASENAME.thor)
  # using reconstruction is currently broken with HDB
  $THORDEC $BASENAME.thor $BASENAME.yuv > "$BASENAME-stdout.txt"
  $YUV2YUV4MPEG $BASENAME -an1 -ad1 -w$WIDTH -h$HEIGHT
  ;;
thor-rt)
  $($TIMER $THORENC -qp $x -cf "$THORDIR/config_LDB_high_efficiency.txt" -if $FILE -of $BASENAME.thor -rf $BASENAME.y4m $EXTRA_OPTIONS > $BASENAME-enc.out)
  SIZE=$(stat -c %s $BASENAME.thor)
  ;;
rav1e)
  $($TIMER $RAV1E $FILE --quantizer $x -o $BASENAME.ivf -r $BASENAME-rec.y4m --threads 1 $EXTRA_OPTIONS > $BASENAME-enc.out)
  if hash dav1d 2>/dev/null; then
    $($TIMERDEC dav1d -q -i $BASENAME.ivf -o $BASENAME.y4m) || (echo "Corrupt bitstream detected!"; exit 98)
  elif hash aomdec 2>/dev/null; then
    $($TIMERDEC aomdec --codec=av1 $AOMDEC_OPTS -o $BASENAME.y4m $BASENAME.ivf) || (echo "Corrupt bitstream detected!"; exit 98)
  else
    echo "AV1 decoder not found, desync/corruption detection disabled."
  fi

  if [ -f $BASENAME.y4m ]; then
    "$Y4M2YUV" "$BASENAME-rec.y4m" -o rec.yuv
    "$Y4M2YUV" "$BASENAME.y4m" -o enc.yuv
    cmp --silent rec.yuv enc.yuv || (echo "Reconstruction differs from output!"; rm -f rec.yuv enc.yuv "$BASENAME-rec.y4m"; exit 98)
    rm -f rec.yuv enc.yuv "$BASENAME-rec.y4m"
  fi
  SIZE=$(stat -c %s $BASENAME.ivf)
  ;;
svt-av1)
  export LD_LIBRARY_PATH=$(dirname "$SVTAV1")
  # svt-av1 has a max intra period of 255
  $($TIMER $SVTAV1 -i $FILE -enc-mode 0 -lp 1 -q $x -o $BASENAME.yuv -b $BASENAME.ivf -w $WIDTH -h $HEIGHT -intra-period 255 $EXTRA_OPTIONS > $BASENAME-enc.out 2>&1)
  $YUV2YUV4MPEG $BASENAME -an1 -ad1 -w$WIDTH -h$HEIGHT > /dev/null
  rm $BASENAME.yuv
  SIZE=$(stat -c %s $BASENAME.ivf)
  ;;
esac

#rename core dumps to prevent more than 1 per slot on disk
mv core.* core 2>/dev/null || true

"$DUMP_PSNR" -a "$FILE" "$BASENAME.y4m" > "$BASENAME-psnr.out"

FRAMES=$(cat "$BASENAME-psnr.out" | grep ^0 | wc -l)
PIXELS=$(($WIDTH*$HEIGHT*$FRAMES))

echo "$x" "$PIXELS" "$SIZE"

PSNR=$(cat "$BASENAME-psnr.out" | grep Total)

echo "$PSNR"

APSNR=$(cat "$BASENAME-psnr.out" | grep Frame-averaged)
PSNRHVS=$("$DUMP_PSNRHVS" "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)

echo "$PSNRHVS"

SSIM=$("$DUMP_SSIM" "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)

echo "$SSIM"

FASTSSIM=$("$DUMP_FASTSSIM" -c "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)

echo "$FASTSSIM"

CIEDE=$("$DUMP_CIEDE" --threads 1 "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)

echo "$CIEDE"

echo "$APSNR"

MSSSIM=$("$DUMP_MSSSIM" "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)

echo "$MSSSIM"

if [ -e "$TIMEROUT" ]; then
  ENCTIME=$(awk '/User/ { s=$4 } END { printf "%.2f", s }' "$TIMEROUT")
else
  ENCTIME=0
fi

echo "$ENCTIME"

if [ -f "$VMAFOSSEXEC" ]; then
  FORMAT=yuv420p
  case $CHROMA in
      420p10)
          FORMAT=yuv420p10le
          ;;
      444p10)
          FORMAT=yuv444p10le
          ;;
      444)
          FORMAT=yuv444p
          ;;
  esac
  "$Y4M2YUV" "$FILE" -o ref
  "$Y4M2YUV" "$BASENAME.y4m" -o dis
  "$VMAFOSSEXEC" $FORMAT $WIDTH $HEIGHT ref dis "$VMAF_ROOT/model/$VMAFMODEL" --log-fmt csv --log "$BASENAME-vmaf.csv" --thread 1 | tail -n 1
  VMAF=$(cat "$BASENAME-vmaf.csv" | grep -o "[^,]*" | tail -1)
  rm -f ref dis
  echo "$VMAF"
else
  echo "0"
fi

if [ -e "$TIMERDECOUT" ]; then
  DECTIME=$(awk '/User/ { s=$4 } END { printf "%.2f", s }' "$TIMERDECOUT")
else
  DECTIME=0
fi

echo "$DECTIME"

if [ ! "$NO_DELETE" ]; then
  rm -f "$BASENAME.ogv" "$BASENAME.x264" "$BASENAME.x265" "$BASENAME.xvc" "$BASENAME.vpx" "$BASENAME.ivf" "$TIMEROUT" "$BASENAME-enc.out" "$BASENAME-psnr.out" "$BASENAME.thor" 2> /dev/null
fi

rm -f "$BASENAME.y4m" "$BASENAME.yuv" "$BASENAME-rec.y4m" 2> /dev/null

rm -f pid

#!/bin/bash

set -e

export LD_LIBRARY_PATH=/usr/local/lib/

#3GB RAM limit
ulimit -m 8000000

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
if [ -z "$VVCENC" ]; then
  export VVCENC="$WORK_ROOT/$CODEC/bin/EncoderAppStatic"
fi
if [ -z "$VVCDEC" ]; then
  export VVCDEC="$WORK_ROOT/$CODEC/bin/DecoderAppStatic"
fi
if [ -z "$VVCCAT" ]; then
  export VVCCAT="$WORK_ROOT/$CODEC/bin/parcatStatic"
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

if [ -z "$VMAF" ]; then
  export VMAF="$VMAF_ROOT/libvmaf/build/tools/vmaf"
fi

if [ -z "$VMAFMODEL" ]; then
  export VMAFMODEL="vmaf_v0.6.1.json" # File name in $VMAFROOT/model
fi

if [ -z "$YUV2YUV4MPEG" ]; then
  export YUV2YUV4MPEG="$DAALATOOL_ROOT/tools/yuv2yuv4mpeg"
fi

if [ -z "$HDRTOOLS_ROOT" ]; then
  export HDRTOOLS_ROOT="$DAALATOOL_ROOT/../hdrtools"
fi

if [ -z "$HDRCONVERT" ]; then
  export HDRCONVERT="$HDRTOOLS_ROOT/bin/HDRConvert"
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

if  [ ! -x "$(command -v perf)" ]; then
  echo "perf, perf-stat is not installed"
  exit 1
fi

echo $$ > pid

FILE=$1

BASENAME="$(basename $FILE)-$x"
rm "$BASENAME.out" 2> /dev/null || true

WIDTH=$(head -1 $FILE | tr ' ' '\n' | grep -E '\bW' | tr -d 'W')
HEIGHT=$(head -1 $FILE | tr ' ' '\n' | grep -E '\bH' | tr -d 'H')
CHROMA=$(head -1 $FILE | tr ' ' '\n' | grep -E '\bC')
# YUV2Y4M requires to be just numbers
YUV_CHROMA=$CHROMA
DEPTH=8
case $CHROMA in
C444p10)
  DEPTH=10
  YUV_CHROMA=444
  ;;
C420p10)
  DEPTH=10
  YUV_CHROMA=420
  ;;
C420jpeg | C420mpeg2)
  YUV_CHROMA=420
esac

# used for libvpx vbr
RATE=$(echo $x*$WIDTH*$HEIGHT*30/1000 | bc)

KFINT=1000
TIMEROUT=$BASENAME-enctime.out
PERF_ENC_OUT=${BASENAME}'-encperf.out'
PERF_DEC_OUT=${BASENAME}'-decperf.out'
PERF_ENC_STAT='perf stat -o '${PERF_ENC_OUT}''
PERF_DEC_STAT='perf stat -o '${PERF_DEC_OUT}''
TIMERDECOUT=$BASENAME-dectime.out
TIMER=$PERF_ENC_STAT' time -v --output='"$TIMEROUT"
TIMERDEC=$PERF_DEC_STAT' time -v --output='"$TIMERDECOUT"
AOMDEC_OPTS='-S'
ENC_EXT=''

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
  ENC_EXT='.ogv'
  #mv "00000000out-$BASENAME.y4m" "$BASENAME.y4m"
  rm -f "00000000out-$BASENAME.y4m"
  "$DUMP_VIDEO" "$BASENAME.ogv" -o "$BASENAME.y4m"
  ;;
x264)
  $($TIMER $X264 --dump-yuv $BASENAME.yuv --preset placebo --min-keyint $KFINT --keyint $KFINT --no-scenecut --crf=$x -o $BASENAME.x264 $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  $YUV2YUV4MPEG $BASENAME -w$WIDTH -h$HEIGHT -an0 -ad0 -c420mpeg2
  SIZE=$(stat -c %s $BASENAME.x264)
  ENC_EXT='.x264'
  ;;
x265)
  $($TIMER $X265 -r $BASENAME.y4m --preset slow --frame-threads 1 --min-keyint $KFINT --keyint $KFINT --no-scenecut --crf=$x -o $BASENAME.x265 $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  SIZE=$(stat -c %s $BASENAME.x265)
  ENC_EXT='.x265'
  ;;
x265-rt)
  $($TIMER $X265 -r $BASENAME.y4m --preset slow --tune zerolatency --rc-lookahead 0 --bframes 0 --frame-threads 1 --min-keyint $KFINT --keyint $KFINT --no-scenecut --crf=$x --csv $BASENAME.csv -o $BASENAME.x265 $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  SIZE=$(stat -c %s $BASENAME.x265)
  ENC_EXT='.x265'
  ;;
xvc)
  $($TIMER $XVCENC -max-keypic-distance $KFINT -qp $x -output-file $BASENAME.xvc $EXTRA_OPTIONS -input-file $FILE > "$BASENAME-stdout.txt")
  $($TIMERDEC $XVCDEC -output-bitdepth $DEPTH -dither 0 -output-file $BASENAME.yuv -bitstream-file $BASENAME.xvc >> $BASENAME-stdout.txt)
  $YUV2YUV4MPEG $BASENAME -w$WIDTH -h$HEIGHT -an0 -ad0 -c420mpeg2
  SIZE=$(stat -c %s $BASENAME.xvc)
  ENC_EXT='.x265'
  ;;
vp8)
  $($TIMER $VPXENC --codec=$CODEC --threads=1 --cpu-used=0 --kf-min-dist=$KFINT --kf-max-dist=$KFINT --end-usage=cq --target-bitrate=100000 --cq-level=$x -o $BASENAME.vpx $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  $VPXDEC --codec=$CODEC -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ENC_EXT='.vpx'
  ;;
vp9)
  $($TIMER $VPXENC --codec=$CODEC --ivf --frame-parallel=0 --tile-columns=0 --auto-alt-ref=2 --cpu-used=0 --passes=2 --threads=1 --kf-min-dist=$KFINT --kf-max-dist=$KFINT --lag-in-frames=25 --end-usage=q --cq-level=$x -o $BASENAME.vpx $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  $VPXDEC --codec=$CODEC -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ENC_EXT='.vpx'
  ;;
vp9-rt)
  $($TIMER $VPXENC --codec=vp9 --ivf --frame-parallel=0 --tile-columns=0 --cpu-used=0 --threads=1 --kf-min-dist=$KFINT --kf-max-dist=$KFINT -p 1 --lag-in-frames=0 --end-usage=q --cq-level=$x -o $BASENAME.vpx $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  $VPXDEC --codec=vp9 -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ENC_EXT='.vpx'
  ;;
vp10)
  $($TIMER $VPXENC --codec=$CODEC --ivf --frame-parallel=0 --tile-columns=0 --auto-alt-ref=2 --cpu-used=0 --passes=2 --threads=1 --kf-min-dist=$KFINT --kf-max-dist=$KFINT --lag-in-frames=25 --end-usage=q --cq-level=$x -o $BASENAME.vpx $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  $VPXDEC --codec=$CODEC -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ENC_EXT='.vpx'
  ;;
vp10-rt)
  $($TIMER $VPXENC --codec=vp10 --ivf --frame-parallel=0 --tile-columns=0 --cpu-used=0 --passes=1 --threads=1 --kf-min-dist=$KFINT --kf-max-dist=$KFINT --lag-in-frames=0 --end-usage=q --cq-level=$x -o $BASENAME.vpx $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  $VPXDEC --codec=vp10 -o $BASENAME.y4m $BASENAME.vpx
  SIZE=$(stat -c %s $BASENAME.vpx)
  ENC_EXT='.vpx'
  ;;
av1)
  $($TIMER $AOMENC --codec=$CODEC --ivf --frame-parallel=0 --tile-columns=0 --auto-alt-ref=2 --cpu-used=0 --passes=2 --threads=1 --kf-min-dist=$KFINT --kf-max-dist=$KFINT --lag-in-frames=25 --end-usage=q --cq-level=$x --test-decode=fatal -o $BASENAME.ivf $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  if $AOMDEC --help 2>&1 | grep output-bit-depth > /dev/null; then
    AOMDEC_OPTS+=" --output-bit-depth=$DEPTH"
  fi
  $($TIMERDEC $AOMDEC --codec=$CODEC $AOMDEC_OPTS -o $BASENAME.y4m $BASENAME.ivf)
  SIZE=$(stat -c %s $BASENAME.ivf)
  ENC_EXT='.ivf'
  ;;
av1-rt)
  $($TIMER $AOMENC --codec=av1 --ivf --frame-parallel=0 --tile-columns=0 --cpu-used=0 --passes=1 --threads=1 --kf-min-dist=$KFINT --kf-max-dist=$KFINT --lag-in-frames=0 --end-usage=q --cq-level=$x --test-decode=fatal -o $BASENAME.ivf $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
  if $AOMDEC --help 2>&1 | grep output-bit-depth > /dev/null; then
    AOMDEC_OPTS+=" --output-bit-depth=$DEPTH"
  fi
  $($TIMERDEC $AOMDEC --codec=av1 $AOMDEC_OPTS -o $BASENAME.y4m $BASENAME.ivf)
  SIZE=$(stat -c %s $BASENAME.ivf)
  ENC_EXT='.ivf'
  ;;
av2 | av2-ai | av2-ra | av2-ra-st | av2-ld | av2-as | av2-as-st)
  case $CODEC in
    av2-ai)
      CTC_PROFILE_OPTS="--cpu-used=0 --passes=1 --end-usage=q --kf-min-dist=0 --kf-max-dist=0 --use-fixed-qp-offsets=1 --limit=30 --deltaq-mode=0 --enable-tpl-model=0 --enable-keyframe-filtering=0 --obu"
      ;;
    av2-ra | av2-ra-st | av2-as | av2-as | av2-as-st)
      CTC_PROFILE_OPTS="--cpu-used=0 --passes=1 --lag-in-frames=19 --auto-alt-ref=1 --min-gf-interval=16 --max-gf-interval=16 --gf-min-pyr-height=4 --gf-max-pyr-height=4 --limit=130 --kf-min-dist=65 --kf-max-dist=65 --use-fixed-qp-offsets=1 --deltaq-mode=0 --enable-tpl-model=0 --end-usage=q --enable-keyframe-filtering=0 --obu"
      ;;
    av2-ld)
      CTC_PROFILE_OPTS="--cpu-used=0 --passes=1 --lag-in-frames=0 --min-gf-interval=16 --max-gf-interval=16 --gf-min-pyr-height=4 --gf-max-pyr-height=4 --limit=130 --kf-min-dist=9999 --kf-max-dist=9999  --use-fixed-qp-offsets=1 --deltaq-mode=0 --enable-tpl-model=0 --end-usage=q --subgop-config-str=ld --enable-keyframe-filtering=0 --obu"
      ;;
    av2)
      # generic, not currently used
      CTC_PROFILE_OPTS=""
      ;;
  esac
  if [ $((WIDTH)) -ge 3840 ] && [ $((HEIGHT)) -ge 2160 ]; then
    CTC_PROFILE_OPTS+=" --tile-columns=1 --threads=2 --row-mt=0"
  else
    CTC_PROFILE_OPTS+=" --tile-columns=0 --threads=1"
  fi
 # CTCv6:  1. 2x2 tiling for E/G1 in RA
 #         2. 10bit for A2/A4/B1
 #         3. SCC tune for B2; SC detector on for others
  case $CTC_VERSION in
    6.0)
    case $CTC_CLASS in
      E | G1)
      case $CODEC in
        av2-ra | av2-ra-st)
          CTC_PROFILE_OPTS+=" --row-mt=0 --threads=4 --tile-rows=1 --tile-columns=1"
        ;;
      esac
      ;;
      A2 | A4 | B1)
        CTC_PROFILE_OPTS+=" --bit-depth=10"
      ;;
    esac
    ;;
  esac
  case $CTC_VERSION in
    6.0)
    case $CTC_CLASS in
      B2)
        CTC_PROFILE_OPTS+=" --tune-content=screen --enable-intrabc-ext=1"
      ;;
      *)
        CTC_PROFILE_OPTS+=" --enable-intrabc-ext=2"
      ;;
    esac
    ;;
  esac
  case $CTC_CLASS in
    G1 | G2)
    CTC_PROFILE_OPTS+=" --color-primaries=bt2020 --transfer-characteristics=smpte2084 --matrix-coefficients=bt2020ncl --chroma-sample-position=colocated"
    ;;
    F1 | F2)
    CTC_PROFILE_OPTS+=" --limit=1 "
    ;;
    # CTCv4: Suggests to have multhreading with tiling for A2 and B1 in LD
    # CTCv5: Suggests to have column tiling along with row-tiling:)
    A2 | B1)
      case $CODEC in
        av2-ld)
          case $CTC_VERSION in
          5.0 | 6.0)
            CTC_PROFILE_OPTS+=" --row-mt=0 --threads=4 --tile-rows=1 --tile-columns=1"
          ;;
          4.0)
            CTC_PROFILE_OPTS+=" --row-mt=0 --threads=2 --tile-rows=1"
          ;;
          esac
        ;;
      esac
    ;;
  esac
  # threading options for the A1 test set must be overriden via EXTRA_OPTIONS at a higher level
  case $CODEC in
    av2-ra | av2-as)
      # this is intentionally not a separate script as only metrics_gather.sh is sent to workers
      echo "#!/bin/bash" > /tmp/enc$$.sh
      echo "PERF_ENC_OUT='${BASENAME}'-encperf-\$1.out" >> /tmp/enc$$.sh
      echo "PERF_ENC_STAT='perf stat -o '\${PERF_ENC_OUT}''" >> /tmp/enc$$.sh
      echo "TIMER=''\${PERF_ENC_STAT}' time -v --output='enctime$$-\$1.out" >> /tmp/enc$$.sh
      echo "RUN='$AOMENC --qp=$x --test-decode=fatal $CTC_PROFILE_OPTS -o $BASENAME-'\$1'.obu --limit=130 --'\$1'=65 $EXTRA_OPTIONS $FILE'" >> /tmp/enc$$.sh
      echo "\$(\$TIMER \$RUN > $BASENAME$$-\$1-stdout.txt)" >> /tmp/enc$$.sh
      chmod +x /tmp/enc$$.sh
      for s in {limit,skip}; do printf "$s\0"; done | xargs -0 -n1 -P2 /tmp/enc$$.sh
      $(cat $BASENAME-limit.obu $BASENAME-skip.obu > $BASENAME.obu)
      $(cat $BASENAME$$-limit-stdout.txt $BASENAME$$-skip-stdout.txt > $BASENAME-stdout.txt)
      $(cat enctime$$-limit.out enctime$$-skip.out > $BASENAME-enctime.out)
      $(cat ${BASENAME}-encperf-limit.out ${BASENAME}-encperf-skip.out > $BASENAME-encperf.out)
      TIME1=$(cat enctime$$-limit.out | grep User | cut -d\  -f4)
      TIME2=$(cat enctime$$-skip.out | grep User | cut -d\  -f4)
      PERF_ENC_INSTR_CNT1=$(awk '/instructions/ { s=$1 } END { gsub(",", "", s) ; print s }' ${BASENAME}-encperf-limit.out)
      PERF_ENC_INSTR_CNT2=$(awk '/instructions/ { s=$1 } END { gsub(",", "", s) ; print s }' ${BASENAME}-encperf-skip.out)
      PERF_ENC_CYCLE_CNT1=$(awk '/cycles/ { s=$1 } END { gsub(",", "", s) ; print s }' ${BASENAME}-encperf-limit.out)
      PERF_ENC_CYCLE_CNT2=$(awk '/cycles/ { s=$1 } END { gsub(",", "", s) ; print s }' ${BASENAME}-encperf-skip.out)
      ENCTIME=$(awk "BEGIN {print $TIME1+$TIME2; exit}")
      PERF_ENC_INSTR_CNT=$(awk "BEGIN {print $PERF_ENC_INSTR_CNT1+$PERF_ENC_INSTR_CNT2; exit}")
      PERF_ENC_CYCLE_CNT=$(awk "BEGIN {print $PERF_ENC_CYCLE_CNT1+$PERF_ENC_CYCLE_CNT2; exit}")
      rm -f /tmp/enc$$.sh enctime$$-limit.out enctime$$-skip.out $BASENAME-limit.obu $BASENAME-skip.obu
      ;;
    *)
      $($TIMER $AOMENC --qp=$x --test-decode=fatal $CTC_PROFILE_OPTS -o $BASENAME.obu $EXTRA_OPTIONS $FILE  > "$BASENAME-stdout.txt")
      ;;
  esac
  # decode the OBU to Y4M
  if $AOMDEC --help 2>&1 | grep output-bit-depth > /dev/null; then
    AOMDEC_OPTS+=" --output-bit-depth=$DEPTH"
  fi
  $($TIMERDEC $AOMDEC $AOMDEC_OPTS -o $BASENAME.y4m $BASENAME.obu)
  SIZE=$(stat -c %s $BASENAME.obu)
  ENC_EXT='.obu'
  case $CODEC in
    av2-as | av2-as-st)
      if [ $((WIDTH)) -ne 3840 ] && [ $((HEIGHT)) -ne 2160 ]; then
        # change the reference to 3840x2160
        FILE=$(sed -e 's/\(640x360\|960x540\|1280x720\|1920x1080\|2560x1440\)/3840x2160/' <<< $FILE)
        # hack to force input Y4M file to F30:1 because HDRConvert requires specifying an output frame rate, and if they do not match it will resample temporaly
        echo "YUV4MPEG2 W$WIDTH H$HEIGHT F30:1 $CHROMA" > $BASENAME-$$.y4m
        $(tail -n+2 $BASENAME.y4m >> $BASENAME-$$.y4m)
        # upsample decoded output to 3840x2160
        $HDRCONVERT -p SourceFile=$BASENAME-$$.y4m -p OutputFile=$BASENAME-$$-out.y4m -p OutputWidth=3840 -p OutputHeight=2160 -p OutputChromaFormat=1 -p OutputBitDepthCmp0=10 -p OutputBitDepthCmp1=10 -p OutputBitDepthCmp2=10 -p OutputColorSpace=0 -p OutputColorPrimaries=0 -p OutputTransferFunction=12 -p SilentMode=1 -p ScaleOnly=1 -p ScalingMode=12 -p OutputRate=30 -p NumberOfFrames=130 1>&2
        # replace decoded output with upsampled file using Y4M header from the reference
        $(head -n 1 $FILE > $BASENAME.y4m)
        $(tail -n+2 $BASENAME-$$-out.y4m >> $BASENAME.y4m)
        rm $BASENAME-$$.y4m $BASENAME-$$-out.y4m
      fi
      ;;
  esac
  ;;
vvc-vtm | vvc-vtm-ra | vvc-vtm-ra-ctc | vvc-vtm-ra-st | vvc-vtm-as-ctc | vvc-vtm-ld | vvc-vtm-ai)
  case $CODEC in
   vvc-vtm-ra | vvc-vtm-ra-st)
     # VVC_CTC says IntraPeriod should be different for different FPS, *shrug*
     VVC_CFG=$WORK_ROOT/rd_tool/cfg/vvc-vtm/encoder_randomaccess_vtm.cfg
     INTRA_PERIOD=32
     case $FPS in
      20 | 24 | 30)
        INTRA_PERIOD=32
      ;;
      50 | 60)
        INTRA_PERIOD=64
      ;;
      100)
        INTRA_PERIOD=100
      ;;
      esac
      CTC_PROFILE_OPTS+=" --IntraPeriod=$INTRA_PERIOD "
     ;;
   vvc-vtm-ra-ctc | vvc-vtm-as-ctc)
     VVC_CFG=$WORK_ROOT/rd_tool/cfg/vvc-vtm/encoder_randomaccess_vtm_gop16.cfg
     ;;
   vvc-vtm-ld)
      VVC_CFG=$WORK_ROOT/rd_tool/cfg/vvc-vtm/encoder_lowdelay_vtm.cfg
      ;;
   vvc-vtm-ai)
      VVC_CFG=$WORK_ROOT/rd_tool/cfg/vvc-vtm/encoder_intra_vtm.cfg
      ;;
    vvc-vtm)
      VVC_CFG=''
      ;;
  esac
  FPS_NUM=$(grep -o -a -m 1 -P "(?<=F)([0-9]+)(?=:[0-9]+)" "$FILE")
  FPS_DEN=$(grep -o -a -m 1 -P "(?<=F$FPS_NUM:)([0-9]+)" "$FILE")
  FPS=$(bc <<< 'scale=3; '$FPS_NUM' / '$FPS_DEN'')
  # Enbale Tiling explictly for >=4K
  if [ $((WIDTH)) -ge 3840 ] && [ $((HEIGHT)) -ge 2160 ]; then
    CTC_PROFILE_OPTS+="  --EnablePicPartitioning=1 --TileColumnWidthArray=15"
  else
    CTC_PROFILE_OPTS+=" "
  fi
  # TODO: Remove this hack if the upstream fixes 420mpeg2 handling
  # Reference: https://jvet.hhi.fraunhofer.de/trac/vvc/ticket/1598
  # Convert Y4M to YUV for certain 420mpeg2 videos in VVC
  if [[ $CHROMA == "C420mpeg2" ]]; then
    $Y4M2YUV $FILE -o ${BASENAME}_src.yuv
    INPUT_SRC_VID=${BASENAME}_src.yuv
  else
    INPUT_SRC_VID=$FILE
  fi
  # Encode video
  case $CODEC in
    vvc-vtm-ra)
      # this is intentionally not a separate script as only metrics_gather.sh is
      # sent to workers
      # VVC parCat requires perfect constructed GOP to concat, so we are always
      # overriding the $EXTRA_OPTIONS wrt GOP Struct.
      echo "#!/bin/bash" > /tmp/enc$$.sh
      echo "TIMER='time -v --output='enctime$$-\$1.out" >> /tmp/enc$$.sh
      echo "case \$1 in FramesToBeEncoded) GOP_PARAMS=\"--\$1=65\";; FrameSkip) GOP_PARAMS=\" --FramesToBeEncoded=65 --\$1=65 \" ;; esac" >> /tmp/enc$$.sh
      echo "RUN='$VVCENC -i $INPUT_SRC_VID -c $VVC_CFG --SourceWidth=$WIDTH --SourceHeight=$HEIGHT --FrameRate=$FPS --InputBitDepth=$DEPTH --FramesToBeEncoded=130 --QP=$x $CTC_PROFILE_OPTS --ReconFile=${BASENAME}-'\$1'-rec.yuv -b $BASENAME-'\$1'.bin $cd '" >> /tmp/enc$$.sh
      echo "\$(\$TIMER \$RUN \$GOP_PARAMS > $BASENAME$$-stdout.txt)" >> /tmp/enc$$.sh
      chmod +x /tmp/enc$$.sh
      for s in {FramesToBeEncoded,FrameSkip}; do printf "$s\0"; done | xargs -0 -n1 -P2 /tmp/enc$$.sh
      # parcat is tool by VTM for concating files as per JVET-B0036
      $($VVCCAT $BASENAME-FramesToBeEncoded.bin $BASENAME-FrameSkip.bin $BASENAME.bin)
      TIME1=$(cat enctime$$-FramesToBeEncoded.out | grep User | cut -d\  -f4)
      TIME2=$(cat enctime$$-FrameSkip.out | grep User | cut -d\  -f4)
      ENCTIME=$(awk "BEGIN {print $TIME1+$TIME2; exit}")
      rm -f /tmp/enc$$.sh enctime$$-FramesToBeEncoded.out enctime$$-FrameSkip.out $BASENAME-FramesToBeEncoded.bin $BASENAME-FrameSkip.bin
      ;;
    vvc-vtm-ra-ctc | vvc-vtm-as-ctc)
      # this is intentionally not a separate script as only metrics_gather.sh is
      # sent to workers
      echo "#!/bin/bash" > /tmp/enc$$.sh
      echo "PERF_ENC_OUT='${BASENAME}'-encperf-\$1.out" >> /tmp/enc$$.sh
      echo "PERF_ENC_STAT='perf stat -o '\${PERF_ENC_OUT}''" >> /tmp/enc$$.sh
      echo "TIMER=''\${PERF_ENC_STAT}' time -v --output='enctime$$-\$1.out" >> /tmp/enc$$.sh
      echo "case \$1 in FramesToBeEncoded) GOP_PARAMS=\"--\$1=65\";; FrameSkip) GOP_PARAMS=\" --FramesToBeEncoded=65 --\$1=65 \" ;; esac" >> /tmp/enc$$.sh
      echo "RUN='$VVCENC -i $INPUT_SRC_VID -c $VVC_CFG --SourceWidth=$WIDTH --SourceHeight=$HEIGHT --FrameRate=$FPS --InputBitDepth=$DEPTH --FramesToBeEncoded=130 --QP=$x $CTC_PROFILE_OPTS --ReconFile=${BASENAME}-'\$1'-rec.yuv -b $BASENAME-'\$1'.bin $EXTRA_OPTIONS '" >> /tmp/enc$$.sh
      # Force config to be Closed-GOP (IDR) with only 1 I Frame
      CTC_PARAMS="--DecodingRefreshType=2 --IntraPeriod=-1"
      echo "CTC_PARAMS=\" $CTC_PARAMS \" " >> /tmp/enc$$.sh
      echo "\$(\$TIMER \$RUN \$GOP_PARAMS \$CTC_PARAMS > $BASENAME$$-\$1-stdout.txt) " >> /tmp/enc$$.sh
      chmod +x /tmp/enc$$.sh
      for s in {FramesToBeEncoded,FrameSkip}; do printf "$s\0"; done | xargs -0 -n1 -P2 /tmp/enc$$.sh
      # do classic concat as it is IDR
      $(cat $BASENAME-FramesToBeEncoded.bin $BASENAME-FrameSkip.bin > $BASENAME.bin)
      $(cat $BASENAME$$-FramesToBeEncoded-stdout.txt $BASENAME$$-FrameSkip-stdout.txt > $BASENAME-stdout.txt)
      $(cat enctime$$-FramesToBeEncoded.out enctime$$-FrameSkip.out > $BASENAME-enctime.out)
      $(cat ${BASENAME}-encperf-FramesToBeEncoded.out ${BASENAME}-encperf-FrameSkip.out > $BASENAME-encperf.out)
      TIME1=$(cat enctime$$-FramesToBeEncoded.out | grep User | cut -d\  -f4)
      TIME2=$(cat enctime$$-FrameSkip.out | grep User | cut -d\  -f4)
      PERF_ENC_INSTR_CNT1=$(awk '/instructions/ { s=$1 } END { gsub(",", "", s) ; print s }' ${BASENAME}-encperf-FramesToBeEncoded.out)
      PERF_ENC_INSTR_CNT2=$(awk '/instructions/ { s=$1 } END { gsub(",", "", s) ; print s }' ${BASENAME}-encperf-FrameSkip.out)
      PERF_ENC_CYCLE_CNT1=$(awk '/cycles/ { s=$1 } END { gsub(",", "", s) ; print s }' ${BASENAME}-encperf-FramesToBeEncoded.out)
      PERF_ENC_CYCLE_CNT2=$(awk '/cycles/ { s=$1 } END { gsub(",", "", s) ; print s }' ${BASENAME}-encperf-FrameSkip.out)
      ENCTIME=$(awk "BEGIN {print $TIME1+$TIME2; exit}")
      PERF_ENC_INSTR_CNT=$(awk "BEGIN {print $PERF_ENC_INSTR_CNT1+$PERF_ENC_INSTR_CNT2; exit}")
      PERF_ENC_CYCLE_CNT=$(awk "BEGIN {print $PERF_ENC_CYCLE_CNT1+$PERF_ENC_CYCLE_CNT2; exit}")
      rm -f /tmp/enc$$.sh enctime$$-FramesToBeEncoded.out enctime$$-FrameSkip.out $BASENAME-FramesToBeEncoded.bin $BASENAME-FrameSkip.bin
      ;;
    *)
      $($TIMER $VVCENC -i $INPUT_SRC_VID -c $VVC_CFG --SourceWidth=$WIDTH --SourceHeight=$HEIGHT --FrameRate=$FPS --InputBitDepth=$DEPTH --FramesToBeEncoded=130 --QP=$x $CTC_PROFILE_OPTS -b $BASENAME.bin --ReconFile=${BASENAME}-rec.yuv  $EXTRA_OPTIONS > "$BASENAME-stdout.txt")
      ;;
  esac
  # Decode the video
  $($TIMERDEC $VVCDEC -b $BASENAME.bin -d $DEPTH -o $BASENAME.yuv > "$BASENAME-dec.txt")
  # Convert the YUV file to Y4M file.
  # YUV2YUV4MPEG of daala_tool takes headers as args and filename without *.yuv*
  # extension
  $YUV2YUV4MPEG $BASENAME  -an1 -ad1 -w$WIDTH -h$HEIGHT -fn$FPS_NUM -fd$FPS_DEN -c$YUV_CHROMA -b$DEPTH
  SIZE=$(stat -c %s $BASENAME.bin)
  ENC_EXT='.bin'
  case $CODEC in
    vvc-vtm-as-ctc)
      if [ $((WIDTH)) -ne 3840 ] && [ $((HEIGHT)) -ne 2160 ]; then
        # change the reference to 3840x2160
        FILE=$(sed -e 's/\(640x360\|960x540\|1280x720\|1920x1080\|2560x1440\)/3840x2160/' <<< $FILE)
        # hack to force input Y4M file to F30:1 because HDRConvert requires specifying an output frame rate, and if they do not match it will resample temporaly
        echo "YUV4MPEG2 W$WIDTH H$HEIGHT F30:1 $CHROMA" > $BASENAME-$$.y4m
        $(tail -n+2 $BASENAME.y4m >> $BASENAME-$$.y4m)
        # upsample decoded output to 3840x2160
        $HDRCONVERT -p SourceFile=$BASENAME-$$.y4m -p OutputFile=$BASENAME-$$-out.y4m -p OutputWidth=3840 -p OutputHeight=2160 -p OutputChromaFormat=1 -p OutputBitDepthCmp0=10 -p OutputBitDepthCmp1=10 -p OutputBitDepthCmp2=10 -p OutputColorSpace=0 -p OutputColorPrimaries=0 -p OutputTransferFunction=12 -p SilentMode=1 -p ScaleOnly=1 -p ScalingMode=12 -p OutputRate=30 -p NumberOfFrames=130 1>&2
        # replace decoded output with upsampled file using Y4M header from the reference
        $(head -n 1 $FILE > $BASENAME.y4m)
        $(tail -n+2 $BASENAME-$$-out.y4m >> $BASENAME.y4m)
        rm $BASENAME-$$.y4m $BASENAME-$$-out.y4m
      fi
      ;;
  esac
;;
thor)
  $($TIMER $THORENC -qp $x -cf "$THORDIR/config_HDB16_high_efficiency.txt" -if $FILE -of $BASENAME.thor $EXTRA_OPTIONS > $BASENAME-enc.out)
  SIZE=$(stat -c %s $BASENAME.thor)
  ENC_EXT='.thor'
  # using reconstruction is currently broken with HDB
  $THORDEC $BASENAME.thor $BASENAME.yuv > "$BASENAME-stdout.txt"
  $YUV2YUV4MPEG $BASENAME -an1 -ad1 -w$WIDTH -h$HEIGHT
  ;;
thor-rt)
  $($TIMER $THORENC -qp $x -cf "$THORDIR/config_LDB_high_efficiency.txt" -if $FILE -of $BASENAME.thor -rf $BASENAME.y4m $EXTRA_OPTIONS > $BASENAME-enc.out)
  SIZE=$(stat -c %s $BASENAME.thor)
  ENC_EXT='.thor'
  ;;
rav1e)
  $($TIMER $RAV1E $FILE --quantizer $x -o $BASENAME.ivf -r $BASENAME-rec.y4m --threads 1 $EXTRA_OPTIONS > $BASENAME-enc.out)
  if hash dav1d 2>/dev/null; then
    $($TIMERDEC dav1d -q -i $BASENAME.ivf -o $BASENAME.y4m) || (echo "Corrupt bitstream detected!"; exit 98)
  elif hash aomdec 2>/dev/null; then
    $($TIMERDEC aomdec --codec=av1 $AOMDEC_OPTS -o $BASENAME.y4m $BASENAME.ivf) || (echo "Corrupt bitstream detected!"; exit 98)
  else
    echo "AV1 decoder not found, desync/corruption detection disabled." >&2
  fi

  if [ -f $BASENAME.y4m ]; then
    "$Y4M2YUV" "$BASENAME-rec.y4m" -o rec.yuv
    "$Y4M2YUV" "$BASENAME.y4m" -o enc.yuv
    cmp --silent rec.yuv enc.yuv || (echo "Reconstruction differs from output!"; rm -f rec.yuv enc.yuv "$BASENAME-rec.y4m"; exit 98)
    rm -f rec.yuv enc.yuv "$BASENAME-rec.y4m"
  else
    mv "$BASENAME-rec.y4m" "$BASENAME.y4m"
  fi
  SIZE=$(stat -c %s $BASENAME.ivf)
  ENC_EXT='.ivf'
  ;;
svt-av1 | svt-av1-ra | svt-av1-ra-crf | svt-av1-ra-vbr | svt-av1-ra-vbr-2p | svt-av1-ld-cbr | svt-av1-ra-cq | svt-av1-as | svt-av1-as-ctc)
  case $CODEC in
    # 1-pass CQ, CTC Style Preset
    svt-av1-ra)
      SVT_PROFILE_OPTS="--preset 0 --passes 1 --hierarchical-levels 4 --frames 130 --keyint 65 --aq-mode 0 --rc 0 --qp $x"
      ;;
    # 1-pass CRF RA
    svt-av1-ra-crf)
      SVT_PROFILE_OPTS="--lp 1 --passes 1 --rc 0 --crf $x --pred-struct 2"
      ;;
    # 1-pass VBR RA
    svt-av1-ra-vbr)
      SVT_PROFILE_OPTS="--lp 1 --passes 1 --rc 1 --tbr $x --pred-struct 2"
      ;;
    # 2-pass VBR RA
    svt-av1-ra-vbr-2p)
      SVT_PROFILE_OPTS="--lp 1 --passes 2 --rc 1 --tbr $x --pred-struct 2"
      ;;
    # 1-pass CBR LD, RTC Mode
    svt-av1-ld-cbr)
      SVT_PROFILE_OPTS="--lp 1 --passes 1 --rc 2 --tbr $x --pred-struct 1"
      ;;
    # 1-pass CQP RA
    svt-av1-ra-cq)
      SVT_PROFILE_OPTS="--lp 1 --passes 1 --rc 0 --aq-mode 0 --crf $x --pred-struct 2 --keyint 999"
      ;;
     # 1-pass SIWG-CTC AS
    svt-av1-as | svt-av1-as-ctc)
      SVT_PROFILE_OPTS="--lp 1 --passes 1 --keyint -1 --crf $x"
      ;;
    svt-av1)
      # Always define CRF points for the given QPs
      SVT_PROFILE_OPTS="--lp 1 --crf $x "
      ;;
  esac
  # Encode the video
  $($TIMER $SVTAV1 -i $FILE $SVT_PROFILE_OPTS -b $BASENAME.ivf $EXTRA_OPTIONS > $BASENAME-stdout.txt 2>&1)
  # Decode the video
  if hash dav1d 2>/dev/null; then
    $($TIMERDEC dav1d -q -i $BASENAME.ivf -o $BASENAME.y4m) || (echo "Corrupt bitstream detected!"; exit 98)
  elif hash aomdec 2>/dev/null; then
    $($TIMERDEC aomdec --codec=av1 $AOMDEC_OPTS -o $BASENAME.y4m $BASENAME.ivf) || (echo "Corrupt bitstream detected!"; exit 98)
  else
    echo "AV1 decoder not found, desync/corruption detection disabled." >&2
  fi
  SIZE=$(stat -c %s $BASENAME.ivf)
  ENC_EXT='.ivf'
  # Upscale to 1080p and compute metrics for svt-av1-as
  # Depends on custom-ffmpeg binary
  case $CODEC in
    svt-av1-as | svt-av1-as-ctc)
      if [ $((WIDTH)) -ne 1920 ] && [ $((HEIGHT)) -ne 1080 ]; then
      # Change source file to be 1080p
      FILE=$(sed -e 's/\(to256x144_lanc\|to384x216_lanc\|to512x288_lanc\|to640x360_lanc\|to768x432_lanc\|to960x540_lanc\|to1280x720_lanc\)//' <<< $FILE)
      fi
      # Use FFmpeg to  upscale and compute reduced-libvmaf as they are fast
      # When measured the process can be very fast, we are talking ~3fps over
      # ~0.8fps
      # Reduced-libvmaf: LIBVMAF - {CIEDE2000, MS-SSIM, CAMBI, PSNR_HVS}
      ffmpeg -hide_banner -loglevel error -threads 1 -y -nostdin -r 25 -i $BASENAME.y4m  -r 25 -i $FILE -lavfi '[0:v]scale=1920x1080:flags=lanczos+accurate_rnd+full_chroma_int:sws_dither=none:param0=5[main];[main][1:v]libvmaf=aom_ctc=1:log_path='$BASENAME-vmaf.xml':log_fmt=xml' -f null -
      ;;
  esac
  ;;
esac

#rename core dumps to prevent more than 1 per slot on disk
mv core.* core 2>/dev/null || true

if [ -f "$VMAF" ]; then
  case $CODEC in
    svt-av1-as | svt-av1-as-ctc)
    # Reduced-Libvmaf: Handle missing metrics at the computation side to make
    # life easier.
    line_to_append+='\    '
    line_to_append+='<metric name="ciede2000" min="0.0" max="0.0" mean="0.0"  harmonic_mean="0.0" />'
    line_to_append+='\n    '
    line_to_append+='<metric name="float_ms_ssim" min="0.0" max="0.0" mean="0.0" harmonic_mean="0.0" />'
    line_to_append+='\n    '
    line_to_append+='<metric name="psnr_hvs_y" min="0.0" max="0.0" mean="0.0" harmonic_mean="0.0" />'
    line_to_append+='\n    '
    line_to_append+='<metric name="psnr_hvs_cb" min="0.0" max="0.0" mean="0.0" harmonic_mean="0.0" />'
    line_to_append+='\n    '
    line_to_append+='<metric name="psnr_hvs_cr" min="0.0" max="0.0" mean="0.0" harmonic_mean="0.0" />'
    line_to_append+='\n    '
    line_to_append+='<metric name="psnr_hvs" min="0.0" max="0.0" mean="0.0" harmonic_mean="0.0" />'
    line_to_append+='\n    '
    line_to_append+='<metric name="cambi" min="0.0" max="0.0" mean="0.0" harmonic_mean="0.0" />'

    # Count lines and insert from 5 rows from end of the file using sed
    total_lines=$(wc -l < "$BASENAME-vmaf.xml")
    line_number=$((total_lines - 5))
    sed -i "${line_number}a${line_to_append}" "$BASENAME-vmaf.xml"
    ;;
    *)
    "$VMAF" -r "$FILE" -d "$BASENAME.y4m" --aom_ctc v6.0 --xml -o "$BASENAME-vmaf.xml" --thread 1 | tail -n 1
    ;;
    esac
  FRAMES=$(cat "$BASENAME-vmaf.xml" | grep "frame frameNum" | wc -l)
  PSNR="Total: 0 (Y': 0 Cb: 0 Cr: 0 )"
else
  "$DUMP_PSNR" -a "$FILE" "$BASENAME.y4m" > "$BASENAME-psnr.out"
  FRAMES=$(cat "$BASENAME-psnr.out" | grep ^0 | wc -l)
  PSNR=$(cat "$BASENAME-psnr.out" | grep Total)
fi

PIXELS=$(($WIDTH*$HEIGHT*$FRAMES))

echo "$x" "$PIXELS" "$SIZE"


echo "$PSNR"

APSNR="Frame-averaged: 0 (Y': 0 Cb: 0 Cr: 0 )" #$(cat "$BASENAME-psnr.out" | grep Frame-averaged)
PSNRHVS="Total: 0 (Y': 0 Cb: 0 Cr: 0 )" #$("$DUMP_PSNRHVS" "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)

echo "$PSNRHVS"

SSIM="Total: 0 (Y': 0 Cb: 0 Cr: 0 )" #$("$DUMP_SSIM" "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)

echo "$SSIM"

FASTSSIM="Total: 0 (Y': 0 Cb: 0 Cr: 0 )" #$("$DUMP_FASTSSIM" -c "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)

echo "$FASTSSIM"

CIEDE="0 0" #$("$DUMP_CIEDE" --threads 1 "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)

echo "$CIEDE"

echo "$APSNR"

MSSSIM="Total: 0 (Y': 0 Cb: 0 Cr: 0 )" #$("$DUMP_MSSSIM" "$FILE" "$BASENAME.y4m" 2> /dev/null | grep Total)

echo "$MSSSIM"

if [ -e "$TIMEROUT" ]; then
  ENCTIME=$(awk '/User/ { s=$4 } END { printf "%.2f", s }' "$TIMEROUT")
else
  if [ -z "$ENCTIME" ]; then
    ENCTIME=0
  fi
fi

echo "$ENCTIME"

echo "0" # Dummy placeholder for vmaf_old in the output

if [ -e "$TIMERDECOUT" ]; then
  DECTIME=$(awk '/User/ { s=$4 } END { printf "%.2f", s }' "$TIMERDECOUT")
else
  DECTIME=0
fi

echo "$DECTIME"

# Extract MD5 of encoded file
ENC_FILE=${BASENAME}${ENC_EXT}
MD5SUM=($(md5sum $ENC_FILE))
echo $MD5SUM

# Extract Encoding Instruction count and cycles for Parallel-GOP cases
if ! [[ "$CODEC" =~ ^(av2-ra|av2-as|vvc-vtm-ra|vvc-vtm-as|vvc-vtm-ra-ctc| vvc-vtm-as-ctc)$ ]]; then
  if [ -e "$PERF_ENC_OUT" ]; then
    PERF_ENC_INSTR_CNT=$(awk '/instructions/ { s=$1 } END { gsub(",", "", s) ; print s }' "$PERF_ENC_OUT")
    PERF_ENC_CYCLE_CNT=$(awk '/cycles/ { s=$1 } END { gsub(",", "", s) ; print s }' "$PERF_ENC_OUT")
  else
    if [ -z "$PERF_ENC_INSTR_CNT" ]; then
    PERF_ENC_INSTR_CNT=0
    fi
    if [ -z "$PERF_ENC_CYCLE_CNT" ]; then
      PERF_ENC_CYCLE_CNT=0
    fi
  fi
# Default to 0 if instr/cycle count is not available for Parallel-GOP cases
else
  if [ -z "$PERF_ENC_INSTR_CNT" ]; then
    PERF_ENC_INSTR_CNT=0
  fi
  if [ -z "$PERF_ENC_CYCLE_CNT" ]; then
    PERF_ENC_CYCLE_CNT=0
  fi
fi

# Extract Decoding Instruction count and cycles
if [ -e "$PERF_DEC_OUT" ]; then
  PERF_DEC_INSTR_CNT=$(awk '/instructions/ { s=$1 } END { gsub(",", "", s) ; print s }' "$PERF_DEC_OUT")
  PERF_DEC_CYCLE_CNT=$(awk '/cycles/ { s=$1 } END { gsub(",", "", s) ; print s }' "$PERF_DEC_OUT")
else
  if [ -z "$PERF_DEC_INSTR_CNT" ]; then
    PERF_DEC_INSTR_CNT=0
  fi
  if [ -z "$PERF_DEC_CYCLE_CNT" ]; then
    PERF_DEC_CYCLE_CNT=0
  fi
fi

echo $PERF_ENC_INSTR_CNT
echo $PERF_ENC_CYCLE_CNT
echo $PERF_DEC_INSTR_CNT
echo $PERF_DEC_CYCLE_CNT

if [ -f "$VMAF" ]; then
  cat "$BASENAME-vmaf.xml"
  rm "$BASENAME-vmaf.xml"
fi

if [ ! "$NO_DELETE" ]; then
  rm -f "$BASENAME.ogv" "$BASENAME.x264" "$BASENAME.x265" "$BASENAME.xvc" "$BASENAME.vpx" "$BASENAME.ivf" "$TIMEROUT" "$BASENAME-enc.out" "$BASENAME-psnr.out" "$BASENAME.thor" 2> /dev/null
fi

rm -f "$BASENAME.y4m" "$BASENAME.yuv" "$BASENAME-rec.y4m" ${BASENAME}_src.yuv  ${BASENAME}-rec.yuv ${BASENAME}-FrameSkip-rec.yuv ${BASENAME}-FramesToBeEncoded-rec.yuv 2> /dev/null

rm -f pid

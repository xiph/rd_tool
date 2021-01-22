#!/bin/bash

if [ $# == 0 ]; then
  echo "usage: OUTPUT=<label> $0 *.out"
  exit 1
fi

TOTAL=total.out

if [ -n "$OUTPUT" ]; then
  TOTAL="$OUTPUT.out"
fi

if [ -e "$TOTAL" ]; then
  echo "ERROR: $TOTAL already exists and will be included in average, please remove it first"
  exit 1
fi

awk '{size[$1]+=$2;bytes[$1]+=$3;psnr[$1]+=$2*$4;psnrhvs[$1]+=$2*$5;ssim[$1]+=$2*$6;fastssim[$1]+=$2*$7;ciede[$1]+=$2*$8;psnrcb[$1]+=$2*$9;psnrcr[$1]+=$2*$10;apsnr[$1]+=$2*$11;apsnrcb[$1]+=$2*$12;apsnrcr[$1]+=$2*$13;msssim[$1]+=$2*$14;encodetime[$1]+=$2*$15;vmaf[$1]+=$2*$16;decodetime[$1]+=$2*$17;psnr_libvmaf[$1]+=$2*$18;psnrcb_libvmaf[$1]+=$2*$19;psnrcr_libvmaf[$1]+=$2*$20;ciede2000_libvmaf[$1]+=$2*$21;ssim_libvmaf[$1]+=$2*$22;msssim_libvmaf[$1]+=$2*$23;psnrhvsy_libvmaf[$1]+=$2*$24;psnrhvscb_libvmaf[$1]+=$2*$25;psnrhvscr_libvmaf[$1]+=$2*$26;psnrhvs_libvmaf[$1]+=$2*$27;vmaf_libvmaf[$1]+=$2*$28;vmafneg_libvmaf[$1]+=$2*$29;}END{for(i in size)print i,size[i],bytes[i],psnr[i]/size[i],psnrhvs[i]/size[i],ssim[i]/size[i],fastssim[i]/size[i],ciede[i]/size[i],psnrcb[i]/size[i],psnrcr[i]/size[i],apsnr[i]/size[i],apsnrcb[i]/size[i],apsnrcr[i]/size[i],msssim[i]/size[i],encodetime[i]/size[i],vmaf[i]/size[i],decodetime[i]/size[i],psnr_libvmaf[i]/size[i],psnrcb_libvmaf[i]/size[i],psnrcr_libvmaf[i]/size[i],ciede2000_libvmaf[i]/size[i],ssim_libvmaf[i]/size[i],msssim_libvmaf[i]/size[i],psnrhvsy_libvmaf[i]/size[i],psnrhvscb_libvmaf[i]/size[i],psnrhvscr_libvmaf[i]/size[i],psnrhvs_libvmaf[i]/size[i],vmaf_libvmaf[i]/size[i],vmafneg_libvmaf[i]/size[i];}' $@ | sort -n > $TOTAL

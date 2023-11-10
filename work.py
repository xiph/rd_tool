from utility import *
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
import time
import re

runs_dst_dir = os.getenv("RUNS_DST_DIR", os.path.join(os.getcwd(), "../runs"))
media_src_dir = os.getenv("MEDIAS_SRC_DIR", os.path.join(os.getcwd(), "/media"))

# Finding files such as `this_(that)` requires `'` be placed on both
# sides of the quote so the `()` are both captured. Files such as
# `du_Parterre_d'Eau` must be converted into
#`'du_Parterre_d'"'"'Eau'
#                ^^^ Required to make sure the `'` is captured.
def shellquote(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"

#set up Codec:QualityRange dictionary
quality_presets = {
    "daala": [7,11,16,25,37],
    "x264": list(range(1,52,5)),
    "x265": list(range(5,52,5)),
    "x265-rt": list(range(5,52,5)),
    "xvc": [20,25,30,35,40],
    "vp8": list(range(12,64,5)),
    "vp9": [20,32,43,55,63],
    "vp9-rt": [20,32,43,55,63],
    "vp10": [8,20,32,43,55,63],
    "vp10-rt": [8,20,32,43,55,63],
    "av1": [20,32,43,55,63],
    "av1-rt": [20,32,43,55,63],
    "av2-ai": [85, 110, 135, 160, 185, 210],
    "av2-ra": [110, 135, 160, 185, 210, 235],
    "av2-ra-st": [110, 135, 160, 185, 210, 235],
    "av2-ld": [110, 135, 160, 185, 210, 235],
    "av2-as": [110, 135, 160, 185, 210, 235],
    "av2-as-st": [110, 135, 160, 185, 210, 235],
    "av2-f" : [60, 85, 110, 135, 160, 185],
    "thor": list(range(7,43,3)),
    "thor-rt": list(range(7,43,3)),
    "rav1e": [20*4,32*4,43*4,55*4,63*4],
    "svt-av1": [27, 33, 39, 46, 52, 58],
    "svt-av1-ra": [27, 33, 39, 46, 52, 58],
    "svt-av1-ra-crf": [27, 33, 39, 46, 52, 58],
    "svt-av1-ra-vbr": [250, 500, 1000, 4000, 8000, 12000],
    "svt-av1-ra-vbr-2p": [250, 500, 1000, 4000, 8000, 12000],
    "svt-av1-ld-cbr": [250, 500, 1000, 4000, 8000, 12000],
    "svt-av1-ra-cq": [27, 33, 39, 46, 52, 58],
    "svt-av1-as": [27, 33, 39, 46, 52, 58],
    "vvc-vtm": [22, 27, 32, 37],
    "vvc-vtm-ra": [22, 27, 32, 37],
    "vvc-vtm-ra-ctc": [22, 27, 32, 37, 42, 47],
    "vvc-vtm-as-ctc": [22, 27, 32, 37, 42, 47],
    "vvc-vtm-ra-st": [22, 27, 32, 37],
    "vvc-vtm-ld": [22, 27, 32, 37],
    "vvc-vtm-ai": [22, 27, 32, 37],
}

class Run:
    def __init__(self, codec):
        self.info = {}
        self.codec = codec
        self.quality = quality_presets[codec]
        self.runid = get_time()
        self.extra_options = ''
        self.save_encode = False
        self.work_items = []
        self.prefix = './'
        self.log = None
        self.rundir = None
        self.status = 'running'
        self.work_items = []
        self.cancelled = False
        self.nightly_run = False
        self.ctc_version = 5.0
    def write_status(self):
        f = open(self.rundir+'/status.txt','w')
        f.write(self.status)
        f.close()
    def cancel(self):
        self.status = 'cancelled'
        self.write_status()
        self.cancelled = True
        for work in self.work_items:
            work.cancel()
    def finish(self):
        if self.log:
            self.log.close()

class RDRun(Run):
    def reduce(self):
        rd_print(self.log,'Logging results...')
        self.work_items.sort(key=lambda work: int(work.quality))
        any_work_failed = False
        for work in self.work_items:
            if not work.failed:
                pass
            else:
                any_work_failed = True
        subprocess.call('OUTPUT="'+self.prefix+'/'+'total" "'+sys.path[0]+'/rd_average.sh" "'+self.prefix+'/*-daala.out"',
          shell=True)
        if any_work_failed:
            self.status = 'failed'
        else:
            self.status = 'completed'
        self.write_status()

class ABRun(Run):
    def reduce(self):
        pass

class Work:
    def __init__(self):
        self.run = None
        self.log = None
        self.retries = 0
        self.done = False
        self.failed = False
        self.runid = ''
        self.slot = None
        self.workid = ''
        self.nightly_run = False
        self.multislots = False
    def cancel(self):
        self.failed = True
        self.done = True

class RDWork(Work):
    def __init__(self):
        super().__init__()
        self.no_delete = False
        self.copy_back_files = ['-stdout.txt', '-enctime.out', '-dectime.out', '-encperf.out', '-decperf.out']
        self.ctc_class = ''
        self.ctc_version = 5.0
    def parse(self, stdout, stderr):
        self.raw = stdout
        split = None
        try:
            split = self.raw.decode('utf-8').replace(')',' ').split(maxsplit=61)
            self.pixels = split[1]
            self.size = split[2]
            self.metric = {}
            self.metric['psnr'] = {}
            self.metric["psnr"][0] = split[6]
            self.metric["psnr"][1] = split[8]
            self.metric["psnr"][2] = split[10]
            self.metric['psnrhvs'] = {}
            self.metric["psnrhvs"][0] = split[14]
            self.metric["psnrhvs"][1] = split[16]
            self.metric["psnrhvs"][2] = split[18]
            self.metric['ssim'] = {}
            self.metric["ssim"][0] = split[22]
            self.metric["ssim"][1] = split[24]
            self.metric["ssim"][2] = split[26]
            self.metric['fastssim'] = {}
            self.metric["fastssim"][0] = split[30]
            self.metric["fastssim"][1] = split[32]
            self.metric["fastssim"][2] = split[34]
            self.metric['ciede2000'] = split[36]
            self.metric['apsnr'] = {}
            self.metric['apsnr'][0] = split[40]
            self.metric['apsnr'][1] = split[42]
            self.metric['apsnr'][2] = split[44]
            self.metric['msssim'] = {}
            self.metric['msssim'][0] = split[48]
            self.metric['msssim'][1] = split[50]
            self.metric['msssim'][2] = split[52]
            self.metric['encodetime'] = split[53]
            self.metric['vmaf_old'] = split[54]
            self.metric['decodetime'] = split[55]
            self.metric['enc_md5'] = split[56]
            self.metric['enc_instr_cnt'] = split[57]
            self.metric['enc_cycle_cnt'] = split[58]
            self.metric['dec_instr_cnt'] = split[59]
            self.metric['dec_cycle_cnt'] = split[60]
            self.vmaf_xml = split[61]
            root = ET.fromstring(self.vmaf_xml)
            for metric_name in ['psnr_y', 'psnr_cb', 'psnr_cr', 'ciede2000', 'float_ssim', 'float_ms_ssim', 'psnr_hvs_y', 'psnr_hvs_cb', 'psnr_hvs_cr', 'psnr_hvs', 'cambi']:
                self.metric['vmaf_'+metric_name] = root.find("pooled_metrics/metric[@name='"+metric_name+"']").get('mean')
            self.metric['vmaf'] = root.find("pooled_metrics/metric[@name='vmaf']").get('mean')
            self.metric['vmaf_neg'] = root.find("pooled_metrics/metric[@name='vmaf_neg']").get('mean')
            for metric_name in ['apsnr_y', 'apsnr_cb', 'apsnr_cr']:
                self.metric['vmaf_'+metric_name] = root.find("aggregate_metrics").get(metric_name)
            self.failed = False
        except (IndexError, ET.ParseError):
            rd_print(self.log,'Decoding result for '+self.filename+' at quality '+str(self.quality)+' failed!')
            rd_print(self.log,'stdout:')
            rd_print(self.log,stdout.decode('utf-8'))
            rd_print(self.log,'stderr:')
            rd_print(self.log,stderr.decode('utf-8'))
            self.failed = True
    def get_line(self):
        work = self
        f = ''
        f += (str(work.quality)+' ')
        f += (str(work.pixels)+' ')
        f += (str(work.size)+' ')
        f += (str(work.metric['psnr'][0])+' ')
        f += (str(work.metric['psnrhvs'][0])+' ')
        f += (str(work.metric['ssim'][0])+' ')
        f += (str(work.metric['fastssim'][0])+' ')
        f += (str(work.metric['ciede2000'])+' ')
        f += (str(work.metric['psnr'][1])+' ')
        f += (str(work.metric['psnr'][2])+' ')
        f += (str(work.metric['apsnr'][0])+' ')
        f += (str(work.metric['apsnr'][1])+' ')
        f += (str(work.metric['apsnr'][2])+' ')
        f += (str(work.metric['msssim'][0])+' ')
        f += (str(work.metric['encodetime'])+' ')
        f += (str(work.metric['vmaf_old'])+' ')
        f += (str(work.metric['decodetime'])+' ')
        f += (str(work.metric['vmaf_psnr_y'])+' ')
        f += (str(work.metric['vmaf_psnr_cb'])+' ')
        f += (str(work.metric['vmaf_psnr_cr'])+' ')
        f += (str(work.metric['vmaf_ciede2000'])+' ')
        f += (str(work.metric['vmaf_float_ssim'])+' ')
        f += (str(work.metric['vmaf_float_ms_ssim'])+' ')
        f += (str(work.metric['vmaf_psnr_hvs_y'])+' ')
        f += (str(work.metric['vmaf_psnr_hvs_cb'])+' ')
        f += (str(work.metric['vmaf_psnr_hvs_cr'])+' ')
        f += (str(work.metric['vmaf_psnr_hvs'])+' ')
        f += (str(work.metric['vmaf'])+' ')
        f += (str(work.metric['vmaf_neg'])+' ')
        f += (str(work.metric['vmaf_apsnr_y'])+' ')
        f += (str(work.metric['vmaf_apsnr_cb'])+' ')
        f += (str(work.metric['vmaf_apsnr_cr'])+' ')
        f += (str(work.metric['vmaf_cambi'])+' ')
        f += (str(work.metric['enc_md5'])+' ')
        f += (str(work.metric['enc_instr_cnt'])+' ')
        f += (str(work.metric['enc_cycle_cnt'])+' ')
        f += (str(work.metric['dec_instr_cnt'])+' ')
        f += (str(work.metric['dec_cycle_cnt'])+' ')
        f += ('\n')
        return f
    def execute(self):
        try:
            slot = self.slot
            slot.setup(self.codec,self.bindir)
            work = self
            # Unique identifer for a given work (encoder invocation)
            work.workid = '_'.join([str(work.filename), str(self.quality), str(self.codec), str(self.runid)])
            input_path = slot.machine.media_path+'/'+work.set+'/'+work.filename
            daalatool_dir = os.getenv("DAALATOOL_DIR", os.path.join(slot.machine.work_root, "daalatool"))
            command = 'WORK_ROOT="'+slot.work_root+'" '
            command += 'DAALATOOL_ROOT="'+daalatool_dir+'"'
            command += ' x="'+str(work.quality) + '" '
            command += 'CODEC="'+work.codec+'" '
            command += 'CTC_CLASS="'+work.ctc_class+'" '
            command += 'CTC_VERSION="'+str(work.ctc_version)+'" '
            command += 'EXTRA_OPTIONS="'+work.extra_options + '" '
            if self.no_delete:
                command += 'NO_DELETE=1 '
            command += slot.work_root + '/rd_tool/metrics_gather.sh '+shellquote(input_path)
            slot.start_shell(command)
            (stdout, stderr) = slot.gather()
            # We need some buffer before we try to copy
            time.sleep(2)
            for file in self.copy_back_files:
                dest_file_path = runs_dst_dir+'/'+work.runid+'/'+work.set+'/'
                if self.multicfg:
                    dest_file_path = runs_dst_dir+'/'+work.runid+'/'+self.codec+'/'+ self.set+'/'
                if slot.get_file(slot.work_root+'/'+work.filename+'-'+str(work.quality)+file, dest_file_path) != 0:
                    rd_print(self.log,'Failed to copy back '+work.filename+'-'+str(work.quality)+file+', continuing anyway')
            self.parse(stdout, stderr)
        except Exception as e:
            rd_print(self.log, 'Exception while running',self.get_name(),e)
            self.failed = True
    def write_results(self):
        base_filename = runs_dst_dir+'/'+self.runid+'/'+self.set+'/'+self.filename
        if self.multicfg:
            base_filename = runs_dst_dir+'/'+self.runid + \
                '/'+self.codec+'/'+self.set+'/'+self.filename
        filename = (base_filename+'-daala.out').encode('utf-8')
        try:
            with open(filename,'r') as f:
                lines = f.readlines()
        except IOError:
            lines = []
        new_line = self.get_line()
        for line in lines:
            if new_line.split()[0] == line.split()[0]:
                rd_print(self.log, 'Data already exists in out file, not writing',self.get_name())
                return
        lines.append(new_line)
        lines.sort(key=lambda x: int(x.split()[0]))
        with open(filename,'w') as f:
            for line in lines:
                f.write(line)
        #write vmaf xml in separate files
        xml_filename = (base_filename+'-'+str(self.quality)+'-libvmaf.xml').encode('utf-8')
        with open(xml_filename, 'w') as f:
            f.write(self.vmaf_xml)
    def get_name(self):
        if len(self.ctc_class) > 0:
            return self.filename + ' with quality ' + str(self.quality) + ' of '+ str(self.ctc_class) + ' with config ' + str(self.codec) + ' for run ' + self.runid
        else:
            return self.filename + ' with quality ' + str(self.quality) + ' for run ' + self.runid
    def cancel(self):
        if self.slot:
            self.slot.kill()
            self.failed = True
        elif not self.done:
            self.failed = True
            self.done = True

def create_rdwork(run, video_filenames):
    work_items = []
    for filename in video_filenames:
        for q in sorted(run.quality, reverse = True):
            work = RDWork()
            work.run = run
            work.log = run.log
            work.quality = q
            work.runid = run.runid
            work.codec = run.codec
            work.bindir = run.bindir
            work.set = run.set
            work.multicfg = run.multicfg
            work.nightly_run = run.nightly_run
            work.ctc_version = run.ctc_version
            work.arch = run.arch
            # Parse and Store the CTC class (A1..A5, E, F1/F2, G1/G2)
            if 'aomctc' in work.set:
                work.ctc_class = work.set.split('-')[1].upper()
            work.filename = filename
            video_input_path = media_src_dir + '/' + work.set + '/' + work.filename
            v = open(video_input_path, "rb")
            line = v.readline().decode("utf-8")
            work.fps_n, work.fps_d = re.search(
                r"F([0-9]*)\:([0-9]*)", line).group(1, 2)
            work.width = int(re.search(r"W([0-9]*)", line).group(1))
            work.height = int(re.search(r"H([0-9]*)", line).group(1))
            # Explictly signal multislots for AV2 and VVC jobs where video is of
            # 4K resolution and from AOM-CTC
            if 'aomctc' in work.set:
                if 'av2' in work.codec or 'vvc' in work.codec:
                    if (int(work.width) >= 3840) and (int(work.height) >= 2160):
                        work.multislots = True
                    if (int(work.width) >= 1920) and (int(work.height) >= 1080):
                        if work.set in ['aomctc-a2-2k', 'aomctc-b1-syn']:
                            if work.nightly_run:
                                work.multislots = True
                            if work.codec in ['av2-ld']:
                                work.multislots = True
            work.extra_options = run.extra_options
            if run.save_encode:
                work.no_delete = True
                if work.codec == 'av1' or work.codec == 'av1-rt' or work.codec == 'rav1e' or 'svt-av1' in work.codec:
                    work.copy_back_files.append('.ivf')
                elif (len(work.codec) >= 3) and (work.codec[0:3] == 'av2'):
                    work.copy_back_files.append('.obu')
                elif (len(work.codec) >= 3) and (work.codec[0:3] == 'vvc'):
                    work.copy_back_files.append('.bin')
                elif work.codec == 'xvc':
                    work.copy_back_files.append('.xvc')
            work_items.append(work)
    return work_items

class ABWork(Work):
    def __init__(self):
        super().__init__()
        self.failed = False
    def execute(self):
        slot = self.slot
        work = self
        input_path = slot.machine.media_path +'/' + work.set + '/' + work.filename

        try:
            slot.setup(self.codec,self.bindir)
            slot.start_shell(slot.work_root+'/rd_tool/ab_meta_compare.sh ' + shellquote(str(self.bpp)) + ' ' + shellquote(self.runid) + ' ' + work.set + ' ' + shellquote(input_path) + ' ' + shellquote(self.codec))
            (stdout, stderr) = slot.gather()

            # filename with extension
            if 'video' in work.set:
                filename = input_path.split('/')[-1].rsplit('.', 1)[0] + '.ogv'
            else:
                filename = input_path.split('/')[-1].rsplit('.', 1)[0] + '.png'

            middle = self.runid + '/' + work.set + '/bpp_' + str(self.bpp)

            remote_file = slot.work_root+'/runs/' + middle + '/' + shellquote(filename)
            local_folder = runs_dst_dir + '/' + middle
            local_file = runs_dst_dir + '/' + middle + '/' + filename

            subprocess.Popen(['mkdir', '--parents', local_folder])
            slot.get_file(remote_file, local_file)
            self.failed = False
        except IndexError:
            rd_print(self.log,'Encoding and copying', filename, 'at bpp', str(self.bpp), 'failed')
            rd_print(self.log, 'stdout:')
            rd_print(self.log, stdout.decode('utf-8'))
            rd_print(self.log, 'stderr:')
            rd_print(self.log, stderr.decode('utf-8'))
            self.failed = True
    def cancel(self):
        self.failed = True
        self.done = True
    def get_name(self):
        return self.filename + ' with bpp ' + str(self.bpp)

def create_abwork(run, video_filenames):
    work_items = []
    bits_per_pixel = [x/10.0 for x in range(1, 11)]
    for filename in video_filenames:
        for bpp in bits_per_pixel:
            work = ABWork()
            work.run = run
            work.log = run.log
            work.bpp = bpp
            work.codec = run.codec
            work.bindir = run.bindir
            work.runid = run.runid
            work.set = run.set
            work.filename = filename
            work.extra_options = run.extra_options
            work_items.append(work)
    return work_items

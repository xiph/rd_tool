from utility import get_time, rd_print
import subprocess
import sys

# Finding files such as `this_(that)` requires `'` be placed on both
# sides of the quote so the `()` are both captured. Files such as
# `du_Parterre_d'Eau` must be converted into
#`'du_Parterre_d'"'"'Eau'
#                ^^^ Required to make sure the `'` is captured.
def shellquote(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"

#set up Codec:QualityRange dictionary
quality_presets = {
    "daala": [3,5,7,11,16,25,37,55,81,122,181],
    "x264": list(range(1,52,5)),
    "x265": list(range(5,52,5)),
    "x265-rt": list(range(5,52,5)),
    "vp8": list(range(12,64,5)),
    "vp9": list(range(12,64,5)),
    "vp10": [8,20,32,43,55,63],
    "vp10-rt": [8,20,32,43,55,63],
    "av1": [8,20,32,43,55,63],
    "av1-rt": [8,20,32,43,55,63],
    "thor": list(range(7,43,3)),
    "thor-rt": list(range(7,43,3))
}

class Run:
    def __init__(self, codec):
        self.codec = codec
        self.quality = quality_presets[codec]
        self.runid = get_time()
        self.extra_options = ''
        self.save_encode = False
        self.work_items = []
        self.prefix = './'

class RDRun(Run):
    def reduce(self):
        rd_print('Logging results...')
        print(self.work_items)
        self.work_items.sort(key=lambda work: work.quality)
        for work in self.work_items:
            if not work.failed:
                f = open((self.prefix+'/'+work.filename+'-daala.out').encode('utf-8'),'a')
                f.write(str(work.quality)+' ')
                f.write(str(work.pixels)+' ')
                f.write(str(work.size)+' ')
                f.write(str(work.metric['psnr'][0])+' ')
                f.write(str(work.metric['psnrhvs'][0])+' ')
                f.write(str(work.metric['ssim'][0])+' ')
                f.write(str(work.metric['fastssim'][0])+' ')
                f.write(str(work.metric['ciede2000'])+' ')
                f.write(str(work.metric['psnr'][1])+' ')
                f.write(str(work.metric['psnr'][2])+' ')
                f.write(str(work.metric['apsnr'][0])+' ')
                f.write(str(work.metric['apsnr'][1])+' ')
                f.write(str(work.metric['apsnr'][2])+' ')
                f.write(str(work.metric['msssim'][0])+' ')
                f.write(str(work.metric['encodetime'])+' ')
                f.write('\n')
                f.close()
        subprocess.call('OUTPUT="'+self.prefix+'/'+'total" "'+sys.path[0]+'/rd_average.sh" "'+self.prefix+'/*.out"',
          shell=True)

class RDWork:
    def __init__(self):
        self.no_delete = False
        self.failed = False
        self.done = False
        self.copy_back_files = ['-stdout.txt']
    def parse(self, stdout, stderr):
        self.raw = stdout
        split = None
        try:
            split = self.raw.decode('utf-8').replace(')',' ').split()
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
            self.failed = False
        except IndexError:
            rd_print('Decoding result for '+self.filename+' at quality '+str(self.quality)+' failed!')
            rd_print('stdout:')
            rd_print(stdout.decode('utf-8'))
            rd_print('stderr:')
            rd_print(stderr.decode('utf-8'))
            self.failed = True
    def execute(self, slot):
        try:
            slot.setup(self.codec,self.bindir)
            work = self
            input_path = slot.machine.media_path+'/'+work.set+'/'+work.filename
            command = 'WORK_ROOT="'+slot.work_root+'" '
            command += 'DAALATOOL_ROOT="'+slot.machine.work_root+'/daalatool" '
            command += ' x="'+str(work.quality) + '" '
            command += 'CODEC="'+work.codec+'" '
            command += 'EXTRA_OPTIONS="'+work.extra_options + '" '
            if self.no_delete:
                command += 'NO_DELETE=1 '
            command += slot.work_root + '/rd_tool/metrics_gather.sh '+shellquote(input_path)
            slot.start_shell(command)
            (stdout, stderr) = slot.gather()
            for file in self.copy_back_files:
                if slot.get_file(slot.work_root+'/'+work.filename+'-'+str(work.quality)+file,'../runs/'+work.runid+'/'+work.set+'/') != 0:
                    rd_print('Failed to copy back '+work.filename+'-'+str(work.quality)+file+', continuing anyway')
            self.parse(stdout, stderr)
            self.done = True
        except Exception as e:
            rd_print(e)
            self.failed = True
    def get_name(self):
        return self.filename + ' with quality ' + str(self.quality)

def create_rdwork(run, video_filenames):
    work_items = []
    for filename in video_filenames:
        for q in sorted(run.quality, reverse = True):
            work = RDWork()
            work.quality = q
            work.runid = run.runid
            work.codec = run.codec
            work.bindir = run.bindir
            work.set = run.set
            work.filename = filename
            work.extra_options = run.extra_options
            if run.save_encode:
                work.no_delete = True
                if work.codec == 'av1':
                    work.copy_back_files.append('.ivf')
            work_items.append(work)
    return work_items

class ABWork:
    def __init__(self):
        self.failed = False
    def execute(self, slot):
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
            local_folder = '../runs/' + middle
            local_file = '../runs/' + middle + '/' + filename

            subprocess.Popen(['mkdir', '--parents', local_folder])
            slot.get_file(remote_file, local_file)
            self.failed = False
        except IndexError:
            rd_print('Encoding and copying', filename, 'at bpp', str(self.bpp), 'failed')
            rd_print('stdout:')
            rd_print(stdout.decode('utf-8'))
            rd_print('stderr:')
            rd_print(stderr.decode('utf-8'))
            self.failed = True
    def get_name(self):
        return self.filename + ' with bpp ' + str(self.bpp)

def create_abwork(run, video_filenames):
    work_items = []
    bits_per_pixel = [x/10.0 for x in range(1, 11)]
    for filename in video_filenames:
        for bpp in bits_per_pixel:
            work = ABWork()
            work.bpp = bpp
            work.codec = run.codec
            work.bindir = run.bindir
            work.runid = run.runid
            work.set = run.set
            work.filename = filename
            work.extra_options = run.extra_options
            work_items.append(work)
    return work_items

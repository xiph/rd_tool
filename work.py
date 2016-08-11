from utility import get_time, rd_print

# Finding files such as `this_(that)` requires `'` be placed on both
# sides of the quote so the `()` are both captured. Files such as
# `du_Parterre_d'Eau` must be converted into
#`'du_Parterre_d'"'"'Eau'
#                ^^^ Required to make sure the `'` is captured.
def shellquote(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"

class RDWork:
    def __init__(self):
        self.no_delete = False
        self.failed = False
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
            command += '/rd_tool/metrics_gather.sh '+shellquote(input_path)
            slot.start_shell(command)
            (stdout, stderr) = slot.gather()
            for file in self.copy_back_files:
                slot.get_file(slot.work_root+'/'+work.filename+'-'+str(work.quality)+file,'../runs/'+work.runid+'/'+work.set+'/')
            self.parse(stdout, stderr)
        except Exception as e:
            rd_print(e)
            self.failed = True
    def get_name(self):
        return self.filename + ' with quality ' + str(self.quality)

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

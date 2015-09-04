#!/usr/bin/env python3

from utility import get_time
import argparse
import os
import sys
import subprocess
import json
import awsremote
import scheduler

def shellquote(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"

if 'DAALA_ROOT' not in os.environ:
    print(get_time(),"Please specify the DAALA_ROOT environment variable to use this tool.")
    sys.exit(1)

daala_root = os.environ['DAALA_ROOT']

extra_options = ''
if 'EXTRA_OPTIONS' in os.environ:
    extra_options = os.environ['EXTRA_OPTIONS']

class Work:
    def __init__(self):
        self.failed = False
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
            self.failed = False
        except IndexError:
            print(get_time(),'Decoding result for '+self.filename+' at quality '+str(self.quality)+'failed!')
            print(get_time(),'stdout:')
            print(get_time(),stdout.decode('utf-8'))
            print(get_time(),'stderr:')
            print(get_time(),stderr.decode('utf-8'))
            self.failed = True
    def execute(self, slot):
        work = self
        if self.individual:
            input_path = '/mnt/media/'+work.filename
        else:
            input_path = '/mnt/media/'+work.set+'/'+work.filename
        slot.start_shell(('DAALA_ROOT=/home/ec2-user/daala/ x="'+str(work.quality) +
            '" CODEC="'+work.codec+'" EXTRA_OPTIONS="'+work.extra_options +
            '" /home/ec2-user/rd_tool/metrics_gather.sh '+shellquote(input_path)))
        (stdout, stderr) = slot.gather()
        self.parse(stdout, stderr)
    def get_name(self):
        return self.filename + ' with quality ' + str(self.quality)
        
class ABWork:
    def __init__(self):
        self.failed = False
    def execute(self, slot):
        work = self
        if self.individual:
            input_path = '/mnt/media/'+work.filename
        else:
            input_path = '/mnt/media/'+work.set+'/'+work.filename
        slot.start_shell(('DAALA_ROOT=/home/ec2-user/daala/ Y4M2PNG=/home/ec2-user/daalatool/tools/y4m2png EXTRA_OPTIONS="'+work.extra_options +
            '" /home/ec2-user/daalatool/tools/ab_compare.sh -a /home/ec2-user/daalatool/tools/ -c daala -b '+str(self.bpp)+' '+shellquote(input_path)))
        (stdout, stderr) = slot.gather()
        (base, ext) = os.path.splitext(work.filename)
        # search for the correct filename
        filename = slot.check_shell('find -maxdepth 1 -name '+shellquote(base)+'*.png')
        print(filename)
        slot.get_file(filename, './')
    def get_name(self):
        return self.filename + ' with bpp ' + str(self.bpp)

#set up Codec:QualityRange dictionary
quality = {
"daala": [5,7,11,16,25,37,55,81,122,181,270,400],
"x264": list(range(1,52,5)),
"x265": list(range(5,52,5)),
"x265-rt": list(range(5,52,5)),
"vp8": list(range(4,64,4)),
"vp9": list(range(4,64,4)),
"thor": list(range(4,40,4))
}

work_items = []

#load all the different sets and their filenames
video_sets_f = open('sets.json','r')
video_sets = json.load(video_sets_f)

parser = argparse.ArgumentParser(description='Collect RD curve data.')
parser.add_argument('set',metavar='Video set name',nargs='+')
parser.add_argument('-codec',default='daala')
parser.add_argument('-prefix',default='.')
parser.add_argument('-individual', action='store_true')
parser.add_argument('-awsgroup', default='Daala')
parser.add_argument('-machines', default=13)
parser.add_argument('-mode', default='metric')
args = parser.parse_args()

aws_group_name = args.awsgroup

#check we have the codec in our codec-qualities dictionary
if args.codec not in quality:
    print(get_time(),'Invalid codec. Valid codecs are:')
    for q in quality:
        print(get_time(),q)
    sys.exit(1)

#check we have the set name in our sets-filenames dictionary
if not args.individual:
  if args.set[0] not in video_sets:
      print(get_time(),'Specified invalid set '+args.set[0]+'. Available sets are:')
      for video_set in video_sets:
          print(get_time(),video_set)
      sys.exit(1)

if not args.individual:
    total_num_of_jobs = len(video_sets[args.set[0]]) * len(quality[args.codec])
else:
    total_num_of_jobs = len(quality[args.codec]) #FIXME

#a logging message just to get the regex progress bar on the AWCY site started...
print(get_time(),'0 out of',total_num_of_jobs,'finished.')

#how many AWS instances do we want to spin up?
#The assumption is each machine can deal with 18 threads,
#so up to 18 jobs, use 1 machine, then up to 64 use 2, etc...
num_instances_to_use = (31 + total_num_of_jobs) // 18

#...but lock AWS to a max number of instances
max_num_instances_to_use = int(args.machines)

if num_instances_to_use > max_num_instances_to_use:
  print(get_time(),'Ideally, we should use',num_instances_to_use,
    'AWS instances, but the max is',max_num_instances_to_use,'.')
  num_instances_to_use = max_num_instances_to_use

machines = awsremote.get_machines(num_instances_to_use, aws_group_name)

#set up our instances and their free job slots
for machine in machines:
    machine.setup()
    
slots = awsremote.get_slots(machines)

#Make a list of the bits of work we need to do.
#We pack the stack ordered by filesize ASC, quality ASC (aka. -v DESC)
#so we pop the hardest encodes first,
#for more efficient use of the AWS machines' time.

if args.individual:
    video_filenames = args.set
else:
    video_filenames = video_sets[args.set[0]]

if args.mode == 'metric':
    for filename in video_filenames:
        for q in sorted(quality[args.codec], reverse = True):
            work = Work()
            work.quality = q
            work.codec = args.codec
            if args.individual:
                work.individual = True
            else:
                work.individual = False
                work.set = args.set[0]
            work.filename = filename
            work.extra_options = extra_options
            work_items.append(work)
elif args.mode == 'ab':
    for filename in video_filenames:  
        for bpp in {0.1}:
            work = ABWork()
            work.bpp = bpp
            work.codec = args.codec
            if args.individual:
                work.individual = True
            else:
                work.individual = False
                work.set = args.set[0]
            work.filename = filename
            work.extra_options = extra_options
            work_items.append(work)
else:
    print('Unsupported -mode parameter.')
    sys.exit(1)

if len(slots) < 1:
    print(get_time(),'All AWS machines are down.')
    sys.exit(1)

work_done = scheduler.run(work_items, slots)

if args.mode == 'metric':
    print(get_time(),'Logging results...')
    work_done.sort(key=lambda work: work.quality)
    for work in work_done:
        if not work.failed:
            if args.individual:
                f = open((args.prefix+'/'+os.path.basename(work.filename)+'.out').encode('utf-8'),'a')
            else:
                f = open((args.prefix+'/'+work.filename+'-daala.out').encode('utf-8'),'a')
            f.write(str(work.quality)+' ')
            f.write(str(work.pixels)+' ')
            f.write(str(work.size)+' ')
            f.write(str(work.metric['psnr'][0])+' ')
            f.write(str(work.metric['psnrhvs'][0])+' ')
            f.write(str(work.metric['ssim'][0])+' ')
            f.write(str(work.metric['fastssim'][0])+' ')
            f.write('\n')
            f.close()
    if not args.individual:
      subprocess.call('OUTPUT="'+args.prefix+'/'+'total" "'+daala_root+'/tools/rd_average.sh" "'+args.prefix+'/*.out"',
          shell=True);

print(get_time(),'Done!')

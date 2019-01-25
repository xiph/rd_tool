#!/usr/bin/env python3

from utility import get_time, rd_print
import argparse
import os
import sys
import subprocess
import json
import codecs
import awsremote
import scheduler
import sshslot
from work import *


config_dir = os.getenv("CONFIG_DIR", os.getcwd())
runs_dst_dir = os.getenv("RUNS_DST_DIR", os.path.join(os.getcwd(), "../runs"))
codecs_src_dir = os.getenv("CODECS_SRC_DIR", os.path.join(os.getcwd(), ".."))

if 'DAALA_ROOT' not in os.environ:
    rd_print(None,"Please specify the DAALA_ROOT environment variable to use this tool.")
    sys.exit(1)

daala_root = os.environ['DAALA_ROOT']

extra_options = ''
if 'EXTRA_OPTIONS' in os.environ:
    extra_options = os.environ['EXTRA_OPTIONS']
    print(get_time(),'Passing extra command-line options:"%s"' % extra_options)

work_items = []

#load all the different sets and their filenames
video_sets_f = codecs.open(os.path.join(config_dir, 'sets.json'),'r',encoding='utf-8')
video_sets = json.load(video_sets_f)

parser = argparse.ArgumentParser(description='Collect RD curve data.')
parser.add_argument('set',metavar='Video set name',nargs='+')
parser.add_argument('-codec',default='daala')
parser.add_argument('-bindir',default='./')
parser.add_argument('-prefix',default='.')
parser.add_argument('-awsgroup', default='Daala')
parser.add_argument('-machines', default=14)
parser.add_argument('-mode', default='metric')
parser.add_argument('-runid', default=get_time())
parser.add_argument('-seed')
parser.add_argument('-bpp')
parser.add_argument('-qualities',nargs='+')
parser.add_argument('-machineconf')
parser.add_argument('-save-encode',action='store_true')

args = parser.parse_args()

aws_group_name = args.awsgroup

#check we have the codec in our codec-qualities dictionary
if args.codec not in quality_presets:
    rd_print(None,'Invalid codec. Valid codecs are:')
    for q in quality_presets:
        rd_print(None,q)
    sys.exit(1)

#check we have the set name in our sets-filenames dictionary
if args.set[0] not in video_sets:
    rd_print(None,'Specified invalid set '+args.set[0]+'. Available sets are:')
    for video_set in video_sets:
        rd_print(None,video_set)
    sys.exit(1)

#Make a list of the bits of work we need to do.
#We pack the stack ordered by filesize ASC, quality ASC (aka. -v DESC)
#so we pop the hardest encodes first,
#for more efficient use of the AWS machines' time.

video_filenames = video_sets[args.set[0]]['sources']

if args.mode == 'metric':
    run = RDRun(args.codec)
else:
    run = Run(args.codec)
run.runid = str(args.runid)
if args.qualities:
    run.quality = args.qualities
run.set = args.set[0]
run.bindir = args.bindir
run.save_encode = args.save_encode
run.extra_options = extra_options
run.prefix = args.prefix

if args.mode == 'metric':
    work_items = create_rdwork(run, video_filenames)
elif args.mode == 'ab':
    if video_sets[args.set[0]]['type'] == 'video':
        print("mode `ab` isn't supported for videos. Skipping.")
    else:
        work_items = create_abwork(run, video_filenames)
else:
    print('Unsupported -mode parameter.')
    sys.exit(1)
run.work_items = list(work_items)

total_num_of_jobs = len(video_sets[args.set[0]]['sources']) * len(run.quality)

#a logging message just to get the regex progress bar on the AWCY site started...
rd_print(None,'0 out of',total_num_of_jobs,'finished.')

#how many AWS instances do we want to spin up?
#The assumption is each machine can deal with 18 threads,
#so up to 18 jobs, use 1 machine, then up to 64 use 2, etc...
num_instances_to_use = (31 + total_num_of_jobs) // 18

#...but lock AWS to a max number of instances
max_num_instances_to_use = int(args.machines)

if num_instances_to_use > max_num_instances_to_use:
    rd_print(None,'Ideally, we should use',num_instances_to_use,
        'instances, but the max is',max_num_instances_to_use,'.')
    num_instances_to_use = max_num_instances_to_use

machines = []
if args.machineconf:
    machineconf = json.load(open(args.machineconf, 'r'))
    for m in machineconf:
        machines.append(sshslot.Machine(m['host'],m['user'],m['cores'],m['work_root'],str(m['port']),m['media_path']))
else:
    while not machines:
        machines = awsremote.get_machines(num_instances_to_use, aws_group_name)

slots = []
#set up our instances and their free job slots
for machine in machines:
    slots.extend(machine.get_slots())

if len(slots) < 1:
    rd_print(None,'All AWS machines are down.')
    sys.exit(1)

work_done = scheduler.run(work_items, slots)

if args.mode == 'metric':
    run.reduce()

rd_print(None,'Done!')

#!/usr/bin/env python

from __future__ import print_function

import argparse
import os
import sys
import threading
import subprocess
import time
import multiprocessing
import boto.ec2.autoscale
from pprint import pprint

if 'DAALA_ROOT' not in os.environ:
    print("Please specify the DAALA_ROOT environment variable to use this tool.")
    sys.exit(1)

daala_root = os.environ['DAALA_ROOT']

class Machine:
    def __init__(self,host):
        self.host = host
    def setup(self):
        print('Connecting to',self.host)
        subprocess.call(['./transfer_git.sh',self.host])
    def execute(self,command):
        ssh_command = ['ssh','-i','daala.pem','-o',' StrictHostKeyChecking=no',command]
    def upload(self,filename):
        basename = os.path.basename(filename)
        print('Uploading',basename)
        subprocess.call(['scp','-i','daala.pem','-o',' StrictHostKeyChecking=no',filename,'ec2-user@'+self.host+':/home/ec2-user/video/'+basename])

class Slot:
    def __init__(self, machine=None):
        self.name='localhost'
        self.machine = machine
        self.p = None
    def execute(self, work):
        self.work = work
        output_name = work.filename+'.'+str(work.quality)+'.ogv'
        env = {}
        env['DAALA_ROOT'] = daala_root
        env['x'] = str(work.quality)
        print('Encoding',work.filename,'with quality',work.quality)
        if self.machine is None:
            self.p = subprocess.Popen(['metrics_gather.sh',work.filename], env=env, stdout=subprocess.PIPE)
        else:
            self.p = subprocess.Popen(['ssh','-i',daala_root+'/tools/daala.pem','-o',' StrictHostKeyChecking=no','ec2-user@'+self.machine.host,'DAALA_ROOT=/home/ec2-user/daala/ x='+str(work.quality)+' /home/ec2-user/rd_tool/metrics_gather.sh /home/ec2-user/video/'+os.path.basename(work.filename)], env=env, stdout=subprocess.PIPE)
    def busy(self):
        if self.p is None:
            return False
        elif self.p.poll() is None:
            return True
        else:
            return False
    def gather(self):
        (stdout, stderr) = self.p.communicate()
        self.work.raw = stdout

class Work:
    def parse(self):
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
            print('Decoding result data failed! Result was:')
            print(split)
            self.failed = True
        
quality_daala = [1,2,3,4,5,6,7,9,11,13,16,20,25,30,37,45,55,67,81,99,122,148,181,221,270,330,400,500]

free_slots = [Slot(),Slot(),Slot(),Slot()]
taken_slots = []

work_items = []
work_done = []

machines = []

parser = argparse.ArgumentParser(description='Collect RD curve data.')
parser.add_argument('file', metavar='*.y4m')
parser.add_argument('--amazon',action='store_true')
parser.add_argument('--local')
args = parser.parse_args()

if args.amazon:
    print('Launching instances...')
    autoscale = boto.ec2.autoscale.AutoScaleConnection();
    ec2 = boto.ec2.connect_to_region('us-west-2');
    autoscale.set_desired_capacity('Daala',2)
    print('Connecting to Amazon instances..')
    group = None
    while 1:
        group = autoscale.get_all_groups(names=['Daala'])[0]
        num_instances = len(group.instances)
        print('Number of instances online:',len(group.instances))
        if num_instances >= 2:
            break
        time.sleep(1)
    instance_ids = [i.instance_id for i in group.instances]
    print(instance_ids)
    instances = ec2.get_only_instances(instance_ids)
    for instance in instances:
        print('Waiting for instance',instance.id,'to boot...')
        while 1:
            instance.update()
            if instance.state == 'running':
                break
    for instance in instances:
        machines.append(Machine(instance.ip_address))
    for machine in machines:
        machine.setup()
        machine.upload(args.file)
        for i in range(0,32):
            free_slots.append(Slot(machine))

for quality in quality_daala:
    work = Work()
    work.quality = quality
    work.filename = args.file
    work_items.append(work)
    
if len(free_slots) < 1:
    print('No slots available for work! Use either --amazon or --local')
    sys.exit(1)

while(1):
    for slot in taken_slots:
        if slot.busy() == False:
            slot.gather()
            work_done.append(slot.work)
            taken_slots.remove(slot)
            free_slots.append(slot)
    if len(work_items) == 0:
        if len(taken_slots) == 0:
            break
    else:
        if len(free_slots) != 0:
            slot = free_slots.pop()
            work = work_items.pop()
            threading.Thread(slot.execute(work))
            taken_slots.append(slot)
    time.sleep(1)   
    
work_done.sort(key=lambda work: work.quality)
    
f = open(args.file+'-daala.out','w')
for work in work_done:
    work.parse()
    if not work.failed:
        f.write(str(work.quality)+' ')
        f.write(str(work.pixels)+' ')
        f.write(str(work.size)+' ')
        f.write(str(work.metric['psnr'][0])+' ')
        f.write(str(work.metric['psnrhvs'][0])+' ')
        f.write(str(work.metric['ssim'][0])+' ')
        f.write(str(work.metric['fastssim'][0])+' ')
        f.write('\n')
f.close()


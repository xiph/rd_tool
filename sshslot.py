from utility import *
import subprocess
import sys
import os
import time

binaries = {
  'daala':['examples/encoder_example'],
  'x264': ['x264'],
  'x265': ['build/linux/x265'],
  'vp8': ['vpxenc','vpxdec'],
  'vp9': ['vpxenc','vpxdec'],
  'vp10': ['vpxenc','vpxdec'],
  'vp10-rt': ['vpxenc','vpxdec'],
  'av1': ['aomenc','aomdec'],
  'av1-rt': ['aomenc','aomdec'],
  'thor': ['build/Thorenc','build/Thordec']
}

# Finding files such as `this_(that)` requires `'` be placed on both
# sides of the quote so the `()` are both captured. Files such as
# `du_Parterre_d'Eau` must be converted into
#`'du_Parterre_d'"'"'Eau'
#                ^^^ Required to make sure the `'` is captured.
def shellquote(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"

class Machine:
    def __init__(self,host,user='ec2-user',cores=18,work_root='/home/ec2-user',port=22,media_path='/mnt/media'):
        self.host = host
        self.user = user
        self.cores = cores
        self.work_root = work_root
        self.port = str(port)
        self.media_path = media_path
        self.log = None
        self.slots = []
    def rsync(self, local, remote):
        return subprocess.call(['rsync', '-r', '-e', "ssh -i daala.pem -o StrictHostKeyChecking=no -p "+str(self.port), local, self.user + '@' + self.host + ':' + remote])
    def check_shell(self, command):
        return subprocess.check_output(['ssh','-i','daala.pem','-p',self.port,'-o',' StrictHostKeyChecking=no',
           self.user+'@'+self.host,
           command.encode("utf-8")])
    def get_slots(self):
        slots = []
        #by doing the machines in the inner loop,
        #we end up with heavy jobs split across machines better
        for i in range(0,self.cores):
            slots.append(Slot(self, i, self.log))
        self.slots = slots
        return slots
    def get_name(self):
        return self.host

#the job slots we can fill
class Slot:
    def __init__(self, machine, num, log):
        self.machine = machine
        self.work_root = machine.work_root + '/slot' + str(num)
        self.p = None
        self.busy = False
        self.work = None
        self.log = log
    def gather(self):
        return self.p.communicate()
    def execute(self, work):
        self.busy = True
        self.work = work
        try:
            self.work.execute(self)
        except Exception as e:
            rd_print(self.log, e)
            self.work.failed = True
        self.busy = False
    def setup(self,codec,bindir):
        time.sleep(1)
        self.check_shell('mkdir -p '+shellquote(self.work_root))
        time.sleep(1)
        if self.machine.rsync('./',self.work_root+'/rd_tool/') != 0:
            rd_print(self.log,'Couldn\'t set up machine '+self.machine.host)
            raise RuntimeError
        time.sleep(1)
        self.check_shell('rm -rf '+shellquote(self.work_root+'/'+codec))
        for binary in binaries[codec]:
            time.sleep(1)
            self.check_shell('mkdir -p '+shellquote(self.work_root+'/'+codec+'/'+os.path.dirname(binary)));
            time.sleep(1)
            if self.machine.rsync(bindir+'/'+binary,self.work_root+'/'+codec+'/'+binary) != 0:
                rd_print(self.log,'Couldn\'t upload codec binary '+binary+'to '+self.machine.host)
                raise RuntimeError
    def start_shell(self, command):
        self.p = subprocess.Popen(['ssh','-i','daala.pem','-p',self.machine.port,'-o',' StrictHostKeyChecking=no',
            self.machine.user+'@'+self.machine.host,
            command.encode("utf-8")], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    def get_file(self, remote, local):
        return subprocess.call(['scp','-i','daala.pem','-P',self.machine.port,self.machine.user+'@'+self.machine.host+':'+shellquote(remote),local])
    def check_shell(self, command):
        return subprocess.check_output(['ssh','-i','daala.pem','-p',self.machine.port,'-o',' StrictHostKeyChecking=no',
           self.machine.user+'@'+self.machine.host,
           command.encode("utf-8")])

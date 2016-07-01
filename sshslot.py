from utility import get_time
import subprocess
import sys
import os

binaries = {
  'daala':['examples/encoder_example'],
  'x264': ['x264'],
  'x265': ['build/linux/x265'],
  'vp8': ['vpxenc','vpxdec'],
  'vp9': ['vpxenc','vpxdec'],
  'av1': ['aomenc','aomdec'],
  'thor': ['build/Thorenc','build/Thordec']
}

class Machine:
    def __init__(self,host,user='ec2-user',cores=32,work_root='/home/ec2-user',port=22):
        self.host = host
        self.user = user
        self.cores = cores
        self.work_root = work_root
        self.port = str(port)
    def rsync(self, local, remote):
        return subprocess.call(['rsync', '-r', '-e', "ssh -i daala.pem -o StrictHostKeyChecking=no -p "+str(self.port), local, self.user + '@' + self.host + ':' + remote])
    def check_shell(self, command):
        return subprocess.check_output(['ssh','-i','daala.pem','-p',self.port,'-o',' StrictHostKeyChecking=no',
           self.user+'@'+self.host,
           command.encode("utf-8")])
    def setup(self,codec):
        print(get_time(),'Connecting to',self.host)
        if self.rsync('./',self.work_root+'/rd_tool/') != 0:
            print(get_time(),'Couldn\'t set up machine '+self.host)
            sys.exit(1)
        self.check_shell('rm -rf '+self.work_root+'/'+codec)
        for binary in binaries[codec]:
            self.check_shell('mkdir -p '+self.work_root+'/'+codec+'/'+os.path.dirname(binary));
            if self.rsync('../'+codec+'/'+binary,self.work_root+'/'+codec+'/'+binary) != 0:
                print(get_time(),'Couldn\'t upload codec binary '+binary+'to '+self.host)
                sys.exit(1)
    def get_slots(self):
        slots = []
        #by doing the machines in the inner loop,
        #we end up with heavy jobs split across machines better
        for i in range(0,self.cores):
            slots.append(Slot(self))
        return slots

#the job slots we can fill
class Slot:
    def __init__(self, machine=None):
        self.machine = machine
        self.work_root = machine.work_root
        self.p = None
        self.busy = False
    def gather(self):
        return self.p.communicate()
    def execute(self, work):
        self.busy = True
        self.work = work
        work.execute(self)
        self.busy = False
    def start_shell(self, command):
        self.p = subprocess.Popen(['ssh','-i','daala.pem','-p',self.machine.port,'-o',' StrictHostKeyChecking=no',
            self.machine.user+'@'+self.machine.host,
            command.encode("utf-8")], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    def get_file(self, remote, local):
        subprocess.call(['scp','-i','daala.pem','-P',self.machine.port,self.machine.user+'@'+self.machine.host+':'+remote,local])
    def check_shell(self, command):
        return subprocess.check_output(['ssh','-i','daala.pem','-p',self.machine.port,'-o',' StrictHostKeyChecking=no',
           self.machine.user+'@'+self.machine.host,
           command.encode("utf-8")])

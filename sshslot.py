from utility import *
import subprocess
import sys
import os
import threading
import time

ssh_privkey_file = os.getenv("SSH_PRIVKEY_FILE", "daala.pem")

binaries = {
    'daala':['examples/encoder_example','examples/dump_video'],
    'x264': ['x264'],
    'x264-rt': ['x264'],
    'x265': ['build/linux/x265'],
    'x265-rt': ['build/linux/x265'],
    'xvc': ['build/app/xvcenc', 'build/app/xvcdec'],
    'vp8': ['vpxenc','vpxdec'],
    'vp9': ['vpxenc','vpxdec'],
    'vp9-rt': ['vpxenc','vpxdec'],
    'vp10': ['vpxenc','vpxdec'],
    'vp10-rt': ['vpxenc','vpxdec'],
    'av1': ['aomenc','aomdec'],
    'av1-rt': ['aomenc','aomdec'],
    'av2-ai': ['aomenc','aomdec'],
    'av2-ra': ['aomenc','aomdec'],
    'av2-ra-st': ['aomenc','aomdec'],
    'av2-ld': ['aomenc','aomdec'],
    'av2-as': ['aomenc','aomdec'],
    'thor': ['build/Thorenc','build/Thordec','config_HDB16_high_efficiency.txt','config_LDB_high_efficiency.txt'],
    'thor-rt': ['build/Thorenc','build/Thordec','config_HDB16_high_efficiency.txt','config_LDB_high_efficiency.txt'],
    'rav1e': ['target/release/rav1e'],
    'svt-av1': ['Bin/Release/SvtAv1EncApp', 'Bin/Release/libSvtAv1Enc.so.0']
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
        return subprocess.call(['rsync', '-r', '-e', "ssh -i "+ssh_privkey_file+" -o StrictHostKeyChecking=no -p "+str(self.port), local, self.user + '@' + self.host + ':' + remote])
    def check_shell(self, command):
        return subprocess.check_output(['ssh','-i',ssh_privkey_file,'-p',self.port,'-o',' StrictHostKeyChecking=no',
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

class SlotProcess:
    def __init__(self, log):
        self.p = None
        self.can_kill = threading.Event()
        self.log = log
    def kill(self):
        # wait until there is actually a process to kill
        success = self.can_kill.wait(20)
        if not success:
            rd_print(self.log,"Waited too long for process to kill.")
            if self.p:
                rd_print(self.log,"Will try to kill anyway.")
            else:
                rd_print(self.log,"Aborting kill.")
                return
        try:
            self.p.kill()
        except Exception as e:
            rd_print(self.log,"Couldn't cancel work item",e)
    def communicate(self):
        return self.p.communicate()
    def shell(self, args):
        self.p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.can_kill.set()

#the job slots we can fill
class Slot:
    def __init__(self, machine, num, log):
        self.machine = machine
        self.work_root = machine.work_root + '/slot' + str(num)
        self.p = None
        self.busy = False
        self.work = None
        self.log = log
        self.can_kill = None
    def gather(self):
        return self.p.communicate()
    def start_work(self, work):
        self.work = work
        work.slot = self
        self.p = SlotProcess(self.log)
        work_thread = threading.Thread(target=self.execute)
        work_thread.daemon = True
        self.busy = True
        work_thread.start()
    def clear_work(self):
        if self.work:
            self.work.slot = None
            self.work = None
    def execute(self):
        try:
            self.work.execute()
        except Exception as e:
            rd_print(self.log, e)
            self.work.failed = True
        self.busy = False
    def setup(self,codec,bindir):
        time.sleep(1)
        try:
            self.check_shell('mkdir -p '+shellquote(self.work_root))
            time.sleep(1)
            self.check_shell('rm -f '+shellquote(self.work_root)+'/*.y4m '+shellquote(self.work_root)+'/*.ivf')
            time.sleep(1)
        except subprocess.CalledProcessError as e:
            rd_print(self.log,e.output)
            rd_print(self.log,'Couldn\'t connect to machine '+self.machine.host)
            raise RuntimeError('This is a bug with AWCY. Likely this machine has gone unreachable.')
        if self.machine.rsync('./',self.work_root+'/rd_tool/') != 0:
            rd_print(self.log,'Couldn\'t set up machine '+self.machine.host)
            raise RuntimeError('Couldn\'t copy tools to machine (out of disk space?)')
        time.sleep(1)
        self.check_shell('rm -rf '+shellquote(self.work_root+'/'+codec))
        for binary in binaries[codec]:
            time.sleep(1)
            self.check_shell('mkdir -p '+shellquote(self.work_root+'/'+codec+'/'+os.path.dirname(binary)));
            time.sleep(1)
            if self.machine.rsync(bindir+'/'+binary,self.work_root+'/'+codec+'/'+binary) != 0:
                rd_print(self.log,'Couldn\'t upload codec binary '+binary+'to '+self.machine.host)
                raise RuntimeError('Couldn\'t upload codec binary')
    def start_shell(self, command):
        self.p.shell(['ssh','-i',ssh_privkey_file,'-p',self.machine.port,'-o',' StrictHostKeyChecking=no', self.machine.user+'@'+self.machine.host,
            command.encode("utf-8")])
    def kill(self):
        kill_thread = threading.Thread(target=self.p.kill)
        kill_thread.daemon = True
        kill_thread.start()
    def get_file(self, remote, local):
        return subprocess.call(['scp','-T','-i',ssh_privkey_file,'-P',self.machine.port,self.machine.user+'@'+self.machine.host+':'+shellquote(remote),local])
    def check_shell(self, command):
        return subprocess.check_output(['ssh','-i',ssh_privkey_file,'-p',self.machine.port,'-o',' StrictHostKeyChecking=no',
           self.machine.user+'@'+self.machine.host,
           command.encode("utf-8")])

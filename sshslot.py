from utility import get_time
import subprocess
import sys

class Machine:
    def __init__(self,host,user='ec2-user',cores=32,work_root='/home/ec2-user',port=22):
        self.host = host
        self.user = user
        self.cores = cores
        self.work_root = work_root
        self.port = port
    def setup(self,codec):
        print(get_time(),'Connecting to',self.host)
        if subprocess.call(['./transfer_git.sh',self.host,codec,self.user,self.work_root,self.port]) != 0:
          print(get_time(),'Couldn\'t set up machine '+self.host)
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
    def rsync(self, local, remote):
        subprocess.call(['rsync', '-r', '-e', "ssh -i daala.pem -o StrictHostKeyChecking=no", local, self.machine.user + '@' + self.machine.host + ':' + remote])
    def check_shell(self, command):
        return subprocess.check_output(['ssh','-i','daala.pem','-p',self.machine.port,'-o',' StrictHostKeyChecking=no',
           self.machine.user+'@'+self.machine.host,
           command.encode("utf-8")])

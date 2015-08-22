from __future__ import print_function
from datetime import datetime
import threading
from time import sleep

#our timestamping function, accurate to milliseconds
#(remove [:-3] to display microseconds)
def GetTime():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def run(work_items, slots):
    retries = 0
    max_retries = 10
    free_slots = slots
    taken_slots = []
    work_done = []
    total_num_of_jobs = len(work_items)
    while(1):
        for slot in taken_slots:
            if slot.busy() == False:
                (stdout, stderr) = slot.gather()
                slot.work.parse(stdout, stderr)
                if slot.work.failed == False:
                    work_done.append(slot.work)
                    print(GetTime(),len(work_done),'out of',total_num_of_jobs,'finished.')
                elif retries >= max_retries:
                    break
                else:
                    retries = retries + 1
                    print(GetTime(),'Retrying work...',retries,'of',max_retries,'retries.')
                    work_items.append(slot.work)
                taken_slots.remove(slot)
                free_slots.append(slot)

        #have we finished all the work?
        if len(work_items) == 0:
            if len(taken_slots) == 0:
                print(GetTime(),'All work finished.')
                break
        elif retries >= max_retries:
            print(GetTime(),'Max number of failed retries reached!')
            sys.exit(1)
        else:
            if len(free_slots) != 0:
                slot = free_slots.pop()
                work = work_items.pop()
                print(GetTime(),'Encoding',work.filename,'with quality',work.quality,'on',slot.machine.host)
                threading.Thread(slot.execute(work))
                taken_slots.append(slot)
        sleep(0.02)
    return work_done

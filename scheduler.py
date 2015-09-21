#!/usr/bin/env python3

from utility import get_time
import threading
from time import sleep
import sys

def run(work_items, slots):
    retries = 0
    max_retries = 10
    free_slots = slots
    taken_slots = []
    work_done = []
    total_num_of_jobs = len(work_items)
    while(1):
        for slot in taken_slots:
            if slot.busy == False:
                if slot.work.failed == False:
                    work_done.append(slot.work)
                    print(get_time(),len(work_done),'out of',total_num_of_jobs,'finished.')
                elif retries >= max_retries:
                    break
                else:
                    retries = retries + 1
                    print(get_time(),'Retrying work...',retries,'of',max_retries,'retries.')
                    work_items.append(slot.work)
                taken_slots.remove(slot)
                free_slots.append(slot)

        #have we finished all the work?
        if len(work_items) == 0:
            if len(taken_slots) == 0:
                print(get_time(),'All work finished.')
                break
        elif retries >= max_retries:
            print(get_time(),'Max number of failed retries reached!')
            sys.exit(1)
        else:
            if len(free_slots) != 0:
                slot = free_slots.pop()
                work = work_items.pop()
                slot.work = work
                print(get_time(),'Encoding',work.get_name(),'on',slot.machine.host)
                work_thread = threading.Thread(target=slot.execute, args=(work,))
                work_thread.daemon = True
                slot.busy = True
                work_thread.start()
                taken_slots.append(slot)
        sleep(0.2)
    return work_done

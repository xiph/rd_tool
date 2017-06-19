#!/usr/bin/env python3

from utility import get_time
import threading
from time import sleep
import sys

def run(work_items, slots):
    retries = 0
    max_retries = 5000
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
                slot.clear_work()
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
                print(get_time(),'Encoding',work.get_name(),'on',slot.machine.host)
                slot.start_work(work)
                taken_slots.append(slot)
        sleep(0.2)
    return work_done

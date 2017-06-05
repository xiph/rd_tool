#!/usr/bin/env python3

import tornado.ioloop
import tornado.web
import os
import json
import argparse
import sshslot
import threading
import time
import awsremote
from queue import PriorityQueue
from work import *
from utility import *
from estimator import *

video_sets_f = open('sets.json','r',encoding='utf-8')
video_sets = json.load(video_sets_f)
video_sets_f.close()

machines = []
slots = []
free_slots = []
work_list = []
run_list = []
work_done = []
args = {}

config = {
  'runs': '../runs/',
  'codecs': '../'
}

def lookup_run_by_id(run_id):
    for run in run_list:
        if run.runid == run_id:
            return run
    return None

class CancelHandler(tornado.web.RequestHandler):
    def get(self):
        global work_list
        global work_done
        run_id = self.get_query_argument('run_id')
        rd_print(None,'Cancelling '+run_id)
        run = lookup_run_by_id(run_id)
        if not run:
            self.write('run_id not found')
            return
        run.cancel()
        for work in work_list[:]:
            if work.runid == run_id:
                work_list.remove(work)
                work.cancel()
                work_done.append(work)
            else:
                print(work.runid)
        print(len(work_list))
        self.write('ok')

class RunSubmitHandler(tornado.web.RequestHandler):
    def get(self):
        global work_list
        global run_list
        run_id = self.get_query_argument('run_id')
        rundir = config['runs'] + '/' + run_id
        info_file_path = rundir + '/info.json'
        log_file_path = rundir + '/output.txt'
        info_file = open(info_file_path, 'r')
        log_file = open(log_file_path, 'a')
        info = json.load(info_file)
        run = RDRun(info['codec'])
        run.info = info
        run.runid = run_id
        run.rundir = config['runs'] + '/' + run_id
        run.log = log_file
        run.set = info['task']
        run.bindir = run.rundir + '/x86_64/'
        run.prefix = run.rundir + '/' + run.set
        try:
            os.mkdir(run.prefix)
        except FileExistsError:
            pass
        if 'qualities' in info:
          if info['qualities'] != '':
              run.quality = list(map(int, info['qualities'].split()))
        if 'extra_options' in info:
          run.extra_options = info['extra_options']
        if 'save_encode' in info:
            if info['save_encode']:
                run.save_encode = True
        run.status = 'running'
        run.write_status()
        run_list.append(run)
        video_filenames = video_sets[run.set]['sources']
        if 'collect_estimate_times' in info and info['collect_estimate_times']:
            run.estimator = RDDataCollector(run, video_filenames)
        else:
            run.estimator = RDEstimator(run)
        run.work_items = create_rdwork(run, video_filenames)
        work_list.extend(run.work_items)
        if False:
            if 'ab_compare' in info:
                if info['ab_compare']:
                    abrun = ABRun(info['codec'])
                    abrun.runid = run_id
                    abrun.rundir = config['runs'] + '/' + run_id
                    abrun.log = log_file
                    abrun.set = info['task']
                    abrun.bindir = config['codecs'] + '/' + info['codec']
                    abrun.prefix = run.rundir + '/' + run.set
                    run_list.append(abrun)
                    abrun.work_items.extend(create_abwork(abrun, video_filenames))
                    work_list.extend(abrun.work_items)
                    pass
        self.write(run_id)


class WorkListHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps([w.get_name() for w in work_list]))

class RunStatusHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/json")
        current_time = time.perf_counter()
        runs = []
        for run in run_list:
            run_json = {}
            run_json['run_id'] = run.runid
            run_json['eta'] = max(0, run.eta - current_time)
            run_json['completed'] = 0
            run_json['total'] = 0
            run_json['info'] = run.info
            for work in run.work_items:
                run_json['total'] += 1
                if work.done:
                    run_json['completed'] += 1
            runs.append(run_json)
        self.write(json.dumps(runs))

class MachineUsageHandler(tornado.web.RequestHandler):
    def get(self):
        global machines
        machine_usage = []
        for machine in machines:
            machine_json = {}
            slot_in_use = []
            for slot in machine.slots:
                if slot.work:
                    slot_in_use.append(slot.work.get_name())
                elif slot.busy:
                    slot_in_use.append('busy with no work')
                else:
                    slot_in_use.append('None')
            machine_json['name'] = machine.get_name()
            machine_json['slots'] = slot_in_use
            machine_usage.append(machine_json)
        self.write(json.dumps(machine_usage))

class FreeSlotsHandler(tornado.web.RequestHandler):
    def get(self):
        global free_slots
        slot_text = []
        for slot in free_slots:
            if slot.work:
                slot_text.append(slot.work.get_name())
            elif slot.busy:
                slot_text.append('busy with no work')
            else:
                slot_text.append('None')
        self.write(json.dumps(slot_text))

class ExecuteTick(tornado.web.RequestHandler):
    def get(self):
        scheduler_tick()
        self.write('ok')


def main():
    global free_slots
    global machines
    global slots
    global args
    parser = argparse.ArgumentParser(description='Run AWCY scheduler daemon.')
    parser.add_argument('-machineconf')
    parser.add_argument('-port',default=4000)
    parser.add_argument('-awsgroup', default='AOM Test')
    parser.add_argument('-max-machines', default=3, type=int)
    args = parser.parse_args()
    if args.machineconf:
        machineconf = json.load(open(args.machineconf, 'r'))
        for m in machineconf:
            machines.append(sshslot.Machine(m['host'],m['user'],m['cores'],m['work_root'],str(m['port']),m['media_path']))
        for machine in machines:
            slots.extend(machine.get_slots())
        free_slots.extend(slots)
    app = tornado.web.Application(
        [
            (r"/work_list.json", WorkListHandler),
            (r"/run_status.json", RunStatusHandler),
            (r"/machine_usage.json", MachineUsageHandler),
            (r"/free_slots.json", FreeSlotsHandler),
            (r"/submit", RunSubmitHandler),
            (r"/cancel", CancelHandler),
            (r"/execute_tick",ExecuteTick)
        ],
        static_path=os.path.join(os.path.dirname(__file__), "static"),
        xsrf_cookies=True,
        debug=False,
        )
    app.listen(args.port)
    ioloop = tornado.ioloop.IOLoop.current()
    if not args.machineconf:
        machine_thread = threading.Thread(target=machine_allocator,daemon=True)
        machine_thread.start()
    scheduler_tick()
    ioloop.start()

def machine_allocator():
    global slots
    global free_slots
    global machines
    global work_list
    global run_list
    while 1:
        # start all machines if we don't have any but have work queued
        if len(work_list) and not len(machines):
            rd_print(None, "Starting machines.")
            machines = []
            while not machines:
                machines = awsremote.get_machines(args.max_machines, args.awsgroup)
            for machine in machines:
                slots.extend(machine.get_slots())
            free_slots.extend(slots)
            time.sleep(60*10) # don't shut down for a tleast 10 minutes
        # stop all machines if nothing is running
        slots_busy = False
        for slot in slots:
            if slot.busy:
                slots_busy = True
        if not slots_busy and not len(work_list) and not len(run_list):
            rd_print(None, "Stopping all machines.")
            machines = []
            slots = []
            free_slots = []
            awsremote.stop_machines(args.awsgroup)
        time.sleep(60)

class KeyedEntry:
    def __init__(self, key, data):
        self.key = key
        self.data = data
    def __lt__(self, other):
        return self.key < other.key

def scheduler_tick():
    global free_slots
    global work_list
    global run_list
    global work_done
    active_slots = []
    update_simulation = False
    max_retries = 5
    # look for completed work
    for slot in slots:
        if slot.busy == False and slot.work != None:
            if slot.work.failed == False:
                slot.work.done = True
                work_done.append(slot.work)
                slot.work.run.completed += 1
                slot.work.update_estimator()
                update_simulation = True
                rd_print(slot.work.log,slot.work.get_name(),'finished.')
            elif slot.work.retries < max_retries:
                slot.work.retries += 1
                rd_print(slot.work.log,'Retrying work ',slot.work.get_name(),'...',slot.work.retries,'of',max_retries,'retries.')
                slot.work.failed = False
                work_list.insert(0, slot.work)
            else:
                slot.work.done = True
                work_done.append(slot.work)
                slot.work.run.completed += 1
                rd_print(slot.work.log,slot.work.get_name(),'given up on.')
            slot.work = None
            free_slots.append(slot)
        elif slot.work != None:
            active_slots.append(slot)
    # update the simulation to find etas for runs
    if update_simulation:
        sim_queue = PriorityQueue()
        sim_completed = {}
        for run in run_list:
            sim_completed[id(run)] = run.completed
        current_time = time.perf_counter()
        # load in progress work into the queue
        for slot in active_slots:
            work = slot.work
            remaining = max(0, work.estimate_time() - (current_time - work.start_time))
            sim_queue.put(KeyedEntry(remaining, work))
        sim_work_list = list(work_list)
        # fill any free slots
        for i in range(0, min(len(free_slots), len(sim_work_list))):
            work = sim_work_list.pop(0)
            sim_queue.put(KeyedEntry(work.estimate_time(), work))
        # go through the simulation's main loop until there is no work to add to empty slots
        while len(sim_work_list) != 0:
            finished = sim_queue.get()
            sim_time = finished.key
            work = finished.data
            run = work.run
            sim_completed[id(run)] += 1
            if sim_completed[id(run)] == len(run.work_items):
                run.eta = current_time + sim_time
            new_work = sim_work_list.pop(0)
            sim_queue.put(KeyedEntry(sim_time + new_work.estimate_time(), new_work))
        # go through the simulation's main loop until all the slots are empty
        while not sim_queue.empty():
            finished = sim_queue.get()
            sim_time = finished.key
            work = finished.data
            run = work.run
            sim_completed[id(run)] += 1
            if sim_completed[id(run)] == len(run.work_items):
                run.eta = current_time + sim_time
    # fill empty slots with new work
    if len(work_list) != 0:
        if len(free_slots) != 0:
            slot = free_slots.pop()
            work = work_list.pop(0)
            rd_print(work.log,'Encoding',work.get_name(),'on',slot.machine.host)
            slot.start_work(work)
    # find runs where all work has been completed
    for run in run_list:
        done = True
        for work in run.work_items:
            if work.done == False:
                done = False
        if done:
            run_list.remove(run)
            try:
                run.reduce()
            except Exception as e:
                rd_print(run.log,e)
                rd_print(run.log,'Failed to run reduce step on '+run.runid)
            rd_print(run.log,'Finished '+run.runid)
            run.finish()
    tornado.ioloop.IOLoop.current().call_later(1,scheduler_tick)

if __name__ == "__main__":
    main()

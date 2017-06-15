#!/usr/bin/env python3

import tornado.ioloop
import tornado.web
import os
import codecs
import json
import argparse
import sshslot
import threading
import time
import awsremote
import queue
from work import *
from utility import *

video_sets_f = codecs.open('sets.json','r',encoding='utf-8')
video_sets = json.load(video_sets_f)

machines = []
slots = []
free_slots = []
work_list = []
run_list = []
work_done = []
args = {}
scheduler_tasks = queue.Queue()

config = {
  'runs': '../runs/',
  'codecs': '../'
}

def lookup_run_by_id(run_id):
    for run in run_list:
        if run.runid == run_id:
            return run
    return None

class SchedulerTask:
    def get(self):
        pass

class CancelHandler(tornado.web.RequestHandler):
    def get(self):
        global scheduler_tasks
        run_id = self.get_query_argument('run_id')
        task = CancelTask()
        task.run_id = run_id
        scheduler_tasks.put(task)
        self.write('ok')

class CancelTask(SchedulerTask):
    def __init__(self):
        self.run_id = None
    def run(self):
        global work_list
        global work_done
        run_id = self.run_id
        rd_print(None,'Cancelling '+run_id)
        run = lookup_run_by_id(run_id)
        if not run:
            rd_print(None,'Could not cancel '+run_id+'. run_id not found.')
            return
        run.cancel()
        for work in work_list[:]:
            if work.runid == run_id:
                work_list.remove(work)
                work_done.append(work)
            else:
                rd_print(None, work.runid)
        rd_print(None, len(work_list))

class RunSubmitHandler(tornado.web.RequestHandler):
    def get(self):
        global scheduler_tasks
        run_id = self.get_query_argument('run_id')
        task = SubmitTask()
        task.run_id = run_id
        scheduler_tasks.put(task)
        self.write('ok')

class SubmitTask(SchedulerTask):
    def __init__(self):
        self.run_id = None
    def run(self):
        global work_list
        global run_list
        run_id = self.run_id
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
              run.quality = info['qualities'].split()
        if 'extra_options' in info:
          run.extra_options = info['extra_options']
        if 'save_encode' in info:
            if info['save_encode']:
                run.save_encode = True
        run.status = 'running'
        run.write_status()
        run_list.append(run)
        video_filenames = video_sets[run.set]['sources']
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

class WorkListHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps([w.get_name() for w in work_list]))

class RunStatusHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/json")
        runs = []
        for run in run_list:
            run_json = {}
            run_json['run_id'] = run.runid
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

def scheduler_tick():
    global free_slots
    global work_list
    global run_list
    global work_done
    global scheduler_tasks
    max_retries = 5
    # run queued up tasks
    while not scheduler_tasks.empty():
        task = scheduler_tasks.get()
        try:
            task.run()
        except Exception as e:
            rd_print(None,e)
            rd_print(None,'Task failed.')
    # look for completed work
    for slot in slots:
        if slot.busy == False and slot.work != None:
            if slot.work.failed == False:
                slot.work.done = True
                try:
                    slot.work.write_results()
                except Exception as e:
                    rd_print(None, e)
                    rd_print('Failed to write results for work item',slot.work.get_name())
                work_done.append(slot.work)
                rd_print(slot.work.log,slot.work.get_name(),'finished.')
            elif slot.work.retries < max_retries and not slot.work.run.cancelled:
                slot.work.retries += 1
                rd_print(slot.work.log,'Retrying work ',slot.work.get_name(),'...',slot.work.retries,'of',max_retries,'retries.')
                slot.work.failed = False
                work_list.insert(0, slot.work)
            else:
                slot.work.done = True
                work_done.append(slot.work)
                rd_print(slot.work.log,slot.work.get_name(),'given up on.')
            slot.clear_work()
            free_slots.append(slot)
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

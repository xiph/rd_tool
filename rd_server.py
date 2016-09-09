#!/usr/bin/env python3

import tornado.ioloop
import tornado.web
import os
import codecs
import json
import argparse
import sshslot
import threading
import awsremote
from work import *
from utility import *

video_sets_f = codecs.open('sets.json','r',encoding='utf-8')
video_sets = json.load(video_sets_f)

machines = []
slots = []
taken_slots = []
free_slots = []
work_list = []
run_list = []
work_done = []
args = {}

config = {
  'runs': '../runs/',
  'codecs': '../'
}

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
        run.runid = run_id
        run.rundir = config['runs'] + '/' + run_id
        run.log = log_file
        run.set = info['task']
        run.bindir = config['codecs'] + '/' + info['codec']
        run.prefix = run.rundir + '/' + run.set
        os.mkdir(run.prefix)
        if 'quality' in info:
          run.quality = info['quality']
        if 'extra_options' in info:
          run.extra_options = info['extra_options']
        if 'save_encode' in info:
            if info['save_encode']:
                run.save_encode = True
        run_list.append(run)
        video_filenames = video_sets[run.set]['sources']
        run.work_items = create_rdwork(run, video_filenames)
        work_list.extend(run.work_items)
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

class RunListHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/json")
        runs = []
        for run in run_list:
            run_json = {}
            run_json['run_id'] = run.runid
            run_json['completed'] = 0
            run_json['total'] = 0
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
                else:
                    slot_in_use.append('None')
            machine_json['name'] = machine.get_name()
            machine_json['slots'] = slot_in_use
            machine_usage.append(machine_json)
        self.write(json.dumps(machine_usage))

def main():
    global free_slots
    global machines
    global slots
    global args
    parser = argparse.ArgumentParser(description='Run AWCY scheduler daemon.')
    parser.add_argument('-machineconf')
    parser.add_argument('-port',default=4000)
    parser.add_argument('-awsgroup', default='AOM Test')
    args = parser.parse_args()
    if args.machineconf:
        machineconf = json.load(open(args.machineconf, 'r'))
        for m in machineconf:
            machines.append(sshslot.Machine(m['host'],m['user'],m['cores'],m['work_root'],str(m['port']),m['media_path']))
        for machine in machines:
            slots.extend(machine.get_slots())
        free_slots = slots
    app = tornado.web.Application(
        [
            (r"/work_list.json", WorkListHandler),
            (r"/run_list.json", RunListHandler),
            (r"/machine_usage.json", MachineUsageHandler),
            (r"/submit", RunSubmitHandler),
        ],
        static_path=os.path.join(os.path.dirname(__file__), "static"),
        xsrf_cookies=True,
        debug=True,
        )
    app.listen(args.port)
    ioloop = tornado.ioloop.IOLoop.current()
    if not args.machineconf:
        machine_tick()
    scheduler_tick()
    ioloop.start()

def machine_tick():
    global slots
    global free_slots
    global machines
    # start all machines if we don't have any but have work queued
    # this will intentionally block any scheduling
    if len(work_list) and not len(machines):
        rd_print(None, "Starting machines.")
        machines = awsremote.get_machines(3, args.awsgroup)
        for machine in machines:
            slots.extend(machine.get_slots())
        free_slots = slots
    # stop all machines if nothing is running
    slots_busy = False
    for slot in slots:
        if slot.busy:
            slots_busy = True
    if not slots_busy and not len(work_list):
        rd_print(None, "Stopping all machines.")
        machines = []
        slots = []
        free_slots = []
        awsremote.stop_machines(args.awsgroup)
    tornado.ioloop.IOLoop.current().call_later(60, machine_tick)

def scheduler_tick():
    global free_slots
    max_retries = 50
    # look for completed work
    for slot in taken_slots:
        if slot.busy == False and slot.work != None:
            if slot.work.failed == False:
                slot.work.done = True
                work_done.append(slot.work)
                rd_print(slot.work.log,len(work_done),'finished.')
            elif slot.work.retries < max_retries:
                slot.work.retries += 1
                rd_print(slot.work.log,'Retrying work...',slot.work.retries,'of',max_retries,'retries.')
                work_list.append(slot.work)
            else:
                slot.work.done = True
                work_done.append(slot.work)
                rd_print(slot.work.get_name(),'given up on.')
            slot.work = None
            taken_slots.remove(slot)
            free_slots.append(slot)
    # fill empty slots with new work
    if len(work_list) != 0:
        if len(free_slots) != 0:
            slot = free_slots.pop()
            work = work_list.pop(0)
            slot.work = work
            rd_print(slot.work.log,'Encoding',work.get_name(),'on',slot.machine.host)
            work_thread = threading.Thread(target=slot.execute, args=(work,))
            work_thread.daemon = True
            slot.busy = True
            work_thread.start()
            taken_slots.append(slot)
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
            except e:
                rd_print(run.log,e)
                rd_print(run.log,'Failed to run reduce step on '+run.runid)
            rd_print(run.log,'Finished '+run.runid)
    tornado.ioloop.IOLoop.current().call_later(1,scheduler_tick)

if __name__ == "__main__":
    main()

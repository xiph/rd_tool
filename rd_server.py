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
        if 'quality' in info:
          run.quality = info['quality']
        if 'extra_options' in info:
          run.extra_options = info['extra_options']
        run_list.append(run)
        video_filenames = video_sets[run.set]['sources']
        run.work_items = create_rdwork(run, video_filenames)
        work_list.extend(run.work_items)
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

def main():
    global free_slots
    parser = argparse.ArgumentParser(description='Run AWCY scheduler daemon.')
    parser.add_argument('-machineconf')
    parser.add_argument('-port',default=4000)
    parser.add_argument('-awsgroup', default='AOM Test')
    args = parser.parse_args()
    if args.machineconf:
        machineconf = json.load(open(args.machineconf, 'r'))
        for m in machineconf:
            machines.append(sshslot.Machine(m['host'],m['user'],m['cores'],m['work_root'],str(m['port']),m['media_path']))
    else:
        machines = awsremote.get_machines(3, args.awsgroup)
    for machine in machines:
        slots.extend(machine.get_slots())
    free_slots = slots
    app = tornado.web.Application(
        [
            (r"/work_list.json", WorkListHandler),
            (r"/run_list.json", RunListHandler),
            (r"/submit", RunSubmitHandler),
        ],
        static_path=os.path.join(os.path.dirname(__file__), "static"),
        xsrf_cookies=True,
        debug=True,
        )
    app.listen(args.port)
    ioloop = tornado.ioloop.IOLoop.current()
    scheduler_tick()
    ioloop.start()

retries = 0
max_retries = 50

def scheduler_tick():
    global free_slots
    for slot in taken_slots:
        if slot.busy == False and slot.work != None:
            if slot.work.failed == False:
                work_done.append(slot.work)
                rd_print(slot.work.log,len(work_done),'finished.')
            else:
                retries = retries + 1
                rd_print(slot.work.log,'Retrying work...',retries,'of',max_retries,'retries.')
                work_list.append(slot.work)
            slot.work = None
            taken_slots.remove(slot)
            free_slots.append(slot)
    if len(work_list) != 0:
        if len(free_slots) != 0:
            slot = free_slots.pop()
            work = work_list.pop()
            slot.work = work
            rd_print(slot.work.log,'Encoding',work.get_name(),'on',slot.machine.host)
            work_thread = threading.Thread(target=slot.execute, args=(work,))
            work_thread.daemon = True
            slot.busy = True
            work_thread.start()
            taken_slots.append(slot)
    for run in run_list:
        done = True
        for work in run.work_items:
            if work.done == False:
                done = False
        if done:
            run_list.remove(run)
            run.reduce()
            rd_print(run.log,'Finished '+run.runid)
    tornado.ioloop.IOLoop.current().call_later(1,scheduler_tick)

if __name__ == "__main__":
    main()

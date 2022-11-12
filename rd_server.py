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
import subprocess
from work import *
from utility import *
from work import quality_presets
from smtplib import SMTP_SSL as SMTP
from email.mime.text import MIMEText

config_dir = os.getenv("CONFIG_DIR", os.getcwd())
runs_dst_dir = os.getenv("RUNS_DST_DIR", os.path.join(os.getcwd(), "../runs"))
codecs_src_dir = os.getenv("CODECS_SRC_DIR", os.path.join(os.getcwd(), ".."))

video_sets_f = codecs.open(os.path.join(config_dir, 'sets.json'),'r',encoding='utf-8')
video_sets = json.load(video_sets_f)
smtp_config = json.load(open(os.path.join(config_dir, 'smtp_cfg.json')))

# CTC Configs
# LD : ctc_sets_mandatory
# RA: ctc_sets_mandatory  + ctc_sets_optional
# AI: ctc_sets_mandatory_ai + ctc_sets_optional
# AS: A1 with Downsampling
ctc_sets_mandatory = [
    "aomctc-a1-4k",
    "aomctc-a2-2k",
    "aomctc-a3-720p",
    "aomctc-a4-360p",
    "aomctc-a5-270p",
    "aomctc-b1-syn",
    "aomctc-b2-syn"]
ctc_sets_mandatory_ai = ctc_sets_mandatory + \
    ["aomctc-f1-hires", "aomctc-f2-midres"]
ctc_sets_optional = ["aomctc-g1-hdr-4k",
                     "aomctc-g2-hdr-2k", "aomctc-e-nonpristine"]
ctc_full_presets = ["av2-ra-st", 'av2-ld','av2-ai']
machines = []
slots = []
free_slots = []
work_list = []
run_list = []
run_set_list = []
run_preset_list = []
work_done = []
args = {}
scheduler_tasks = queue.Queue()

config = {
  'runs': runs_dst_dir,
  'codecs': codecs_src_dir,
}

def return_set_list(info_file, codec_id):
    if len(info_file['ctcSets']) > 0:
        if 'aomctc-all' in info_file['ctcSets']:
            if codec_id == 'av2-ai':
                run_set_list = ctc_sets_mandatory_ai + ctc_sets_optional
            elif codec_id == 'av2-ra-st' or codec_id == 'av2-ra':
                run_set_list = ctc_sets_mandatory + ctc_sets_optional
            elif codec_id == 'av2-ld':
                run_set_list = ctc_sets_mandatory
        elif 'aomctc-mandatory' in info_file['ctcSets']:
            if codec_id == 'av2-ra-st' or codec_id == 'av2-ra' or codec_id ==   'av2-ld':
                run_set_list = ctc_sets_mandatory
            elif codec_id == 'av2-ai':
                run_set_list =  ctc_sets_mandatory_ai
        else:
            run_set_list = info_file['ctcSets']
    else:
        run_set_list = [info_file['task']]
    return run_set_list

def lookup_run_by_id(run_id):
    for run in run_list:
        if run.runid == run_id:
            return run
    return None


def generate_email_content(run, set_flag, cfg_flag, all_flag):
    completed_jobs = 0
    total_jobs = 0
    for work in run.work_items:
        total_jobs += 1
        if work.done:
            completed_jobs += 1
    content_string = 'Run ID: %s, \nSet: %s, \nCodec: %s, \nCompleted Jobs: %d, \nTotal Jobs: %d, \nMetadata: %s ' % (
        run.runid, run.set, run.codec, completed_jobs, total_jobs, run.info)
    if set_flag:
        content_string += '\nFinished Encoding for %s set with %s config' % (
            run.set, run.codec)
    if cfg_flag:
        content_string += '\nFinished Encoding all sets for %s config' % (
            run.codec)
    if all_flag:
        content_string += '\nFinished Encoding all the given sets and configs for the RunID %s' % (
            run.runid)
    server_cfg = json.load(open(os.path.join(config_dir, 'config.json')))
    if 'base_url' in server_cfg.keys():
        server_url = server_cfg['base_url']
    else:
        server_url = 'http://' + \
            os.getenv('EXTERNAL_ADDR', 'localhost') + \
            ':' + str(server_cfg['port'])
    content_string += '\nCheck job for more information: ' + \
        server_url + '/?job=' + run.runid
    content_string += '\nJob logs: ' + \
        server_url + '/runs/' + run.runid + '/output.txt'
    return content_string


def submit_email_notification(run, smtp_cfg, set_flag, cfg_flag, all_flag):
    text_subtype = 'plain'
    subject = 'AWCY: Run status: %s' % (run.runid)
    content = generate_email_content(run, set_flag, cfg_flag, all_flag)
    destination = run.info['nick']
    # Do not attempt to do emailing if the Nick is not having email style ie.
    # containing @ symbol to keep it simple
    if '@' not in destination:
        return
    try:
        msg = MIMEText(content, text_subtype)
        msg['Subject'] = subject
        msg['From'] = smtp_cfg['sender']
        msg['To'] = destination

        conn = SMTP(smtp_cfg['smtpserver'])
        conn.set_debuglevel(False)
        conn.login(smtp_cfg['username'], smtp_cfg['password'])
        try:
            conn.sendmail(smtp_cfg['sender'], destination, msg.as_string())
        finally:
            conn.quit()
    except Exception as e:
        rd_print(run.log, "E: Failed to send email, error:", e)


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
        global run_set_list
        global run_preset_list
        run_id = self.run_id
        rundir = config['runs'] + '/' + run_id
        info_file_path = rundir + '/info.json'
        log_file_path = rundir + '/output.txt'
        info_file = open(info_file_path, 'r')
        log_file = open(log_file_path, 'a')
        info = json.load(info_file)
        if len(info['ctcSets']) > 1:
            run_set_list = return_set_list(info, info['codec'])
        else:
              run_set_list = [info['task']]
        if len(info['ctcPresets']) > 1:
            run_preset_list = info['ctcPresets']
            if 'av2-all' in info['ctcPresets']:
                run_preset_list = ctc_full_presets
        else:
            run_preset_list = [info['codec']]
        for this_preset in run_preset_list:
            run_set_list = return_set_list(info, this_preset)
            for this_video_set in sorted(run_set_list):
                run = RDRun(info['codec'])
                run.info = info
                run.runid = run_id
                run.rundir = config['runs'] + '/' + run_id
                run.log = log_file
                run.codec = this_preset
                run.set = this_video_set
                if len(run_preset_list) > 1:
                    run.multicfg = True
                else:
                    run.multicfg = False
                if this_video_set in ['aomctc-f1-hires','aomctc-f2-midres']:
                    run.quality = quality_presets['av2-f']
                rd_print(run.log, "Starting encoding of ", this_video_set, "with", this_preset)
                if 'arch' in info:
                    run.arch = info['arch']
                else:
                    run.arch = 'x86_64'
                run.bindir = run.rundir + '/' + run.arch + '/'
                run.prefix = run.rundir + '/' + run.set
                if len(run_preset_list) > 1:
                    run.prefix = run.rundir + '/' + run.codec + '/' + run.set
                try:
                    prefix_maker = subprocess.run(['mkdir','-p', run.prefix])
                    if prefix_maker.returncode == 0:
                        pass
                    else:
                        print(prefix_maker)
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
                run.set_type = video_sets[run.set].get('type', 'undef')
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
                            abrun.work_items.extend(create_abwork(abrun,    video_filenames))
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
            run_json['set'] = run.set
            run_json['config'] = run.codec
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
        self.set_header("Content-Type", "application/json")

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
    parser.add_argument('-awsgroup', default='nonexistent_group')
    parser.add_argument('-max-machines', default=3, type=int)
    args = parser.parse_args()
    if args.machineconf:
        machineconf = json.load(open(args.machineconf, 'r'))
        for m in machineconf:
            machines.append(sshslot.Machine(m['host'],m['user'],m['cores'],m['work_root'],str(m['port']),m['media_path']))
        for machine in machines:
            slots.extend(machine.get_slots())
        free_slots.extend(reversed(slots))
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
        machine_allocator_tick()
    scheduler_tick()
    ioloop.start()

def machine_allocator_tick():
    global slots
    global free_slots
    global machines
    global work_list
    global run_list
    # start all machines if we don't have any but have work queued
    if len(work_list) and not len(machines):
        rd_print(None, "Starting machines.")
        #awsgroup.start_machines(args.max_machines, args.awsgroup)
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
        #awsremote.stop_machines(args.awsgroup)
    try:
        updated_machines = awsremote.get_machines(args.max_machines, args.awsgroup)
    except:
        tornado.ioloop.IOLoop.current().call_later(60,machine_allocator_tick)
        return
    print(updated_machines)
    for m in machines:
        matching = [um for um in updated_machines if um.host == m.host]
        if len(matching) == 0:
            rd_print(None, "Machine disappeared: " + m.get_name())
            for s in m.slots:
                slots.remove(s)
                try:
                    free_slots.remove(s)
                except:
                    pass
            machines.remove(m)
    for um in updated_machines:
        print(um, um.get_name())
        matching = [m for m in machines if m.host == um.host]
        if len(matching) == 0:
            rd_print(None, "Machine appeared: " + um.get_name())
            new_slots = um.get_slots()
            slots.extend(new_slots)
            free_slots.extend(new_slots)
            machines.append(um)
    tornado.ioloop.IOLoop.current().call_later(60,machine_allocator_tick)

def find_image_work(items, default = None):
    for work in items:
        if work.run.set_type == 'image':
            return work
    return default

def scheduler_tick():
    global slots
    global free_slots
    global work_list
    global run_list
    global run_set_list
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
            elif slot.work.retries < max_retries and not slot.work.run.cancelled and (slot.p.p is None or not slot.p.p.returncode == 98):
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
            work = work_list[0]
            # search for image work if there is only one slot available
            # allows prioritizing image runs without making scheduler the bottleneck
            if len(free_slots) == 0:
                try:
                    work = find_image_work(work_list, work)
                except Exception as e:
                    rd_print(None, e)
                    rd_print(None, 'Finding image work failed.')
            work_list.remove(work)
            rd_print(work.log,'Encoding',work.get_name(),'on',slot.machine.host)
            slot.start_work(work)
    # As we have Work of Works with different sets for same RunID,
    # Create a mechanism to filter and store the results for unique jobs based
    # on sets.
    current_unique_run_list = []
    for this_run in run_list:
        current_unique_run_list.append(this_run.runid)
    current_unique_run_list = list(dict.fromkeys(current_unique_run_list))
    # Make a tracker for given a run
    run_tracker = {}
    # find runs/sub-runs where all work has been completed a given run_id
    for this_run in current_unique_run_list:
        # Create a set-based tracker for unique jobs.
        run_tracker[this_run] = {}
        run_tracker[this_run]['done'] = True
        run_tracker[this_run]['cfg'] = {}
        run_tracker[this_run]['status'] = {}
        #run_tracker[this_run]['sets'] = {}
        ## Part 1: Initialise config for different presets
        for run in run_list:
            if run.runid == this_run:
                run_tracker[this_run]['cfg'][run.codec] = {}
        ## Part 2: Update flags
        for run in run_list:
            if run.runid == this_run:
                run_tracker[this_run]['cfg'][run.codec][run.set] = True
                for work in run.work_items:
                    if work.done == False:
                        run_tracker[this_run]['cfg'][run.codec][run.set] = False
                        run_tracker[this_run]['done'] = False
                        run_tracker[this_run]['status'][run.codec] = False
        ## Part 3: Send updates and curate results.
        for run in run_list:
            if run.runid == this_run:
                if run_tracker[this_run]['cfg'][run.codec][run.set]:
                    rd_print(run.log, "Finished Encoding ", run.set, "set for ", run.codec, "config.")
                    run_list.remove(run)
                    run_tracker[this_run]['done'] = False
                    if len(run.info['ctcSets']) > 1:
                        submit_email_notification(run, smtp_config, set_flag=True, cfg_flag=False, all_flag=False)
                if all(value == True for value in run_tracker[this_run]['cfg'][run.codec].values()):
                    rd_print(run.log, "Finished Encoding", run.codec, "config.")
                    run_tracker[this_run]['status'][run.codec] = True
                    if len(run.info['ctcPresets']) > 1:
                        submit_email_notification(run, smtp_config, set_flag=False, cfg_flag=True, all_flag=False)
                if all(value == True for value in run_tracker[this_run]['status'].values()):
                    run_tracker[this_run]['done'] = True
                    rd_print(run.log, "Finished Encoding all sets for ", run.runid)
                    submit_email_notification(run, smtp_config, set_flag=False, cfg_flag=False, all_flag=True)
                    try:
                        # Explicty set the first Task ID as the Prefix for
                        # average (this taskID is sorted based on priority)
                        run.prefix = run.rundir + '/' + sorted(run_set_list)[0]
                        # Use A2 set for mandatory/all CTC Class
                        if  'aomctc-mandatory' in run.info['ctcSets'] or 'aomctc-all' in run.info['ctcSets']:
                            run.prefix = run.rundir + '/aomctc-a2-2k'
                        if len(run.info['ctcPresets']) > 1:
                            run.prefix = run.rundir + '/' + \
                                run.info['codec'] + '/' + sorted(run_set_list)[0]
                            if 'aomctc-mandatory' in run.info['ctcSets'] or 'aomctc-all' in run.info['ctcSets']:
                                run.prefix = run.rundir + '/' + run.info['codec'] + '/aomctc-a2-2k'
                        run.reduce()
                    except Exception as e:
                        rd_print(run.log,e)
                        rd_print(run.log,'Failed to run reduce step on '+run.runid)
                        rd_print(run.log,'Finished '+run.runid)
                        run.finish()
    tornado.ioloop.IOLoop.current().call_later(1,scheduler_tick)

if __name__ == "__main__":
    main()

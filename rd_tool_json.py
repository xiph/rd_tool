#!/usr/bin/env python2

"""
Encode a set of files on Amazon EC2 instances and save a report with rate-distortion info in JSON format.
"""

import argparse
import bisect
import datetime
from functools import total_ordering
import json
import logging
from multiprocessing import cpu_count
from os import path
import sys
import threading
import time

THIS_DIR = path.dirname(sys.argv[0])
sys.path.append(path.join(THIS_DIR, 'pylib'))
from executor import make_local_pool, run_in_thread, Task, LazyTask, TaskFailed
from encoders import get_encoder, get_encoder_names

REMOTE_DAALA_ROOT = '/home/ec2-user/daala/'
REMOTE_SETS_DIR = '/home/ec2-user/sets/'

TARGET_BITS_PER_PIXEL = [0.05, 0.1]

def make_report(run_id, set_name, sets_dir, daala_root, encoder, pool):
    start_time = datetime.datetime.utcnow()

    set_files = get_sets()[set_name]

    logging.info('Set has %d files', len(set_files))
    total_files.set(len(set_files))

    file_paths = [path.join(sets_dir, set_name, file_name) for file_name in set_files]

    # Start jobs for each file
    file_jobs = {}
    for file_path in file_paths:
        file_jobs[path.basename(file_path)] = run_in_thread(make_report_for_file, [], {
            'run_id': run_id,
            'file_path': file_path,
            'daala_root': daala_root,
            'encoder': encoder,
            'pool': pool,
        })

    # Gather job results, waiting for jobs to finish
    file_reports = {}
    for file_name, job in file_jobs.items():
        result = job.result()
        file_reports[file_name] = result

    return {
        'run_id': run_id,
        'set': set_name,
        'date': start_time.isoformat() + 'Z',
        'files': file_reports,
    }

def make_report_for_file(run_id, file_path, daala_root, encoder, pool):
    """Encode a file at several quality levels and return a report."""
    # Start by gathering information on the file
    file_info = pool.await_task(Task(Task.MAX_PRIORITY, 'y4m_info.py', [file_path]))
    file_size = file_info['bytes']
    file_pixels = file_info['pixels']

    # Make tasks for all possible quality parameters, from lowest quality
    # (high q) to highest (low q). Only the ones accessed by the binary search
    # will actually be run.
    encode_tasks = []
    for q in range(encoder.max_q, encoder.min_q - 1, -1):
    #for q in range(16, 8, -1):
        run_name = '{0}-{1}-{2}'.format(run_id, path.basename(file_path), q)
        task = Task(
            priority = estimate_priority(file_size, q),
            name = 'run_encoder.py',
            arguments = ['--codec', encoder.name(), '--run-name', run_name, '--daala-root', daala_root, str(q), file_path]
        )
        encode_tasks.append(LazyTask(task, pool))

    # Start tasks for extra quality levels
    for q in encoder.default_qualities():
        encode_tasks[encoder.max_q - q].ensure_enqueued()

    # Start searches for binary tasks in separate threads
    # They'll be accessing the same encode_tasks array, sharing the results
    target_bpp_jobs = {}
    for bpp in TARGET_BITS_PER_PIXEL:
        target_size = bytes_for_bpp(bpp, file_pixels)
        target_bpp_jobs[str(bpp)] = run_in_thread(search_for_size, [encode_tasks, target_size])

    # Run search tasks to completion and gather the results
    bpp_to_quality = {}
    for bpp, job in target_bpp_jobs.items():
        if job.result() == None:
            bpp_to_quality[bpp] = None
        else:
            bpp_to_quality[bpp] = encode_tasks[job.result()].result()['quality']

    # Collect info from the tasks that have been run
    encode_info = []
    for task in encode_tasks:
        if task.is_enqueued_or_completed():
            try:
                result = task.result()
            except TaskFailed as e:
                logging.warning('Task failed: %r', e)
                result = {'error': repr(e)}
            encode_info.append(result)

    completed_files.increment()
    return {
        'info': file_info,
        'encodes': encode_info,
        'bpp_to_quality': bpp_to_quality,
    }


@total_ordering
class TargetSize:
    """Compares itself to encode tasks using the encoded file size"""
    def __init__(self, target_bytes):
        self.target_bytes = target_bytes
    def __lt__(self, encode_task):
        return self.target_bytes < encode_task.result()['bytes']
    def __eq__(self, encode_task):
        return self.target_bytes == encode_task.result()['bytes']


def search_for_size(encode_tasks, target_size):
    """Search for an encode smaller or equal to a target size.
    Returns the index of the encode, or None if no smaller encodes are found."""
    right_of_target = bisect.bisect_right(encode_tasks, TargetSize(target_size))
    if right_of_target == 0:
        return None
    else:
        return right_of_target - 1


def get_sets():
    return json.load(open(path.join(THIS_DIR, 'sets.json'), 'r'))

def estimate_priority(file_size, quality):
    """
    >>> estimate_priority(1e7, 10) < estimate_priority(1e6, 10)
    True
    >>> estimate_priority(1e6, 10) < estimate_priority(1e6, 50)
    True
    >>> estimate_priority(5000, 10) < estimate_priority(5500, 12)
    False
    >>> estimate_priority(5000, 10) < estimate_priority(5500, 100)
    True
    """
    # Do a very rough estimate of running time based on file size and quality
    # The idea is that we want to run the longer-running tasks first, so we
    # don't end up waiting for a single long-running task at the end while the
    # rest of the cores sit idle.
    from math import atan
    return 5 - atan(file_size / atan(2 + quality / 10.0))

def bytes_for_bpp(bpp, pixels):
    return (bpp * pixels) // 8


class Counter:
    """Atomic counter for stats"""
    def __init__(self):
        self.lock = threading.Lock()
        self._value = 0
    def set(self, value):
        with self.lock: self._value = value
    def get(self):
        with self.lock: return self._value
    def increment(self, increment=1):
        with self.lock: self._value += increment
    def decrement(self, decrement=1):
        self.increment(-decrement)

enqueued_tasks = Counter()
executing_tasks = Counter()
completed_tasks = Counter()
failed_tasks = Counter()
total_tasks = Counter()
completed_files = Counter()
total_files = Counter()

def print_progress(delay):
    while True:
        time.sleep(delay)
        logging.info("%d out of %d files completed.", completed_files.get(), total_files.get())
        logging.info("%d tasks waiting, %d tasks running, %d tasks completed, %d tasks failed", enqueued_tasks.get(), executing_tasks.get(), completed_tasks.get(), failed_tasks.get())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', default='unnamed_run', help='name to identify the run')
    parser.add_argument('--codec', default='daala', choices=get_encoder_names(), help='codec to use')
    parser.add_argument('--sets-dir', default=REMOTE_SETS_DIR, help='directory with files to encode, organized by set')
    parser.add_argument('--set', required=True, help='name of file set to encode')
    parser.add_argument('--daala-root', default=REMOTE_DAALA_ROOT, help='path to daala')
    parser.add_argument('--progress-interval', type=int, default=30, help='how often to print progress report')
    parser.add_argument('--verbose', '-v', action='store_true', help='more verbose logging')
    parser.add_argument('--quiet', '-q', action='store_true', help='less verbose logging')
    args = parser.parse_args()

    if args.quiet:
        loglevel = logging.WARNING
    elif args.verbose:
        loglevel = logging.DEBUG
    else:
        loglevel = logging.INFO

    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(name)s: %(message)s', level=loglevel)

    encoder = get_encoder(args.codec)
    pool = make_local_pool(THIS_DIR, num_threads=cpu_count())

    # progress tracking
    pool.set_on_enqueue(lambda: (total_tasks.increment(), enqueued_tasks.increment()))
    pool.set_on_execute(lambda: (enqueued_tasks.decrement(), executing_tasks.increment()))
    pool.set_on_complete(lambda: (executing_tasks.decrement(), completed_tasks.increment()))
    pool.set_on_failure(lambda: (executing_tasks.decrement(), failed_tasks.increment()))

    if not args.quiet:
        progress_printer = threading.Thread(target=print_progress, args=[args.progress_interval])
        progress_printer.daemon = True
        progress_printer.start()

    start_time = time.time()
    report = make_report(
        run_id = args.run_id,
        set_name = args.set,
        sets_dir = args.sets_dir,
        daala_root = args.daala_root,
        encoder = encoder,
        pool = pool,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    end_time = time.time()

    logging.info('Completed in %d seconds', int(round(end_time - start_time)))
    logging.info('Total %d tasks, %d completed, %d failed', total_tasks.get(), completed_tasks.get(), failed_tasks.get())

    pool.shutdown()


if __name__ == '__main__':
    main()

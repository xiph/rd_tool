#!/usr/bin/env python2
"""
Code for running task concurrently on remote servers via SSH
"""

from collections import namedtuple
import json
import logging
from os import path
import Queue as queue
import subprocess
import threading

log = logging.getLogger('executor')


def make_local_pool(rd_tool_dir, num_threads=1):
    """Get a pool that executes tasks by running them on the local machine."""
    task_queue = queue.PriorityQueue()
    executor = LocalMachineExecutor(rd_tool_dir)
    threads = [Worker(task_queue, executor) for i in range(num_threads)]
    for thread in threads:
        thread.start()
    log.debug('Created local executor with %d workers', len(threads))
    return Pool(task_queue, threads, executor)


def run_in_thread(func, args=[], kwargs={}):
    """Call function in a new thread and return a future that will receive the return value."""
    result_future = Future()
    def call_func():
        try:
            result = func(*args, **kwargs)
        except BaseException as e:
            log.debug('Thread failed:', exc_info=True)
            result_future.set_exception(e)
        else:
            result_future.set_result(result)
    thread = threading.Thread(target=call_func)
    thread.daemon = True
    thread.start()
    return result_future


class Future:
    def __init__(self):
        self._done = threading.Event()
        self._failed = False
        self._exception = None
        self._result = None

    def set_result(self, result):
        """Set the result of this future"""
        if self._done.is_set():
            raise Exception('Future can only be resolved once')
        self._result = result
        self._done.set()

    def set_exception(self, exception):
        """Set an exception to be raised by result()"""
        if self._done.is_set():
            raise Exception('Future can only be resolved once')
        self._failed = True
        self._exception = exception
        self._done.set()

    def result(self):
        """Get the result of the future. Blocks until the future is done."""
        self._done.wait()
        if self._failed:
            raise self._exception
        return self._result


class Task(namedtuple('Task', 'priority, name, arguments')):
    """Represents a task to be executed
    Tasks are placed under the task/ folder, are run with the passed arguments,
    and output a JSON line that is returned as the result.
    If multiple tasks are waiting to be executed, the task with the lowest
    priority should run first.
    """
    # We inherit a sort order from namedtuple

    MAX_PRIORITY = 0

    def __init__(self, priority, name, arguments):
        super(Task, self).__init__(priority, name, arguments)
        self.future = Future()

    def set_result(self, result):
        """Set the result, or a TaskFailed exception if the task failed"""
        log.debug('Got result %r for %r', result, self)
        self.future.set_result(result)

    def set_exception(self, exception):
        log.debug('Got exception %r for %r', exception, self)
        self.future.set_exception(exception)

    def result(self):
        """Get the result of the task. Blocks until the task is done. Throws TaskFailed if the task failed."""
        return self.future.result()


class LazyTask:
    """Wrapper for Task that lazily executes it when the result is accessed."""
    def __init__(self, task, pool):
        self.task = task
        self.pool = pool
        self.enqueued = False
        self.enqueue_lock = threading.Lock()

    def ensure_enqueued(self):
        with self.enqueue_lock:
            if not self.enqueued:
                self.pool.enqueue_task(self.task)
                self.enqueued = True

    def is_enqueued_or_completed(self):
        """Check if the wrapped task is enqueued or completed"""
        with self.enqueue_lock:
            return self.enqueued

    def result(self):
        """Get the result of the task, blocking until ready."""
        self.ensure_enqueued()
        return self.task.result()


class TaskFailed(Exception):
    pass


class Worker(threading.Thread):
    """A worker thread represents one machine slot.
    It grabs tasks from the queue and runs them with the executor.
    """

    def __init__(self, task_queue, executor):
        super(Worker, self).__init__()
        self.task_queue = task_queue
        self.executor = executor
        self._stop = threading.Event()
        self.daemon = True

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            try:
                task = self.task_queue.get(timeout=1)
                self.executor.execute(task)
            except queue.Empty:
                pass


class Pool:
    def __init__(self, task_queue, threads, executor):
        self.task_queue = task_queue
        self.threads = threads
        self.stopped = False
        self.executor = executor
        self._on_enqueue = None

    def await_task(self, task):
        """Wait for a task to execute and return the result"""
        self.enqueue_task(task)
        return task.result()

    def enqueue_task(self, task):
        """Execute a task asynchronously. The result is stored in the task."""
        if self.stopped:
            raise RuntimeError("Cannot run tasks after shutdown")
        log.debug('Enqueueing task %r', task)
        if self._on_enqueue is not None:
            self._on_enqueue()
        self.task_queue.put(task)

    def shutdown(self):
        self.stopped = True
        for thread in self.threads:
            thread.stop()
        log.debug('Waiting for workers...')
        for thread in self.threads:
            thread.join()
        log.debug('Workers stopped!')
        while not self.task_queue.empty():
            self.task_queue.get().set_exception(TaskFailed('Shutdown'))

    def set_on_enqueue(self, on_enqueue):
        self._on_enqueue = on_enqueue

    def set_on_execute(self, on_execute):
        self.executor.on_execute = on_execute

    def set_on_complete(self, on_complete):
        self.executor.on_complete = on_complete

    def set_on_failure(self, on_failure):
        self.executor.on_failure = on_failure


class LocalMachineExecutor:
    """Executor that runs tasks locally."""

    on_execute = None
    on_complete = None
    on_failure = None
    def __init__(self, rd_tool_dir):
        self.rd_tool_dir = rd_tool_dir

    def execute(self, task):
        """Run a task and set its result. Called by Worker threads."""
        if self.on_execute:
            self.on_execute()
        task_path = path.join(self.rd_tool_dir, 'tasks', task.name)
        try:
            cmd = [task_path] + task.arguments
            log.debug('Running command %r', cmd)
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            result = json.loads(output)
            task.set_result(result)
            if self.on_complete:
                self.on_complete()
            return
        except subprocess.CalledProcessError as e:
            task.set_exception(TaskFailed('{0} failed with return code {1} and output "{2}"'.format(task, e.returncode, e.output)))
        except ValueError as e:
            task.set_exception(TaskFailed('{0} returned unparsable output "{1}"'.format(task, output)))
        except BaseException as e:
            task.set_exception(TaskFailed('{0} failed with unhandled exception "{1}"'.format(task, e)))
        if self.on_failure:
            self.on_failure()

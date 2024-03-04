# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import functools
import logging
import queue

from gi.repository import GLib

log = logging.getLogger('gajim.c.m.task_manager')


class TaskManager:
    def __init__(self) -> None:
        self._timeout: int | None = None
        self._queue: queue.PriorityQueue[Task] = queue.PriorityQueue()

    def _start_worker(self) -> None:
        self._timeout = GLib.timeout_add_seconds(2, self._process_queue)

    def _process_queue(self) -> bool:
        log.info('%s tasks queued', self._queue.qsize())
        requeue: list[Task] = []
        while not self._queue.empty():
            task = self._queue.get_nowait()
            if task.is_obsolete():
                log.info('Task obsolete: %r', task)
                continue

            if not task.preconditions_met():
                # precondition_met() can change the obsolete flag, so we need
                # to check again here
                if task.is_obsolete():
                    log.info('Task obsolete: %r', task)
                else:
                    requeue.append(task)
                continue

            log.info('Execute task %r', task)
            task.execute()
            self._requeue_tasks(requeue)
            return True

        if self._requeue_tasks(requeue):
            # Queue is empty, but there are tasks to requeue
            # don't stop worker
            return True

        # Queue is empty, stop worker
        self._timeout = None
        return False

    def _requeue_tasks(self, tasks: list[Task]) -> bool:
        if not tasks:
            return False

        for task in tasks:
            log.info('Requeue task (preconditions not met): %r', task)
            self._queue.put_nowait(task)
        return True

    def add_task(self, task: Task) -> None:
        log.info('Adding task: %r', task)
        self._queue.put_nowait(task)
        if self._timeout is None:
            self._start_worker()


@functools.total_ordering
class Task:
    def __init__(self, priority: int = 0) -> None:
        self.priority = priority
        self._obsolete = False

    def is_obsolete(self) -> bool:
        return self._obsolete

    def set_obsolete(self) -> None:
        self._obsolete = True

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Task):
            raise NotImplementedError
        return self.priority < other.priority

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Task):
            raise NotImplementedError
        return other.priority == self.priority

    def execute(self) -> None:
        raise NotImplementedError

    def preconditions_met(self) -> bool:
        raise NotImplementedError

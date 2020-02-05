#!/usr/bin/python3
# Copyright (c) 2020 by Fred Morris Tacoma WA
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Collecting and Reporting Operational Statistics.


Your application will generally allocate a StatisticsFactory as part of its general
initialization. Its factory method will then be called to allocate a (named)
StatisticsCollector.

At the start of every measured activity you will call the StatisticsCollector.start_timer()
method, returning a timer instance; and at the end of the measured activity you will call
timer.stop().

Finally when you want a snapshot of the statistics, you will call your StatisticsFactory's
stats() method, which will return the aggregated statistics from all of the
StatisticsCollectors it is managing.
"""

from time import time
from threading import Lock

class RingBuffer(object):
    """Used for things which need to be averaged."""

    # Ostensibly each bucket is for 1 second of data. A few extra buckets guarantees us
    # a full minute's worth of complete data.
    BUCKETS = 63
    ONE = 1
    TEN = 10
    SIXTY = 60

    def __init__(self, zero=0):
        self.buffer = [zero] * self.BUCKETS
        self.index = 0
        self.current_second = int(time())
        self.zero = zero
        return
    
    def retire_bucket(self):
        """To be overridden by subclasses to finalize a retiring bucket."""
        pass
    
    def update_bucket(self, value):
        """To be overridden by subclasses to update a bucket with an additional value."""
        pass
    
    def retire_elapsed_buckets(self, n):
        for i in range(n):
            self.retire_bucket()
            self.index += 1
            if self.index >= len(self.buffer):
                self.index = 0
            self.buffer[self.index] = self.zero
        return
    
    def make_seconds_current(self):
        now_seconds = int(time())
        elapsed_seconds = now_seconds - self.current_second
        if elapsed_seconds:
            self.retire_elapsed_buckets(elapsed_seconds)
        self.current_second = now_seconds
        return
        
    def add(self, value):
        """This is what you call with new data!"""
        self.make_seconds_current()
        self.update_bucket(value)
        return
    
    def stats(self):
        """Return a statistics summary."""
        self.make_seconds_current()
        j = self.index - 1
        if j < 0:
            j = len(self.buffer) - 1
        v = self.buffer[j]
        minimum = v
        maximum = v
        accum = v
        one = v
        for i in range(self.TEN - self.ONE):
            j -= 1
            if j < 0:
                j = len(self.buffer) - 1
            v = self.buffer[j]
            if minimum > v:
                minimum = v
            if maximum < v:
                maximum = v
            accum += v
        ten = accum / self.TEN
        for i in range(self.SIXTY - self.TEN):
            j -= 1
            if j < 0:
                j = len(self.buffer) - 1
            v = self.buffer[j]
            if minimum > v:
                minimum = v
            if maximum < v:
                maximum = v
            accum += v
        sixty = accum / self.SIXTY
        return dict(minimum=minimum, maximum=maximum, one=one, ten=ten, sixty=sixty)
            
class AveragingRingBuffer(RingBuffer):
    def __init__(self, zero=0):
        RingBuffer.__init__(self, zero)
        self.count = 0
        return
    
    def retire_bucket(self):
        if self.count:
            self.buffer[self.index] /= self.count
        self.count = 0
        return
    
    def update_bucket(self, value):
        self.buffer[self.index] += value
        self.count += 1
        return

class LevelingRingBuffer(RingBuffer):
    def __init__(self, zero=0):
        RingBuffer.__init__(self, zero)
        self.accum = zero
        return
    
    def retire_bucket(self):
        self.buffer[self.index] = self.accum
        return
    
    def update_bucket(self, value):
        self.accum += value
        return
    
class CountingRingBuffer(RingBuffer):
    def retire_bucket(self):
        return
    
    def update_bucket(self, value):
        self.buffer[self.index] += value
        return
    
class AbstractStatisticsCollector(object):
    """Collect statistics over time about something and be able to report about it.
    
    (Thread safe) locking is used, although we're never actually going to do anything
    which releases the GIL in a critical section."""
    def __init__(self, name):
        """Initialize the collector.
        
        name    An identifier for the thing about which statistics are being collected.
        """
        pass
    def start_timer(self):
        """Call this at the start of the named event.
        
        It returns a StatisticsTimer instance. When the event ends you will call that
        instance's stop() method.
        """
        pass
    def stop_timer(self, elapsed):
        """You won't call this method directly."""
        pass
    def stats(self):
        """You won't call this method directly."""
        pass

class StatisticsTimer(object):
    """A thing that a StatisticsCollector produces for context while timing."""

    def __init__(self, collector):
        self.collector = collector
        self.start = time()
        return
    
    def stop(self):
        self.collector.stop_timer(time() - self.start)
        return

class StatisticsCollector(AbstractStatisticsCollector):
    """Collect statistics over time when we know what those statistics are for.
    
    This is the default statistics collector, it assumes you know a priori the
    name of the event you're about to process.
    
    It collects:
    
    * Elapsed Time
    * Depth of Queue (how many of the events are awaiting processing)
    * Number of Events per second
    """
    
    def __init__(self, name):
        self.name = name
        self.elapsed_time = AveragingRingBuffer(0.0)
        self.depth = LevelingRingBuffer(0)
        self.n_per_sec = CountingRingBuffer(0)
        self.lock = Lock()
        return
        
    def start_timer(self):
        self.lock.acquire()
        self.depth.add(1)
        self.n_per_sec.add(1)
        self.lock.release()
        return StatisticsTimer(self)
    
    def stop_timer(self, elapsed):
        """Called by expiring StatisticsTimers."""
        self.lock.acquire()
        self.elapsed_time.add(elapsed)
        self.depth.add(-1)
        self.lock.release()
        return
    
    def stats(self):
        self.lock.acquire()
        statistics = dict( name=self.name,
                           elapsed=self.elapsed_time.stats(),
                           depth=self.depth.stats(),
                           n_per_sec=self.n_per_sec.stats()
                         )
        self.lock.release()
        return (statistics,)

class UndeterminedStatisticsTimer(StatisticsTimer):
    """For use with the UndeterminedStatisticsCollector."""
    
    def stop(self, name):
        """Stop timing the event.
        
        name    indicates the type of event it turned out to be.
        """
        self.collector.stop_timer((time() - self.start), name)
        return

class UndeterminedStatisticsCollector(AbstractStatisticsCollector):
    """Collect statistics when we're not quite sure what we're collecting stats for.
    
    This collector is for the case where the processing you're doing will ultimately
    determine the what kind of event it is.

    It collects:
        * Elapsed Time
        * Number of Events per second
    
    Depth of Queue cannot be collected because we won't know what queue we're "in"
    until we're done with the processing.
    """
    def __init__(self, names):
        self.collectors = {
                name: { 'elapsed_time': AveragingRingBuffer(0.0), 'n_per_sec': CountingRingBuffer(0) }
                for name in names
            }
        self.lock = Lock()
        return
        
    def start_timer(self):
        return UndeterminedStatisticsTimer(self)
    
    def stop_timer(self, elapsed, name):
        """Called by expiring StatisticsTimers."""
        self.lock.acquire()
        collector = self.collectors[name]
        collector['elapsed_time'].add(elapsed)
        collector['n_per_sec'].add(1)
        self.lock.release()
        return
    
    def stats(self):
        self.lock.acquire()
        statistics = (
                dict( name=collector,
                      elapsed=self.collectors[collector]['elapsed_time'].stats(),
                      n_per_sec=self.collectors[collector]['n_per_sec'].stats()
                    )
                for collector in self.collectors.keys()
            )
        self.lock.release()
        return statistics

class StatisticsFactory(object):
    """Create federated statistics so that they can be reported on and managed together."""

    def __init__(self, collector=StatisticsCollector):
        self.collectors = []
        self.collector = collector
        return
    
    def Collector(self, *args, using=None):
        """Allocates a collector with the supplied name."""
        collector = (using or self.collector)(*args)
        self.collectors.append(collector)
        return collector

    def stats(self):
        return [ collection for collector in self.collectors for collection in collector.stats() ]


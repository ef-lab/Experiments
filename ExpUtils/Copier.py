import time
from multiprocessing import Process, Queue, Event
from shutil import copyfile


class Copier:
    def __init__(self):
        self.queue = Queue()
        self.thread_end = Event()
        self.copying = Event()
        self.thread_runner = Process(target=self.dequeue, args=(self.queue, self.thread_end, self.copying))

    def run(self):
        self.thread_runner.start()

    def append(self, source, target):
        self.queue.put({'source': source, 'target': target})

    def dequeue(self, q, thread_end, copying):
        while not thread_end.is_set():
            if not q.empty():
                if not copying.is_set():
                    copying.set()
                data = q.get()
                copyfile(data['source'], data['target'])
                print('Done copying')
            else:
                if copying.is_set():
                    copying.clear()
                time.sleep(.1)

    def exit(self):
        while not self.queue.empty():
            time.sleep(.1)
        self.thread_end.set()
        self.thread_runner.join()

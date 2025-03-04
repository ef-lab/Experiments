import time, os
from multiprocessing import Process, Queue, Event
from shutil import copyfile, copytree


class Copier:
    def __init__(self):
        self.queue = Queue()
        self.thread_end = Event()
        self.pause = Event()
        self.copying = Event()
        self.thread_runner = Process(target=self.dequeue, args=(self.queue, self.thread_end, self.copying, self.pause))

    def run(self):
        self.thread_runner.start()

    def append(self, source, target):
        self.queue.put({'source': source, 'target': target})

    def dequeue(self, q, thread_end, copying, thread_pause):
        while not thread_end.is_set():
            if not q.empty() and not thread_pause.is_set():
                if not copying.is_set():
                    copying.set()
                data = q.get()
                os.makedirs(os.path.dirname(data['target']), exist_ok=True)
                if os.path.isdir(data['source']):
                    copytree(data['source'], data['target'], dirs_exist_ok=True)
                else:
                    copyfile(data['source'], data['target'])
                print('Done copying')
            else:
                if copying.is_set():
                    copying.clear()
                time.sleep(.1)

    def exit(self):
        if self.pause.is_set(): self.pause.clear()
        while not self.queue.empty():
            time.sleep(.1)
        self.thread_end.set()
        #self.thread_runner.join()

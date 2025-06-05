import time, h5py, numpy
from multiprocessing import Process, Queue, Manager, Event
from multiprocessing.managers import BaseManager


class Dataset(object):
    def __init__(self, datapath):
        self.datasets = dict()
        self.datapath = datapath

    def createDataset(self, dataset, shape, dtype=numpy.int16, compression="gzip", chunk_len=1):
        self.datasets[dataset] = self.h5Dataset(self.datapath, dataset, shape, dtype, compression, chunk_len)

    def get(self, dataset):
        return self.datasets[dataset]

    def update_i(self, dataset):
        self.datasets[dataset].i += 1

    class h5Dataset():
        def __init__(self, datapath, dataset, shape, dtype=numpy.uint16, compression="gzip", chunk_len=1):
            with h5py.File(datapath, mode='a') as h5f:
                self.i = 0
                self.shape = shape
                self.dtype = dtype
                h5f.create_dataset(
                    dataset,
                    shape=(0,) + shape,
                    maxshape=(None,) + shape,
                    dtype=dtype,
                    compression=compression,
                    chunks=(chunk_len,) + shape)


class Writer(object):
    def __init__(self, datapath):
        self.datapath = datapath
        self.queue = Queue()
        self.thread_end = Event()
        BaseManager.register('Dataset', Dataset)
        manager = BaseManager()
        manager.start()
        self.datasets = manager.Dataset(datapath)
        self.thread_runner = Process(target=self.dequeue, args=(self.queue, self.datasets, self.thread_end))
        self.thread_runner.start()
        self.writing = True

    def append(self, dataset, data):
        self.queue.put({'dataset': dataset, 'data': data})

    def dequeue(self, q, datasets, thread_end):
        while not thread_end.is_set():
            if not q.empty():
                values = q.get()
                d = datasets.get(values['dataset'])
                with h5py.File(self.datapath, mode='a') as h5f:
                    dset = h5f[values['dataset']]
                    dset.resize((d.i + 1,) + d.shape)
                    dset[d.i] = [values['data']]
                    datasets.update_i(values['dataset'])
                    h5f.flush()
            else:
                time.sleep(.1)

    def exit(self):
        while not self.queue.empty():
            time.sleep(.1)
        self.thread_end.set()
        #self.thread_runner.join()
        self.writing = False
        print('Done recording')
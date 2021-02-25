# !/usr/bin/env python
from PyQt5 import uic, QtWidgets
from PyQt5.QtGui import QPixmap
import time, h5py, os,gi, numpy, datetime, threading
from queue import Queue
gi.require_version('Aravis', '0.8')
from gi.repository import Aravis

class Writer(object):
    def __init__(self, datapath):
        self.datapath = datapath
        self.queue = Queue()
        self.datasets = dict()
        self.thread_end = threading.Event()
        self.thread_runner = threading.Thread(target=self.dequeue)  # max insertion rate of 10 events/sec
        self.thread_runner.start()

    def createDataset(self, dataset, shape, dtype=numpy.int16, compression="gzip", chunk_len=1):
        self.datasets[dataset] = self.h5Dataset(self.datapath, dataset, shape, dtype, compression, chunk_len)

    def append(self, dataset, data):
        self.queue.put({'dataset': dataset, 'data': data})

    def dequeue(self):
        while not self.thread_end.is_set():
            if not self.queue.empty():
                values = self.queue.get()
                with h5py.File(self.datapath, mode='a') as h5f:
                    dset = h5f[values['dataset']]
                    dset.resize((self.datasets[values['dataset']].i + 1,) + self.datasets[values['dataset']].shape)
                    dset[self.datasets[values['dataset']].i] = [values['data']]
                    self.datasets[values['dataset']].i += 1
                    h5f.flush()
            else:
                time.sleep(.1)

    def exit(self):
        while not self.queue.empty():
            time.sleep(.1)
        self.thread_end.set()
        self.thread_runner.join()
        print(self.thread_runner.is_alive())

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


class Camera():
    def __init__(self):
        self.fps = 20
        self.exposure_time = 45000

        Aravis.enable_interface("Fake")
        #self.camera = Aravis.Camera.new(None)
        self.camera = Aravis.Camera.new('Fake_1')
        self.iframe = 0
        #self.dtype = numpy.uint16
        #self.camera.set_pixel_format(Aravis.PIXEL_FORMAT_MONO_16)
        self.dtype = numpy.uint8
        self.camera.set_pixel_format(Aravis.PIXEL_FORMAT_MONO_8)
        self.camera.get_payload()
        self.camera.set_region(180, 0, 600, 600)
        [xbin, ybin] = self.camera.get_binning()
        if xbin == 1:
            self.camera.set_binning(1, 2)
            self.camera.set_binning(2, 2)
        #self.camera.set_exposure_time_auto(False)
        #self.camera.set_gain_auto(False)
        #self.camera.set_gain(0)
        #self.camera.set_exposure_time(self.exposure_time)
        self.camera.set_frame_rate(self.fps)
        payload = self.camera.get_payload()
        [self.x, self.y, self.width, self.height] = self.camera.get_region()
        self.stream = self.camera.create_stream(None, None)
        for i in range(0, 100):
            self.stream.push_buffer(Aravis.Buffer.new_allocate(payload))
        self.setup()

    def set_frame_rate(self, fps):
        self.fps = fps
        self.camera.set_frame_rate(fps)

    def set_exposure_time(self, exposure_time):
        self.exposure_time = exposure_time * 1000
        self.camera.set_exposure_time(exposure_time * 1000)

    def setup(self):
        self.thread_end = threading.Event()
        self.save = threading.Event()
        self.thread_runner = threading.Thread(target=self.capture)  # max insertion rate of 10 events/sec
        self.queue = Queue()

    def set_queue(self, q):
        self.queue = q

    def start(self):
        self.camera.start_acquisition()
        self.thread_runner.start()

    def rec(self, filename=''):
        now = datetime.datetime.now()
        animal_id = 0
        session = 0
        filename = '%s_%s.h5' % (filename, now.strftime('%Y-%m-%d_%H-%M-%S'))
        print('Starting the recording of %s' % filename)
        self.saver = Writer(filename)
        self.saver.createDataset('frames', shape=(self.width, self.height, 1), dtype=self.dtype)
        self.saver.createDataset('timestamps', shape=(1,), dtype=numpy.double)
        self.saver.createDataset('indexes', shape=(1,))
        self.iframe = 0
        self.save.set()

    def stop(self):
        print('Wrote %d frames' % self.iframe)
        self.save.clear()
        self.saver.exit()

    def capture(self):
        while not self.thread_end.is_set():
            image = self.stream.pop_buffer()
            if image:
                dat = numpy.ndarray(buffer=image.get_data(), dtype=self.dtype, shape=(600, 600, 1))
                # saver.append('sys_timestamps',time.time())
                if self.save.is_set():
                    print('Saving frame %d' % self.iframe)
                    self.iframe += 1
                    self.saver.append('timestamps', image.get_system_timestamp() * 1e-9)
                    self.saver.append('frames', dat)
                    self.saver.append('indexes', self.iframe)
                self.stream.push_buffer(image)
                self.queue.put(dat)

    def quit(self):
        self.thread_end.set()
        self.camera.stop_acquisition()
        self.thread_runner.join()
        print(self.thread_runner.is_alive())
        self.saver.exit()


class MasterRunner(QtWidgets.QWidget):
    def __init__(self, shape=(600, 600), dtype=numpy.int16):
        super(MasterRunner, self).__init__()
        self.queue = Queue()
        self.dtype = dtype
        self.shape = shape
        self.cam = Camera()

        # Create a queue to share data between process
        self.cam.set_queue(self.queue)
        self.cam.start()

        # load ui
        path = os.path.join(os.path.dirname(__file__), "form.ui")
        self.ui = uic.loadUi(path, self)

        # handle inputs
        self.ui.stop_button.clicked.connect(self.cam.stop)
        self.ui.rec_button.clicked.connect(lambda: self.cam.rec('%s_%s' % (self.ui.animal_input.text(),
                                                                           self.ui.session_input.text())))

        # set view window
        self.scene = QtWidgets.QGraphicsScene()
        self.ui.graphicsView.setScene(self.scene)
        self.ui.graphicsView.show()
        self.present = threading.Thread(target=self.updateplot)
        self.thread_end = threading.Event()
        self.present.start()

    def updateplot(self):
        while self.queue.qsize() > 1 and not self.thread_end.is_set():
            image = self.queue.get()
            self.scene.clear()
            self.scene.addPixmap(image)
            self.ui.graphicsView.update()

    def quit(self):
        print('stopping')
        self.thread_end.set()
        self.cam.stop()
        self.cam.quit()
        print('stopped')
        # self.simulate.kill()


if __name__ == "__main__":
    MainEventThread = QtWidgets.QApplication([])
    MainApp = MasterRunner()
    MainApp.show()
    MainEventThread.exec()

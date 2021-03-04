import time, numpy, datetime, threading
import multiprocessing as mp
from Writer import Writer


class Camera:
    def __init__(self):
        import matplotlib.image as mpimg
        img = mpimg.imread('image.png')
        self.fps = 10
        self.exposure_time = 45000
        self.iframe = 0
        self.img = img[:, :, 1]
        self.dtype = numpy.uint8
        sz = numpy.shape(img)
        self.width = sz[0]
        self.height = sz[1]
        self.setup()

    def setup(self):
        mgr = mp.Manager()
        self.namespace = mgr.Namespace()
        self.namespace.fps = self.fps
        self.namespace.scale = 255

        self.cam_queue = mp.Queue()
        self.capture_end = mp.Event()
        self.capture_runner = mp.Process(target=self.capture, args=(self.namespace,))
        self.capture_runner.start()
        self.save = threading.Event()
        self.thread_end = threading.Event()
        self.thread_runner = threading.Thread(target=self.dequeue, args=(self.cam_queue,))  # max insertion rate of 10 events/sec

    def set_queue(self, queue):
        self.process_queue = queue

    def start(self):
        self.thread_runner.start()

    def rec(self, filename=''):
        now = datetime.datetime.now()
        filename = '%s_%s.h5' % (filename, now.strftime('%Y-%m-%d_%H-%M-%S'))
        print('Starting the recording of %s' % filename)
        self.saver = Writer(filename)
        self.saver.datasets.createDataset('frames', shape=(self.width, self.height, 1), dtype=self.dtype)
        self.saver.datasets.createDataset('timestamps', shape=(1,), dtype=numpy.double)
        self.iframe = 0
        self.save.set()

    def stop(self):
        print('Wrote %d frames' % self.iframe)
        self.save.clear()
        if hasattr(self, 'saver'):
            self.saver.exit()

    def set_frame_rate(self, fps):
        self.namespace.fps = fps

    def dequeue(self, cam_queue):
        while not self.thread_end.is_set():
            if cam_queue.empty(): time.sleep(.05)
            else:
                item = cam_queue.get()
                if self.save.is_set():
                    self.iframe += 1
                    self.saver.append('timestamps', item['timestamps'])
                    self.saver.append('frames', item['frames'])
                self.process_queue.put(item)

    def capture(self,namespace):
        while not self.capture_end.is_set():
            item = dict()
            img = numpy.uint8(numpy.minimum(self.img*namespace.scale,numpy.ones(numpy.shape(self.img))*255))
            #img = numpy.uint8(numpy.multiply(self.img, numpy.random.random(numpy.shape(self.img)) * namespace.scale))
            item['frames'] = img[:, :, numpy.newaxis]
            item['timestamps'] = time.time()
            self.cam_queue.put(item)
            time.sleep(1/namespace.fps)

    def quit(self):
        print('Stopping...')
        self.capture_end.set()
        self.capture_runner.join()
        self.thread_end.set()
        self.thread_runner.join()
        if hasattr(self, 'saver'):
            self.saver.exit()


class oldCamera:
    def __init__(self):
        import matplotlib.image as mpimg
        img = mpimg.imread('image.png')
        self.img = img[:, :, 1]
        self.fps = 10
        self.exposure_time = 45000
        self.iframe = 0
        self.dtype = numpy.uint8
        sz = numpy.shape(img)
        self.width = sz[0]
        self.height = sz[1]
        self.setup()

    def setup(self):
        self.thread_end = threading.Event()
        self.save = threading.Event()
        self.thread_runner = threading.Thread(target=self.capture)  # max insertion rate of 10 events/sec

    def set_queue(self, queue):
        self.queue = queue

    def start(self):
        self.thread_runner.start()

    def rec(self, filename=''):
        now = datetime.datetime.now()
        filename = '%s_%s.h5' % (filename, now.strftime('%Y-%m-%d_%H-%M-%S'))
        print('Starting the recording of %s' % filename)
        self.saver = Writer(filename)
        self.saver.datasets.createDataset('frames', shape=(self.width, self.height, 1), dtype=self.dtype)
        self.saver.datasets.createDataset('timestamps', shape=(1,), dtype=numpy.double)
        self.saver.datasets.createDataset('indexes', shape=(1,))
        self.iframe = 0
        self.save.set()

    def stop(self):
        print('Wrote %d frames' % self.iframe)
        self.save.clear()
        self.saver.exit()

    def capture(self, fps):
        while not self.thread_end.is_set():
            dat = numpy.uint8(numpy.multiply(self.img, numpy.random.rand(self.width, self.height))*255)
            if self.save.is_set():
                self.iframe += 1
                self.saver.append('timestamps', time.time())
                self.saver.append('frames', dat[:, :, numpy.newaxis])
                self.saver.append('indexes', self.iframe)
            self.queue.put(dat)
            time.sleep(1/fps)

    def quit(self):
        self.thread_end.set()
        self.thread_runner.join()
        print(self.thread_runner.is_alive())
        self.saver.exit()


class AravisCam(Camera):
    def __init__(self):
        import gi
        gi.require_version('Aravis', '0.8')
        from gi.repository import Aravis

        self.fps = 10
        self.exposure_time = 45000

        Aravis.enable_interface("Fake")
        self.camera = Aravis.Camera.new(None)
        self.iframe = 0
        self.dtype = numpy.uint16
        self.camera.set_pixel_format(Aravis.PIXEL_FORMAT_MONO_16)
        self.camera.get_payload()
        self.camera.set_region(180, 0, 600, 600)
        xbin, ybin = self.camera.get_binning()
        if xbin == 1:
            self.camera.set_binning(1, 2)
            self.camera.set_binning(2, 2)
        self.camera.set_exposure_time_auto(False)
        self.camera.set_gain_auto(False)
        self.camera.set_gain(0)
        self.camera.set_exposure_time(self.exposure_time)
        self.camera.set_frame_rate(self.fps)
        payload = self.camera.get_payload()
        self.x, self.y, self.width, self.height = self.camera.get_region()
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

    def start(self):
        self.camera.start_acquisition()
        self.thread_runner.start()

    def capture(self):
        while not self.thread_end.is_set():
            image = self.stream.pop_buffer()
            if image:
                dat = numpy.ndarray(buffer=image.get_data(), dtype=self.dtype, shape=(600, 600, 1))
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


class FakeAravisCam(AravisCam):
    def __init__(self):
        import gi
        gi.require_version('Aravis', '0.8')
        from gi.repository import Aravis

        self.fps = 10
        self.exposure_time = 45000
        Aravis.enable_interface("Fake")
        self.camera = Aravis.Camera.new('Fake_1')
        self.iframe = 0
        self.dtype = numpy.uint8
        self.camera.set_pixel_format(Aravis.PIXEL_FORMAT_MONO_8)
        self.camera.get_payload()
        self.camera.set_region(180, 0, 600, 600)
        xbin, ybin = self.camera.get_binning()
        if xbin == 1:
            self.camera.set_binning(1, 2)
            self.camera.set_binning(2, 2)
        self.camera.set_frame_rate(self.fps)
        payload = self.camera.get_payload()
        [self.x, self.y, self.width, self.height] = self.camera.get_region()
        self.stream = self.camera.create_stream(None, None)
        for i in range(0, 100):
            self.stream.push_buffer(Aravis.Buffer.new_allocate(payload))
        self.setup()
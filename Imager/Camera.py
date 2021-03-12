import time, numpy, datetime, threading
import multiprocessing as mp
from ExpUtils.Writer import Writer
from queue import Queue


class Camera:
    def __init__(self, shape=(600, 600)):
        self.fps = 2
        self.exposure_time = 45000
        self.iframe = 0
        self.dtype = numpy.uint8
        self.width = shape[0]
        self.height = shape[1]
        mgr = mp.Manager()
        self.namespace = mgr.Namespace()
        self.namespace.fps = self.fps
        self.namespace.scale = 255
        self.setup()
        self.time = 0
        self.reported_framerate = 0

    def setup(self):
        self.cam_queue = Queue()
        self.capture_end = threading.Event()
        self.capture_runner = threading.Thread(target=self.capture, args=(self.cam_queue, self.stream))
        self.capture_runner.start()
        self.save = threading.Event()
        self.thread_end = threading.Event()
        self.thread_runner = threading.Thread(target=self.dequeue, args=(self.cam_queue,))  # max insertion rate of 10 events/sec

    def set_queue(self, queue):
        self.process_queue = queue

    def start(self):
        self.thread_runner.start()

    def rec(self, basename=''):
        now = datetime.datetime.now()
        filename = '%s_%s.h5' % (basename, now.strftime('%Y-%m-%d_%H-%M-%S'))
        print('Starting the recording of %s' % filename)
        self.saver = Writer(filename)
        self.saver.datasets.createDataset('frames', shape=(self.width, self.height, 1), dtype=self.dtype)
        self.saver.datasets.createDataset('timestamps', shape=(1,), dtype=numpy.double)
        self.iframe = 0
        self.save.set()
        return filename

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
                if self.process_queue.full():
                    self.process_queue.get()
                #print(cam_queue.qsize())
                self.reported_framerate = 1/(item['timestamps'] - self.time)
                self.time = item['timestamps']
                self.process_queue.put(numpy.uint8(item['frames']/65000*255))

    def capture(self, namespace):
        while not self.capture_end.is_set():
            item = dict()
            #img = numpy.uint8(numpy.minimum(self.img*namespace.scale,numpy.ones(numpy.shape(self.img))*255))
            #img = numpy.uint8(numpy.multiply(self.img, numpy.random.random(numpy.shape(self.img)) * namespace.scale))
            img = numpy.uint8(numpy.random.random((self.width, self.height)) * namespace.scale)
            item['frames'] = img[:, :, numpy.newaxis]
            item['timestamps'] = time.time()
            self.cam_queue.put(item)
            time.sleep(1/namespace.fps)

    def quit(self):
        print('Stopping...')
        self.capture_end.set()
        #self.capture_runner.join()
        self.thread_end.set()
        #self.thread_runner.join()
        if hasattr(self, 'saver'):
            self.saver.exit()


class AravisCam(Camera):
    def __init__(self, shape=(600, 600)):
        import gi
        gi.require_version('Aravis', '0.8')
        from gi.repository import Aravis

        self.Aravis = Aravis
        self.fps = 1
        self.time = 0
        self.exposure_time = 40000
        self.iframe = 0
        self.setup_camera()
        self.camera.get_payload()
        #self.camera.set_binning(2, 1)
        #self.camera.set_binning(1, 1)
        self.camera.set_region(180, 0, shape[0], shape[1])
        xbin, ybin = self.camera.get_binning()
        print(shape)
        print(xbin)
        self.reported_framerate = 0
        #self.camera.set_binning(1, 2)
        #self.camera.set_binning(1, 1)
        if xbin == 1:
            self.camera.set_binning(1, 2)
            self.camera.set_binning(2, 2)
        self.camera.set_frame_rate(self.fps)
        payload = self.camera.get_payload()
        self.x, self.y, self.width, self.height = self.camera.get_region()
        self.stream = self.camera.create_stream(None, None)
        for i in range(0, 100):
            self.stream.push_buffer(self.Aravis.Buffer.new_allocate(payload))
        self.setup()

    def setup_camera(self):
        self.camera = self.Aravis.Camera.new(None)
        self.dtype = numpy.uint16
        self.camera.set_pixel_format(self.Aravis.PIXEL_FORMAT_MONO_16)
        self.camera.set_exposure_time_auto(False)
        self.camera.set_gain_auto(False)
        self.camera.set_gain(0)
        self.camera.set_exposure_time(self.exposure_time)

    def set_frame_rate(self, fps):
        max_exposure = 1000000 / fps * 0.95
        if self.exposure_time > max_exposure:
            print('Exposure higher than fps allows..')
            self.set_exposure_time(max_exposure, direct=True)
            print('Setting exposure to %d' % max_exposure)
        print('Setting frame rate at %d' % fps)
        self.fps = fps
        self.camera.stop_acquisition()
        self.camera.set_frame_rate(fps)
        print('Frame rate is at %d' % self.camera.get_frame_rate())
        self.camera.start_acquisition()
        return self.camera.get_frame_rate()

    def set_exposure_time(self, exposure_prc, direct=False):
        max_exp = 1000000/self.fps * 0.95
        if direct:
            exposure_time = exposure_prc
        else:
            exposure_time = max_exp*exposure_prc
        print('Setting exposure to %d' % exposure_time)
        self.exposure_time = exposure_time  # in microseconds
        self.camera.stop_acquisition()
        self.camera.set_exposure_time(exposure_time)
        self.camera.start_acquisition()

    def set_gain(self, gain):
        print('Setting gain at %d' % gain)
        self.camera.set_gain(gain)

    def start(self):
        self.camera.start_acquisition()
        self.thread_runner.start()

    def capture(self, q, stream):
        while not self.capture_end.is_set():
            image = stream.pop_buffer()
            if image:
                item = dict()
                dat = numpy.ndarray(buffer=image.get_data(), dtype=self.dtype, shape=(self.width, self.height, 1))
                stream.push_buffer(image)
                item['frames'] = dat
                item['timestamps'] = time.time()
                q.put(item)

    def quit(self):
        self.camera.stop_acquisition()
        super().quit()


class FakeAravisCam(AravisCam):
    def setup_camera(self):
        self.Aravis.enable_interface("Fake")
        self.camera = self.Aravis.Camera.new('Fake_1')
        self.dtype = numpy.uint8
        self.camera.set_pixel_format(self.Aravis.PIXEL_FORMAT_MONO_8)

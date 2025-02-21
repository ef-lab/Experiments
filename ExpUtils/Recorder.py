import os, time, threading
from datetime import datetime
from subprocess import Popen
from ExpUtils.Communicator import Communicator
from utils.Timer import *
if os.getlogin() == 'ScanImage':
    import matlab.engine


class Recorder:
    def __init__(self, os_path=''):
        self._callbacks = dict(connected=lambda: None, started=lambda: None, stopped=lambda: None)
        self.key = dict()
        self.filename = ''
        self.base_folder = ''
        self.timer = Timer()
        self.running = False
        self.rec_info = dict()

    def start(self):
        pass

    def stop(self):
        pass

    def get_rec_info(self, rec_idx=0):
        return False

    def update_key(self, key):
        self.key.update(key)

    def update_rec_info(self, rec_info):
        self.rec_info.update(rec_info)

    def register_callback(self, key):
        print('updating ', key)
        self._callbacks.update(key) # update the dictionary with the callback functions
        print(self._callbacks)

    def get_state(self):
        return self.running

    def quit(self):
        pass


class Imager(Communicator, Recorder):
    def __init__(self, os_path=''):
        super().__init__()
        self.key = dict()
        self.filename = ''
        self.base_folder = ''
        self.timer = Timer()
        self.running = False
        self.rec_info = dict()
        self.register_callback(dict(rec_info=self.update_rec_info))  # function to update the recording information

        if os.name == 'nt':
            #Popen('python3.11 %sExperiments/Imager/Imager.py' % os_path, cwd=os_path + 'Experiments/', shell=True)
            Popen('python Y:/manolis/github/Experiments/Imager/Imager.py', cwd='Y:/manolis/github/Experiments', shell=True)
        else:
            Popen('sh Imager.sh', cwd='../', shell=True)
            #

    def start(self):
        self.send('start')

    def stop(self):
        self.send('stop')

    def get_rec_info(self, rec_idx):
        self.update_rec_info(dict(rec_idx=rec_idx))
        return self.rec_info


class ScanImage(Recorder):
    def __init__(self, connected=lambda x: None, message=lambda x: None):
        super().__init__()
        self._callbacks['connected'] = connected
        self._callbacks['message'] = message
        mat_engines = matlab.engine.find_matlab()
        if not mat_engines:
            self._callbacks['message']("No MATLAB detected: \n " +
                                       "1.Start MATLAB \n " +
                                       "2.Run matlab.engine.shareEngine \n " +
                                       "3.Run scanimage")
            return False

        self.matlab = matlab.engine.connect_matlab(mat_engines[0])
        self._callbacks['connected'](True)
        self.version = str(int(self.matlab.eval("hSI.VERSION_MAJOR", nargout=1))) + '.' + \
                       str(int(self.matlab.eval("hSI.VERSION_MINOR", nargout=1))) + '.' + \
                       str(int(self.matlab.eval("hSI.VERSION_UPDATE", nargout=1)))

        now = datetime.now()  # current date and time
        self.base_folder = 'F:/' + now.strftime("%Y-%m-%d") + '/'
        self.matlab.eval("mkdir('" + self.base_folder + "')")
        self.matlab.eval("hSI.hScan_ImagingScanner.logFilePath='" + self.base_folder + "'", nargout=0)

    def get_rec_info(self, rec_idx):
        self.matlab.eval("hSI.hScan_ImagingScanner.logFileCounter=" + str(rec_idx), nargout=0)
        file_base = str(self.key['animal_id']) + '_' + str(self.key['session'])
        self.filename = file_base + '_' + str(rec_idx).zfill(5)
        self.matlab.eval("hSI.hScan_ImagingScanner.logFileStem='" + file_base + "'", nargout=0)
        self.matlab.eval("hSI.hScan_ImagingScanner.logFilePath='" + self.base_folder + "'", nargout=0)
        return dict(source_path=self.base_folder,
                    filename=self.filename,
                    software='ScanImage',
                    version=self.version,
                    rec_idx=rec_idx)

    def start(self):
        self.timer.start()
        self._callbacks['report']('Waiting ScanImage to start recording')
        state = ''
        while not state == 'grab':
            state = self.matlab.eval("hSI.acqState", nargout=1)
            time.sleep(0.5)
            if self.timer.elapsed_time() > 115000:
                self._callbacks['report']('Session problem, Aborting')
                self._callbacks['abort']()
                break

        if state == 'grab':
            self._callbacks['recording'] = True
            self.running = True

    def stop(self):
        state = ''
        while state != 'idle':
            state = self.matlab.eval("hSI.acqState", nargout=1)
            print('waiting for recording to end!')
            time.sleep(.5)
        self._callbacks['stopped']()
        self.running = False

    def get_state(self):
        state = self.matlab.eval("hSI.acqState", nargout=1)
        if state == 'grab':
            self.running = True
        elif state == 'idle':
            self.running = False
        return self.running

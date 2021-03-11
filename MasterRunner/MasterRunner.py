from PyQt5 import uic, QtWidgets, QtCore
from PyQt5 import QtGui
import os, numpy, sys, threading, time, signal
from queue import Queue
from pathlib import Path
from subprocess import Popen
sys.path.append(str(Path.home()) + '/github/PyMouse')
sys.path.append(str(Path.home()) + '/github/Experiments')
from Experiments import *
from Logger import *
from ExpUtils.Communicator import *
from ExpUtils.Copier import *


class MasterRunner(QtWidgets.QWidget):
    def __init__(self, shape=(600, 600), dtype=numpy.int16):
        super(MasterRunner, self).__init__()
        self.queue = Queue()
        self.dtype = dtype
        self.shape = shape
        self.colormap = 'gray'
        self.animal_id = ''
        self.session = ''
        self.rec_info = ''
        self.targetpath = str(Path.home()) + '/target/'
        self.logger = Logger()
        self.copier = Copier()
        self.rec_started = False

        # load ui
        path = os.path.join(os.path.dirname(__file__), "form.ui")
        self.ui = uic.loadUi(path, self)
        self.ui.start_button.clicked.connect(self.start)
        self.ui.stop_button.clicked.connect(self.stop)
        self.ui.program_run.clicked.connect(self.run_program)
        self.conn = Communicator(connect_callback=self.ui.led_button.setDown)
        self.ui.animal_input.textChanged.connect(self.update_animal_id)
        self.conn.register_callback(dict(started=self.set_rec_info))
        self.conn.register_callback(dict(stopped=self.stop_rec))

    def set_rec_info(self, key):
        self.rec_started = True
        self.rec_info = key
        self.ui.file.setText(os.path.basename(self.rec_info['filename']))

    def update_animal_id(self):
        self.animal_id = self.ui.animal_input.text()
        self.logger.update_setup_info(dict(animal_id=self.animal_id))
        self.conn.send(dict(basename=self.animal_id))

    def run_program(self):
        Popen('sh Imager.sh', cwd="../", shell=True)

    def runTask(self, task):
        self.pymouse_proc = Popen('python3 ~/github/PyMouse/run.py %d' % task,
                                  cwd=str(Path.home())+'/github/PyMouse/', shell=True)

    def start(self):
        self.ui.start_button.setDown(True)
        self.ui.start_button.setText("Running")
        self.conn.send('start')
        while not self.rec_started and not self.ui.led_button.isDown:
            time.sleep(.1)
        print('starting task')
        self.runTask(self.ui.task.value())
        while self.logger.get_setup_info('status') != 'running':
            time.sleep(.1)
        print('started task')
        time.sleep(1)
        self.session = self.logger.get_setup_info('session')
        sess = str(self.session)
        self.ui.session_id.setText(sess)

    def stop_rec(self, *args):
        self.rec_started = False
        source_file = os.path.join(self.rec_info['source_path'], self.rec_info['filename'])
        if isinstance(self.rec_info, dict) and os.path.isfile(source_file) and self.ui.autocopy.checkState():
            target_file = os.path.join(self.targetpath, self.rec_info['filename'])
            print('Copying file %s' % target_file)
            self.copier.append(source_file, target_file)
            self.logger.log('Files', dict(self.rec_info, target_path=self.targetpath,
                                          animal_id=self.animal_id, session=self.session))

    def stop(self):
        self.logger.update_setup_info(dict(status='exit'))
        self.ui.start_button.setText("Stopping")
        while self.pymouse_proc.poll():
            time.sleep(.1)
        self.conn.send('stop')
        while self.rec_started and not self.ui.led_button.isDown:
            time.sleep(.1)
        self.ui.start_button.setDown(False)
        self.ui.start_button.setText("Start")

    def closeEvent(self, event):
        self.conn.quit()
        self.logger.update_setup_info(dict(status='exit'))
        self.logger.cleanup()
        self.copier.exit()
        event.accept()  # let the window close


if __name__ == "__main__":
    MainEventThread = QtWidgets.QApplication([])
    MainApp = MasterRunner()
    MainApp.show()
    MainEventThread.exec()


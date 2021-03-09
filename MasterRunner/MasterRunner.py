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


class MasterRunner(QtWidgets.QWidget):
    def __init__(self, shape=(600, 600), dtype=numpy.int16):
        super(MasterRunner, self).__init__()
        self.queue = Queue()
        self.dtype = dtype
        self.shape = shape
        self.colormap = 'gray'
        self.animal_id = ''
        self.session = ''
        self.logger = Logger()
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

    def set_rec_info(self, key):
        self.rec_started = True
        print(key)

    def update_animal_id(self):
        self.animal_id = self.ui.animal_input.text()
        self.logger.update_setup_info(dict(animal_id=self.animal_id))
        self.conn.send(dict(basename=self.animal_id))

    def run_program(self):
        Popen('sh Imager.sh', cwd="../", shell=True)

    def runTask(self, task):
        self.pymouse_proc = Popen('python3 ~/github/PyMouse/run.py %d' % task, cwd='/Users/eman/github/PyMouse/', shell=True)

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
        self.ui.session.setText(str(self.session))

    def stop(self):
        self.ui.start_button.setDown(False)
        self.rec_started = False
        self.ui.start_button.setText("Start")
        self.conn.send('stop')
        self.logger.update_setup_info(dict(status='exit'))

    def closeEvent(self, event):
        self.conn.quit()
        self.logger.update_setup_info(dict(status='exit'))
        self.logger.cleanup()
        event.accept()  # let the window close


if __name__ == "__main__":
    MainEventThread = QtWidgets.QApplication([])
    MainApp = MasterRunner()
    MainApp.show()
    MainEventThread.exec()


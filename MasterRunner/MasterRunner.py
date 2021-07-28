from PyQt5 import uic, QtWidgets, QtCore
import os, numpy, sys, threading, time, signal
from pathlib import Path
from subprocess import Popen
is_win = os.name == 'nt'
os_path = str(Path.home())
os_path += '/Documents/GitHub/' if is_win else '/github/'
sys.path.append(os_path + 'PyMouse')
sys.path.append(os_path + 'lab/python')
sys.path.append(os_path + 'Experiments')
from ExpUtils.Communicator import *
from ExpUtils.Copier import *


class Runner(QtWidgets.QWidget):
    def __init__(self, shape=(600, 600), dtype=numpy.int16):
        from core.Logger import Logger, dj
        import common

        self.logger = Logger()
        self.experiment = dj.create_virtual_module('experiment', 'lab_experiments', create_tables=True)
        self.common = common
        super(Runner, self).__init__()
        self.queue = Queue()
        self.dtype = dtype
        self.shape = shape
        self.colormap = 'gray'
        self.animal_id = ''
        self.session = ''
        self.rec_info = ''
        self.targetpath = self.common.Paths().getLocal('data')#'X:/' if is_win else '/mnt/lab/data/'

        self.copier = Copier()
        self.copier.run()
        self.rec_started = False
        self.exit = False

        # load ui
        path = os.path.join(os.path.dirname(__file__), "form.ui")
        self.ui = uic.loadUi(path, self)
        self.ui.start_button.clicked.connect(self.start)
        self.ui.stop_button.clicked.connect(self.stop)
        self.ui.abort_button.clicked.connect(self.abort)
        self.ui.insert_button.clicked.connect(self.insert_note)
        self.ui.software_run.clicked.connect(self.run_program)
        self.ui.user.addItems(self.common.User().fetch('user_name'))
        self.ui.anesthesia.addItems(self.experiment.AnesthesiaType().fetch('anesthesia'))
        self.ui.surgery_type.addItems(self.experiment.SurgeryType().fetch('surgery'))
        self.ui.anesthesia_type.addItems(self.experiment.AnesthesiaType().fetch('anesthesia'))
        self.ui.aim.addItems(self.experiment.Aim().fetch('rec_aim'))
        self.ui.software.addItems(self.experiment.Software().fetch('software'))
        self.recorder = Communicator(connect_callback=self.ui.connect_indicator.setDown)
        self.ui.animal_input.textChanged.connect(self.update_animal_id)
        self.recorder.register_callback(dict(started=self.set_rec_info))
        self.recorder.register_callback(dict(stopped=self.stop_rec))
        self.ui.surgery_button.clicked.connect(self.insert_surgery)
        self.ui.anesthesia_button.clicked.connect(self.insert_anesthesia)
        self.ui.anesthesia_time.setDateTime(QtCore.QDateTime.currentDateTime())
        self.ui.surgery_time.setDateTime(QtCore.QDateTime.currentDateTime())

    def set_rec_info(self, key):
        self.rec_started = True
        self.ui.recording_indicator.setDown(True)
        self.rec_info = key
        self.ui.file.setText(os.path.basename(self.rec_info['filename']))
        self.source_file = os.path.join(self.rec_info['source_path'], self.rec_info['filename'])

    def update_animal_id(self):
        self.animal_id = self.ui.animal_input.text()
        self.logger.update_setup_info(dict(animal_id=self.animal_id))
        self.recorder.send(dict(basename=self.animal_id))
        self.ui.session_id.setText(str(self.logger.get_last_session()))

    def run_program(self):
        if self.ui.software.currentText() == 'Imager':
            if is_win:
                Popen('python3.8 %sExperiments/Imager/Imager.py' % os_path, cwd=os_path+'Experiments/', shell=True)
            else:
                Popen('sh Imager.sh', cwd='../', shell=True)

    def run_task(self, task):
        self.pymouse_proc = Popen('python3 %sPyMouse/run.py %d' % (os_path, task),
                                  cwd=os_path+'PyMouse/', shell=True)

    def start(self):
        self.ui.running_indicator.setDown(True)
        self.ui.start_button.setDown(True)
        self.ui.start_button.setText("Running")
        self.recorder.send('start')
        self.session_key = dict(animal_id=self.animal_id, session=self.logger.get_last_session() + 1)
        while self.ui.connect_indicator.isDown() and not self.rec_started:
            time.sleep(.1)
        if self.ui.task_check.checkState():
            self.run_task(self.ui.task.value())
            while len(self.experiment.Session & self.session_key) == 0:
                time.sleep(.2)
            self.ui.stimulus_indicator.setDown(True)
        else:
            self.logger.log_session(dict(user=self.ui.user.currentText()))
        self.ui.session_id.setText(str(self.session_key['session']))
        if self.rec_started:
            self.target_file = os.path.join(self.targetpath + self.rec_info['software'], self.rec_info['filename'])
            recs = (self.experiment.Recording & self.session_key).fetch('rec_idx')
            rec_idx = 1 if not recs.size > 0 else max(recs) + 1
            tuple = {**self.session_key, **self.rec_info, 'target_path': self.targetpath + self.rec_info['software'],
                     'rec_idx': rec_idx, 'rec_aim': self.ui.aim.currentText()}
            self.logger.log('Recording', data=tuple)

        if self.ui.anesthesia.currentText() != 'none':
            self.logger.log('Session.Anesthetized', data={**self.session_key,
                                                          'anesthesia': self.ui.anesthesia.currentText()})

    def stop_rec(self, *args):
        self.rec_started = False
        self.ui.recording_indicator.setDown(False)
        if isinstance(self.rec_info, dict) and os.path.isfile(self.source_file) and self.ui.autocopy.checkState():
            print('Copying %s to %s' % (self.source_file, self.target_file))
            self.copier.append(self.source_file, self.target_file)

    def stop(self):
        self.logger.update_setup_info(dict(status='exit'))
        self.ui.start_button.setText("Stopping")
        if self.ui.task_check.checkState():
            while self.pymouse_proc.poll() is None:
                time.sleep(.1)
            self.ui.stimulus_indicator.setDown(False)
        self.recorder.send('stop')
        while self.rec_started and self.ui.connect_indicator.isDown:
            time.sleep(.1)
        self.ui.start_button.setDown(False)
        self.ui.start_button.setText("Start")
        self.ui.running_indicator.setDown(False)

    def abort(self):
        self.logger.log('Session.Excluded', {**self.session_key, 'reason':"aborted"})
        self.stop()

    def insert_note(self):
        txt = self.ui.note_field.toPlainText()
        if txt:
            self.logger.log('Session.Notes', {**self.session_key, 'note': txt})
            self.ui.note_field.setPlainText('')

    def insert_surgery(self):

        if self.ui.surgery_type.currentText() != 'none':
            dt = self.ui.surgery_time.dateTime()
            self.logger.log('Surgery', dict(animal_id=int(self.ui.animal_input.text()),
                                            surgery=self.ui.surgery_type.currentText(),
                                            user_name=self.ui.user.currentText(),
                                            timestamp=dt.toString("yyyy-MM-dd hh:mm:ss"),
                                            note=self.ui.surgery_notes.toPlainText()))
            self.ui.surgery_notes.setPlainText('')

    def insert_anesthesia(self):
        if self.ui.anesthesia_type.currentText() != 'none':
            dt = self.ui.anesthesia_time.dateTime()
            self.logger.log('Anesthesia', dict(animal_id=int(self.ui.animal_input.text()),
                                               anesthesia=self.ui.anesthesia_type.currentText(),
                                               user_name=self.ui.user.currentText(),
                                               timestamp=dt.toString("yyyy-MM-dd hh:mm:ss"),
                                               dose=self.ui.anesthesia_dose.text()))

    def copying_callback(self):
        if self.copier.copying.is_set():
            self.ui.copying_indicator.setDown(True)
        else:
            self.ui.copying_indicator.setDown(False)

    def closeEvent(self, event):
        self.recorder.quit()
        self.logger.update_setup_info(dict(status='exit'))
        self.logger.cleanup()
        self.copier.exit()
        self.exit = True
        event.accept()  # let the window close


if __name__ == "__main__":
    MainEventThread = QtWidgets.QApplication([])
    MainApp = Runner()
    MainApp.show()
    #MainEventThread.exec()
    while not MainApp.exit:
        MainEventThread.processEvents()
        MainApp.copying_callback()
        time.sleep(.01)
    MainEventThread.quit()




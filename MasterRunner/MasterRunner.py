from PyQt5 import uic, QtWidgets, QtCore
import os, numpy, sys, threading, time, signal, glob
from datetime import datetime, timedelta
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
from utils.Timer import *
from utils.helper_functions import *
from core.Logger import *
import common as common


class Runner(QtWidgets.QWidget):
    animal_id, session, setup_name, rec_info, rec_started, exit = 0, '', '', '', False, False
    colormap, common, state, dtype, shape = 'gray', common, 'starting', numpy.int16, (600, 600)

    def __init__(self):
        self.logger = Logger()
        self.logger.setup_schema({'recording': 'lab_recordings'})
        super(Runner, self).__init__()
        self.queue = Queue()
        self.targetpath = self.common.Paths().getLocal('data')
        self.copier = Copier()
        self.copier.run()
        self.timer = Timer()
        self.main_timer = Timer()

        path = os.path.join(os.path.dirname(__file__), "form.ui")
        self.ui = uic.loadUi(path, self)
        self.ui.start_button.clicked.connect(self.start)
        self.ui.stop_button.clicked.connect(self.stop)
        self.ui.abort_button.clicked.connect(self.abort)
        self.ui.insert_button.clicked.connect(self.insert_note)
        self.ui.software_run.clicked.connect(self.run_program)
        self.ui.user.addItems(self.common.User().fetch('user_name'))
        self.ui.anesthesia.addItems(self.logger.get(table='AnesthesiaType', fields=['anesthesia'], schema='recording'))
        self.ui.surgery_type.addItems(self.logger.get(table='SurgeryType', fields=['surgery'], schema='mice'))
        self.ui.anesthesia_type.addItems(self.logger.get(table='AnesthesiaType', fields=['anesthesia'], schema='recording'))
        self.ui.aim.addItems(self.logger.get(table='Aim', fields=['rec_aim'], schema='recording'))
        self.ui.software.addItems(self.logger.get(table='Software', fields=['software'], schema='recording'))
        self.recorder = Communicator(connect_callback=self.ui.connect_indicator.setDown)
        self.ui.animal_input.textChanged.connect(self.update_animal_id)
        self.recorder.register_callback(dict(started=self.set_rec_info))
        self.recorder.register_callback(dict(stopped=self.stop_rec))
        self.ui.surgery_button.clicked.connect(self.insert_surgery)
        self.ui.task.valueChanged.connect(self.update_task)
        self.ui.anesthesia_button.clicked.connect(self.insert_anesthesia)
        self.ui.anesthesia_time.setDateTime(QtCore.QDateTime.currentDateTime())
        self.ui.surgery_time.setDateTime(QtCore.QDateTime.currentDateTime())
        self.ui.setup.currentIndexChanged.connect(self.update_setup)
        self.ui.stim_refresh.clicked.connect(self.update_setups)
        self.update_setups()
        self.update_sessions()
        self.state = 'ready'
        self.report('Ready')

    def update_setups(self):
        self.ui.setup.currentIndexChanged.disconnect()
        self.ui.setup.clear()
        self.ui.setup.addItems(['local'] + list(self.logger.get(table='Control', fields=['setup'], schema='experiment',
                                               key={'status': 'ready'})))
        self.ui.setup.currentIndexChanged.connect(self.update_setup)

    def set_rec_info(self, key):
        recs = self.logger.get(table='Recording', fields=['rec_idx'], key=self.session_key, schema='recording')
        rec_idx = 1 if not recs.size > 0 else max(recs) + 1
        self.sess_tmst = self.logger.get(table='Session', fields=['session_tmst'], key=self.session_key)[0]
        target_path = os.path.join(self.targetpath, key['software'], str(self.session_key['animal_id']) +
                                   '_' + str(self.session_key['session']) + '_' + str(rec_idx) + '_' +
                                   datetime.strftime(self.sess_tmst, '%Y-%m-%d_%H-%M-%S'))
        self.rec_info = {**self.session_key, 'rec_idx': rec_idx, 'rec_aim': self.ui.aim.currentText(),
                         'target_path': target_path, 'source_path': [], **key}
        self.rec_thread = threading.Thread(target=self._set_rec_info)
        self.rec_thread.start()

    def _set_rec_info(self):
        if self.rec_info['software'] == 'Miniscope':
            date = datetime.strftime(self.sess_tmst, '%Y_%m_%d')
            self.rec_info['version'] = '1.10'
            self.timer.start()
            while not self.rec_info['source_path']:  # waiting for recording to start
                self.rec_info['source_path'] = [folder for folder in glob.glob('D:/Miniscope/' + date + '/*')
                 if datetime.strptime(date + ' ' + os.path.split(folder)[1], '%Y_%m_%d %H_%M_%S') >= self.sess_tmst]
                if not self.rec_info['source_path']: time.sleep(.5); self.report('Waiting for recording to start')
                if self.timer.elapsed_time() > 5000: self.report('Recording problem, Aborting'); self.stop(); return
        elif self.rec_info['software'] == 'OpenEphys':
            date = datetime.strftime(self.sess_tmst, '%Y-%m-%d')
            self.rec_info['version'] = '0.5.4'
            self.rec_info['source_path'] = [folder for folder in glob.glob('D:/OpenEphys/' + date + '*')
             if datetime.strptime(os.path.split(folder)[1], '%Y-%m-%d_%H-%M-%S') >= self.sess_tmst-timedelta(seconds=10)]
        if self.rec_info['source_path']:
            self.rec_info['source_path'] = self.rec_info['source_path'][0]
            self.logger.log('Recording', data=self.rec_info, schema='recording')
            self.ui.file.setText(os.path.basename(self.rec_info['filename']))
            self.rec_started = True
            self.ui.recording_indicator.setDown(True)

    def report(self, message):
        print(message)

    def update_animal_id(self):
        self.animal_id = int(self.ui.animal_input.text())
        self.logger.update_setup_info(dict(animal_id=self.animal_id), dict(setup=self.logger.setup))
        self.recorder.send(dict(basename=self.animal_id))
        self.ui.session_id.setText(str(self.logger.get_last_session()))
        self.update_sessions()

    def update_setup(self):
        self.setup_name = self.ui.setup.currentText()
        if self.setup_name != 'local':
            self.logger.setup = self.setup_name

    def run_program(self):
        if self.ui.software.currentText() == 'Imager':
            if is_win:
                Popen('python3.8 %sExperiments/Imager/Imager.py' % os_path, cwd=os_path+'Experiments/', shell=True)
            else:
                Popen('sh Imager.sh', cwd='../', shell=True)

    def run_task(self, task):
        if self.setup_name == 'local':
            self.pymouse_proc = Popen('python3 %sPyMouse/run.py %d' % (os_path, task),
                                      cwd=os_path+'PyMouse/', shell=True)
        else:
            self.logger.update_setup_info(dict(task_idx=task, status='running', animal_id=self.animal_id),
                                          dict(setup=self.setup_name))

    def start(self):
        self.ui.error_indicator.setDown(False)
        if self.state == 'ready':
            self.start_thread = threading.Thread(target=self._start)
            self.start_thread.start()

    def _start(self):
        self.state = 'starting'
        self.update_setup()
        self.update_animal_id()
        self.ui.start_button.setDown(True)
        self.ui.start_button.setText("Starting...")
        self.recorder.send('start')
        self.session_key = dict(animal_id=self.animal_id, session=self.logger.get_last_session() + 1)
        self.timer.start()
        self.report('Waiting for recording to start')
        while self.ui.connect_indicator.isDown() and not self.rec_started:
            time.sleep(.1)
            if self.timer.elapsed_time() > 10000:
                self.report('Recording problem, Aborting')
                self.ui.error_indicator.setDown(True); self.abort(); return
        if self.ui.task_check.checkState():
            self.run_task(self.ui.task.value())
            self.timer.start()
            self.report('Waiting session to start')
            while len(self.logger.get(table='Session', fields=['session'], key=self.session_key)) == 0:
                time.sleep(.4)
                if self.timer.elapsed_time() > 30000:
                    self.report('Session problem, Aborting')
                    self.ui.error_indicator.setDown(True); self.abort(); return
            self.ui.stimulus_indicator.setDown(True)
            table = rgetattr(self.logger._schemata['experiment'], 'Session')
            (table & self.session_key)._update('user_name', self.ui.user.currentText())
        else:
            self.logger.log_session(dict(user=self.ui.user.currentText()))
        self.ui.running_indicator.setDown(True)
        self.ui.session_id.setText(str(self.session_key['session']))
        # set recording info
        if self.ui.software.currentText() in ['Miniscope', 'OpenEphys']:
            self.set_rec_info(dict(started=True, filename='', software=self.ui.software.currentText()))
        if self.ui.anesthesia.currentText() != 'none':
            self.logger.log('Recording.Anesthetized', schema='recording',
                            data={**self.session_key, 'anesthesia': self.ui.anesthesia.currentText()})
        self.ui.start_button.setText("Running")
        self.report('Experiment started')
        self.state = 'running'
        self.update_sessions()

    def stop_rec(self, *args):
        self.ui.recording_indicator.setDown(False)
        if self.rec_started and self.ui.autocopy.checkState():
            source_file = os.path.join(self.rec_info['source_path'], self.rec_info['filename'])
            if os.path.isfile(source_file) or os.path.isdir(source_file):
                target_file = os.path.join(self.rec_info['target_path'], self.rec_info['filename'])
                self.report('Copying %s to %s' % (source_file, target_file))
                self.copier.append(source_file, target_file)
        self.rec_started = False

    def stop(self):
        if self.state in {'running', 'starting'}:
            self.stop_thread = threading.Thread(target=self._stop)
            self.stop_thread.start()

    def _stop(self):
        self.state = 'stopping'
        self.report('Stopping')
        self.ui.stop_button.setText("Stopping")
        self.logger.update_setup_info(dict(status='stop'), dict(setup=self.logger.setup))
        if self.ui.task_check.checkState():
            if self.setup_name == 'local':
                while self.pymouse_proc.poll() is None: time.sleep(.1)
            else:
                while self.logger.get(table='Control', fields=['status'], schema='experiment',
                                      key={'setup': self.logger.setup})[0] not in {'exit', 'ready'}:
                    time.sleep(.1)
            self.ui.stimulus_indicator.setDown(False)
        if self.ui.software.currentText() in ['Miniscope', 'OpenEphys']:
            self.stop_rec()
        else:
            self.recorder.send('stop')
            while self.rec_started and self.ui.connect_indicator.isDown:
                time.sleep(.1)
        self.ui.start_button.setDown(False)
        self.ui.start_button.setText("Start")
        self.ui.stop_button.setText("Stop")
        self.ui.running_indicator.setDown(False)
        self.report('Ready')
        self.state = 'ready'
        self.update_sessions()

    def abort(self):
        if self.state in {'running', 'starting'}:
            if self.setup_name == 'local': Popen.kill(self.pymouse_proc)
            self.logger.log('Session.Excluded', {**self.session_key, 'reason': "aborted"})
            self.ui.abort_button.setText("Aborting")
            self.stop()
            self.ui.abort_button.setText("Abort")

    def insert_note(self):
        txt = self.ui.note_field.toPlainText()
        if txt:
            self.logger.log('Session.Notes', {**self.session_key, 'note': txt})
            self.ui.note_field.setPlainText('')
            self.report('Note inserted')

    def insert_surgery(self):
        if self.ui.surgery_type.currentText() != 'none':
            dt = self.ui.surgery_time.dateTime()
            self.logger.log('Surgery', data=dict(animal_id=int(self.ui.animal_input.text()),
                                                 surgery=self.ui.surgery_type.currentText(),
                                                 user_name=self.ui.user.currentText(),
                                                 timestamp=dt.toString("yyyy-MM-dd hh:mm:ss"),
                                                 note=self.ui.surgery_notes.toPlainText()), schema='mice')
            self.ui.surgery_notes.setPlainText('')
            self.report('Surgery inserted')

    def insert_anesthesia(self):
        if self.ui.anesthesia_type.currentText() != 'none':
            dt = self.ui.anesthesia_time.dateTime()
            self.logger.log('Anesthesia', data=dict(animal_id=int(self.ui.animal_input.text()),
                                                    anesthesia=self.ui.anesthesia_type.currentText(),
                                                    user_name=self.ui.user.currentText(),
                                                    timestamp=dt.toString("yyyy-MM-dd hh:mm:ss"),
                                                    dose=self.ui.anesthesia_dose.text()), schema='recording')
            self.report('Anesthesia inserted')

    def update_task(self):
        if self.ui.task.value():
            protocol = self.logger.get(table='Task', fields=['protocol'],
                                       schema='experiment', key={'task_idx': self.ui.task.value()})
            if protocol:
                path, filename = os.path.split(protocol[0])
                self.ui.task_file.setText(str(filename))

    def update_sessions(self):
        info = ['']*5
        info[0], info[1], info[2], info[3], info[4] = \
            self.logger.get(table='Session', fields=['session', 'user_name', 'setup','experiment_type', 'session_tmst'],
                            schema='experiment', key={'animal_id': self.animal_id})
        # Set the table values
        self.ui.Sessions.clearContents()
        for row in range(len(info[0])):
            for col in range(len(info)):
                self.ui.Sessions.setItem(row, col, QtWidgets.QTableWidgetItem(str(info[col][len(info[0]) - row - 1])))

    def copying_callback(self):
        self.ui.copying_indicator.setDown(self.copier.copying.is_set())

    def main(self):
        if self.main_timer.elapsed_time() > 500:
            self.copying_callback()
            self.main_timer.start()
            if self.state == 'running' and self.ui.task_check.checkState():
                self.ui.trial_number.setText(str(self.logger.setup_info['trials']))
                if self.logger.setup_info['status'] != 'running' and self.logger.setup_info['state'] == 'ERROR!':
                    self.report('Error!')
                    self.ui.error_indicator.setDown(True)
                    self.abort()
                elif self.logger.setup_info['status'] != 'running':
                    self.report('experiment done!')
                    self.stop()

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
    while not MainApp.exit:
        MainEventThread.processEvents()
        MainApp.main()
        time.sleep(.01)
    MainEventThread.quit()




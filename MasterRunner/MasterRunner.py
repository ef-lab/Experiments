from PyQt5 import uic, QtWidgets, QtCore
import os, numpy, sys, glob, json, re
from datetime import datetime, timedelta
from pathlib import Path

os_path = str(Path.home())
os_path += '/GitHub/' if os.name == 'nt' else '/github/'
sys.path.append(os_path + 'EthoPy')
#sys.path.append('Y:\manolis\github\EthoPy')
sys.path.append(os_path + 'lab/python')
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(sys.argv[0]))))

from ExpUtils.Recorder import *
from ExpUtils.Copier import *
from ExpUtils.Timer import *
from utils.helper_functions import *
from core.Logger import *
import common as common


class Runner(QtWidgets.QWidget):
    animal_id, session, setup_name, rec_started, exit, rec_info = 0, '', '', False, False, {'software':"None"}
    colormap, common, state, dtype, shape, session_key = 'gray', common, 'starting', numpy.int16, (600, 600), dict()

    def __init__(self):
        self.logger = Logger()
        self.logger.setup_schema({'recording': 'lab_recordings'})
        super(Runner, self).__init__()
        self.queue = Queue()
        self.copier = Copier()
        self.targetpath = self.common.Paths().getLocal('data')
        self.copier.run()
        self.timer = Timer()
        self.main_timer = Timer()
        self.recorder = Recorder()  # init default recorder, this gets overridden once a recorder has been connected
        path = os.path.join(os.path.dirname(__file__), "form.ui")
        self.ui = uic.loadUi(path, self)
        self.ui.start_button.clicked.connect(self.start)
        self.ui.stop_button.clicked.connect(self.stop)
        self.ui.abort_button.clicked.connect(self.abort)
        self.ui.insert_button.clicked.connect(self.insert_note)
        self.ui.software_run.clicked.connect(self.start_recorder)  # callback for recorder start
        self.ui.user.addItems(self.common.User().fetch('user_name'))
        self.ui.anesthesia.addItems(self.logger.get(table='AnesthesiaType', fields=['anesthesia'], schema='recording'))
        self.ui.surgery_type.addItems(self.logger.get(table='SurgeryType', fields=['surgery'], schema='mice'))
        self.ui.anesthesia_type.addItems(self.logger.get(table='AnesthesiaType', fields=['anesthesia'], schema='recording'))
        self.ui.aim.addItems(self.logger.get(table='Aim', fields=['rec_aim'], schema='recording'))
        self.ui.software.addItems(self.logger.get(table='Software', fields=['software'], schema='recording'))
        self.ui.animal_input.textChanged.connect(self.update_animal_id)
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

        # read the configuration from the local_conf.json
        try:
            with open("local_conf.json", "r", encoding="utf-8") as f:
                config = json.load(f)
        except FileNotFoundError:
            logging.error("Configuration file 'local_conf.json' not found.")
            raise
        except json.JSONDecodeError:
            logging.error("Configuration file 'local_conf.json' is not a valid JSON.")
            raise

        if 'aim' in config: self.ui.aim.setCurrentText(config['aim'])
        if 'software' in config: self.ui.software.setCurrentText(config['software'])
        if 'setup' in config: self.ui.setup.setCurrentText(config['setup'])
        if 'target_path' in config: self.targetpath = config['target_path']
        self.ui.user.setCurrentText('bot')

    def update_setups(self):
        self.ui.setup.currentIndexChanged.disconnect()
        self.ui.setup.clear()
        self.ui.setup.addItems(['local'] + list(self.logger.get(table='Control', fields=['setup'], schema='experiment',
                                               key={'status': 'ready'})))
        self.ui.setup.currentIndexChanged.connect(self.update_setup)

    def report(self, message):
        print(message)

    def update_animal_id(self):
        try:
            self.animal_id = int(self.ui.animal_input.text())
        except ValueError:
            print("Animal ID does not contain a number!")
            return

        self.logger.update_setup_info(dict(animal_id=self.animal_id), dict(setup=self.logger.setup))
        last_session = self.logger._get_last_session()
        self.ui.session_id.setText(str(last_session))
        self.recorder.update_key(dict(animal_id=self.animal_id, session=last_session+1))
        self.update_sessions()

    def update_setup(self):
        self.setup_name = self.ui.setup.currentText()
        if self.setup_name != 'local':
            self.logger.setup = self.setup_name

    def start_recorder(self):
        callbacks = dict(connected=self.ui.connect_indicator.setDown,
                         started=self.set_rec_info,
                         stopped=self.stop_rec,
                         report=self.report,
                         abort=self.abort,
                         recording=self.set_rec_status)

        if self.ui.software.currentText() == 'ScanImage':
            self.recorder = ScanImage(callbacks=callbacks)
            self.recorder.register_callback(dict(message=self._message))
        elif self.ui.software.currentText() == 'Imager':
            self.recorder = Imager(os_path=os_path)
            self.recorder.register_callback(callbacks)

    def set_rec_status(self, status):
        self.rec_started = status
        self.ui.recording_indicator.setDown(status)

    def set_rec_info(self, key):
        self.rec_info = {**self.rec_info, **key, 'rec_aim': self.ui.aim.currentText()}

    def run_task(self, task):
        if self.setup_name == 'local':
            self.ethopy_proc = Popen('python3 %sEthoPy/run.py %d' % (os_path, task),
                                      cwd=os_path+'EthoPy/', shell=True)
        else:
            self.logger.update_setup_info(dict(task_idx=task, status='running', animal_id=self.animal_id),
                                          dict(setup=self.setup_name))

    def start(self):
        if self.state != 'ready':
            self.report('Already started!')
            return
        self.ui.error_indicator.setDown(False)
        self.update_setup()
        self.update_animal_id()
        self.session_key = dict(animal_id=self.animal_id, session=self.logger._get_last_session() + 1)
        if self.ui.software.currentText() == 'OpenEphys':
            self._message('Start OpenEphys Recording!')
            self.recorder = OpenEphys()
            time.sleep(1)
        self.start_thread = threading.Thread(target=self._start)
        self.start_thread.start()

    def _start(self):
        #try:
        self.state = 'starting'
        self.ui.start_button.setDown(True)
        self.ui.start_button.setText("Starting...")

        if self.ui.task_check.checkState():
            self.run_task(self.ui.task.value())
            self.timer.start()
            self.report('Waiting session to start')
            while len(self.logger.get(table='Session', fields=['session'], key=self.session_key)) == 0:
                time.sleep(.4)
                if self.timer.elapsed_time() > 10000:
                    self.report('Session problem, Aborting')
                    self.ui.error_indicator.setDown(True); self.abort(); return
            self.ui.stimulus_indicator.setDown(True)
            self.logger.thread_lock.acquire()
            table = rgetattr(self.logger._schemata['experiment'], 'Session')
            self.session_key['user_name'] = self.ui.user.currentText()
            table.update1(self.session_key)
            self.logger.thread_lock.release()
        else:
            self.logger.log_session(dict(user=self.ui.user.currentText()))
        time.sleep(2)

        self.log_rec()

        # start the experiment
        #if self.ui.software.currentText() in ['ScanImage', 'Thorcam']:
        #    self._message('Start Recorder!')

        self.recorder.start()
        self.timer.start()
        while self.ui.connect_indicator.isDown() and not self.rec_started:
            time.sleep(.1)
            if self.timer.elapsed_time() > 10000:
                self.report('Recording problem, Aborting')
                self.ui.error_indicator.setDown(True); self.abort(); return

        self.logger.update_setup_info(dict(status='operational', animal_id=self.animal_id),
                                      dict(setup=self.logger.setup))

        self.ui.running_indicator.setDown(True)
        self.ui.session_id.setText(str(self.session_key['session']))
        # set recording info
        if self.ui.software.currentText() in ['Miniscope', 'OpenEphys']:
            self.set_rec_info(dict(started=True, filename='', software=self.ui.software.currentText()))
        elif self.ui.software.currentText() in ['Imager', 'ScanImage']:
            rec_info = self.recorder.get_rec_info(rec_idx=self.rec_info['rec_idx'])
            if rec_info:
                self.set_rec_info(rec_info)
        elif not self.rec_info['filename']:
            self.report('Filename not set! Check recorder status... ')
            self.ui.error_indicator.setDown(True)
            self.abort()

        if self.ui.anesthesia.currentText() != 'none':
            self.logger.log('Recording.Anesthetized', schema='recording',
                            data={**self.session_key,'rec_idx':self.rec_info['rec_idx'],
                                  'anesthesia': self.ui.anesthesia.currentText()})
        self.ui.start_button.setText("Running")
        self.report('Experiment started')
        self.state = 'running'
        self.update_sessions()
        #except:
        #    print('start error!')
        #    self.ui.error_indicator.setDown(True)
        #    self.abort()

    def log_rec(self):

        if self.ui.software.currentText() != 'None':  # check if recorder is selected
            # SET REC IDX
            recs = self.logger.get(table='Recording', fields=['rec_idx'], key=self.session_key, schema='recording')
            rec_idx = 1 if not recs.size > 0 else max(recs) + 1

            # get session tmst
            self.sess_tmst = self.logger.get(table='Session', fields=['session_tmst'], key=self.session_key)[0]

            # set target path
            target_path = os.path.join(self.targetpath, self.rec_info['software'], str(self.session_key['animal_id']) +
                                       '_' + str(self.session_key['session']) + '_' + str(self.rec_info['rec_idx']) + '_' +
                                       datetime.strftime(self.sess_tmst, '%Y-%m-%d_%H-%M-%S'))

            # define rec_info
            self.rec_info = {'source_path': '', **self.rec_info, **self.session_key,
                             'target_path': target_path}

            self.recorder.sess_tmst = self.sess_tmst
            self.recorder.set_basename(str(self.session_key['animal_id']) + '_' + str(self.session_key['session']))
            self.set_rec_info(dict(**self.recorder.get_rec_info(rec_idx), **self.session_key))
            self.logger.log('Recording', data=self.rec_info, schema='recording', replace=True, priority=1)

            self.rec_thread = threading.Thread(target=self._log_rec_())
            self.rec_thread.start()

    def _log_rec_(self):
        #try:
        if self.rec_info['software'] == 'Miniscope':
            date = datetime.strftime(self.sess_tmst, '%Y_%m_%d')
            self.rec_info['version'] = '1.10'
            self.timer.start()
            while not self.rec_info['source_path']:  # waiting for recording to start
                folders = [folder for folder in glob.glob('D:/Miniscope/' + date + '/*')
                if datetime.strptime(date + ' ' + os.path.split(folder)[1], '%Y_%m_%d %H_%M_%S') >= self.sess_tmst]
                self.rec_info['source_path'] = folders[-1]
                if not self.rec_info['source_path']: time.sleep(.5); self.report('Waiting for recording to start')
                if self.timer.elapsed_time() > 5000: self.report('Recording problem, Aborting'); self.abort(); return
        elif self.rec_info['software'] == 'OpenEphys':
            date = datetime.strftime(self.sess_tmst, '%Y-%m-%d')
            self.rec_info['version'] = '0.5.4'
            #self.rec_info['source_path'] = [folder for folder in glob.glob('D:/OpenEphys/' + date + '*')
            # if datetime.strptime(os.path.split(folder)[1], '%Y-%m-%d_%H-%M-%S') >= self.sess_tmst-timedelta(seconds=20)]
            folders = [folder for folder in glob.glob('D:/OpenEphys/' + date + '*')
            if datetime.strptime(os.path.split(folder)[1], '%Y-%m-%d_%H-%M-%S') >= self.sess_tmst-timedelta(seconds=20)]
            self.rec_info['source_path'] = folders[-1]

        if self.rec_info['source_path']:
            self.logger.log('Recording', data=self.rec_info, schema='recording', replace=True, priority=1)
            self.ui.file.setText(os.path.basename(self.rec_info['source_path']+self.rec_info['filename']))
            self.set_rec_status(True)
        else:
            self.report('Recording source path not found!')

        #except:
        #    print('rec error!')
        #    self.ui.error_indicator.setDown(True); self.abort()

    def stop_rec(self, *args):
        if self.rec_started and self.ui.autocopy.checkState():
            source_file = os.path.join(self.rec_info['source_path'], self.rec_info['filename']).replace("\\", "/")
            if os.path.isfile(source_file) or os.path.isdir(source_file):
                self.copy_file(source_file, self.rec_info['filename'])
            else:
                pattern = re.compile(self.rec_info['filename'] + ".*")
                for filepath in os.listdir(self.rec_info['source_path']):
                    source_file = os.path.join(self.rec_info['source_path'], filepath).replace("\\", "/")
                    if pattern.match(filepath):
                        self.copy_file(source_file, filepath)
        self.set_rec_status(False)

    def copy_file(self,source_file, target_file):
        target_file = os.path.join(self.rec_info['target_path'], target_file).replace("\\", "/")
        self.report('Copying %s to %s' % (source_file, target_file))
        self.copier.append(source_file, target_file)

    def stop(self):
        if self.state in {'running', 'starting'}:
            if self.logger.get_setup_info('status') == 'running':
                self.logger.update_setup_info(dict(status='stop', animal_id=self.animal_id),
                                              dict(setup=self.setup_name))
                while self.logger.get_setup_info('status') not in {'exit', 'ready'}:
                    time.sleep(.5)
            self.ui.stimulus_indicator.setDown(False)
            if self.ui.software.currentText() == 'OpenEphys':
                self.copier.pause.set()
                self._message('Stop OpenEphys Recording!')
                self.copier.pause.clear()
            else:
                self.recorder.stop()
                while self.rec_started and self.ui.connect_indicator.isDown:
                    time.sleep(.1)
            self.stop_thread = threading.Thread(target=self._stop)
            self.stop_thread.start()

    def _stop(self):
        self.state = 'stopping'
        self.report('Stopping')
        self.ui.stop_button.setText("Stopping")
        if self.ui.task_check.checkState():
            if self.setup_name == 'local':
                while self.ethopy_proc.poll() is None: time.sleep(.1)
            else:
                while self.logger.get(table='Control', fields=['status'], schema='experiment',
                                      key={'setup': self.logger.setup})[0] not in {'exit', 'ready'}:
                    time.sleep(.1)

        if self.ui.software.currentText() in ['Miniscope', 'OpenEphys']:
            self.stop_rec()
        else:
            self.recorder.stop()

        self.ui.start_button.setDown(False)
        self.ui.start_button.setText("Start")
        self.ui.stop_button.setText("Stop")
        self.ui.running_indicator.setDown(False)
        self.report('Ready')
        self.state = 'ready'
        self.update_sessions()

    def abort(self):
        if self.state in {'running', 'starting'}:
            if self.setup_name == 'local': Popen.kill(self.ethopy_proc)
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
            protocol = self.logger.get(table='Task', fields=['task'],
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
            if self.state in ['running', 'operational'] and self.ui.task_check.checkState():
                status = self.logger.get_setup_info('status')
                self.ui.trial_number.setText(str(self.logger.setup_info['trials']))
                if status not in ['running', 'operational'] and self.logger.setup_info['state'] == 'ERROR!':
                    self.report('Error!')
                    self.ui.error_indicator.setDown(True)
                    self.abort()
                elif status not in ['running', 'operational']:
                    self.report('experiment done!')
                    self.stop()
            elif self.state in ['running', 'operational'] and not self.ui.task_check.checkState() and not self.recorder.get_state():
                self.report('experiment done!')
                self.stop()

    def closeEvent(self, event):
        self.recorder.quit()
        if self.setup_name == 'local':
            self.logger.update_setup_info(dict(status='exit'))
        self.logger.cleanup()
        self.copier.exit()
        self.exit = True
        event.accept()  # let the window close

    def _message(self, message):
        msgBox = QtWidgets.QMessageBox()
        msgBox.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msgBox.setText(message)
        msgBox.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        msgBox.exec()


if __name__ == "__main__":
    MainEventThread = QtWidgets.QApplication([])
    MainApp = Runner()
    MainApp.show()
    while not MainApp.exit:
        MainEventThread.processEvents()
        MainApp.main()
        time.sleep(.05)
    MainEventThread.quit()




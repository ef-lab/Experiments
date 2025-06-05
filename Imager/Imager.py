from PyQt5 import uic, QtWidgets, QtCore
from PyQt5.QtGui import QPixmap, QImage
from PyQt5 import QtGui
import os, numpy, sys
from pathlib import Path
os_path = '/Documents/GitHub/' if os.name == 'nt' else '/github/'
sys.path.append(str(Path.home()) + os_path + 'Experiments')
from Camera import *
from ExpUtils.Communicator import *


class Imager(QtWidgets.QWidget):
    version = '0.1'

    def __init__(self):
        super(Imager, self).__init__()
        self.queue = Queue(maxsize=2)
        self.basename = ''
        self.basepath = ''
        self.filename = ''
        self.rec_info = dict()
        # load ui
        path = os.path.join(os.path.dirname(__file__), "form.ui")
        self.ui = uic.loadUi(path, self)
        self.setColorTable()
        self.fps = self.ui.fps_input.value()
        self.shape = (self.ui.X_sz.value(), self.ui.Y_sz.value())
        #self.shape=(640, 480)
        self.cam = self.setCamera()                    # handle inputs
        self.ui.stop_button.clicked.connect(self.stop_rec)
        self.ui.rec_button.clicked.connect(self.start_rec)
        self.ui.fps_input.valueChanged.connect(self.updateFPS)
        self.ui.exposure_input.valueChanged.connect(self.updateExposure)
        self.ui.gain_input.valueChanged.connect(self.updateGain)
        self.ui.colormaps.currentIndexChanged.connect(self.setColorTable)

        # set view window
        self.scene = QtWidgets.QGraphicsScene()
        self.ui.graphicsView.setScene(self.scene)
        self.ui.graphicsView.show()
        self.ui.graphicsView.rotate(0)
        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.updateplot)
        timer.start(100)
        self.updateplot()
        self.conn = Communicator(role='client')
        self.conn.register_callback(dict(start=self.start_rec))
        self.conn.register_callback(dict(stop=self.stop_rec))
        self.conn.register_callback(dict(basename=self.set_basename))
        self.conn.register_callback(dict(basepath=self.set_basepath))
        self.conn.send(dict(connected=True))

    def set_basename(self, basename):
        self.basename = basename

    def set_basepath(self, basepath):
        self.basepath = basepath

    def start_rec(self, *args):
        self.ui.rec_button.setDown(True)
        self.ui.stop_button.setDown(False)
        self.filename = self.cam.rec(basename=self.basepath + str(self.basename))
        self.rec_info = dict(source_path=os.path.dirname(self.filename),
                             filename=os.path.basename(self.filename),
                             software='Imager',
                             version=self.version)
        self.conn.send(dict(started=self.rec_info,
                            recording=True,
                            rec_info=self.rec_info))

    def stop_rec(self, *args):
        self.ui.rec_button.setDown(False)
        self.cam.stop()
        self.conn.send(dict(stopped=True))

    def updateFPS(self):
        if not self.ui.rec_button.isDown():
            fps = self.cam.set_frame_rate(self.ui.fps_input.value())
            self.fps = fps
            self.ui.fps_input.setValue(fps)

    def updateExposure(self):
        if not self.ui.rec_button.isDown():
            self.ui.exposure_input.setValue(self.cam.set_exposure_time(self.ui.exposure_input.value()))

    def updateGain(self):
        if not self.ui.rec_button.isDown():
            self.cam.set_gain(self.ui.gain_input.value())

    def setCamera(self):
        #cam = SpinCam(shape=self.shape)
        #cam = WebCam(shape=self.shape)
        cam = ThorCam(shape=self.shape)
        cam.fps = self.fps
        cam.set_queue(self.queue)
        cam.start()
        return cam

    def updateplot(self):
        if not self.queue.empty():
            item = self.queue.get()
            image = QImage(item, self.cam.width, self.cam.height, QImage.Format_Indexed8)
            image.setColorTable(self.color_table)
            self.scene.clear()
            self.scene.addPixmap(QPixmap(image))
            self.ui.graphicsView.fitInView(self.scene.sceneRect(), QtCore.Qt.KeepAspectRatio)
            self.ui.graphicsView.update()
            self.ui.frames.display(self.cam.iframe)
            self.ui.fps_indicator.display(int(self.cam.reported_framerate))

    def closeEvent(self, event):
        self.cam.stop()
        self.cam.quit()
        self.conn.quit()
        print('Exiting...')
        event.accept()  # let the window close

    def setColorTable(self):
        colormap = str(self.ui.colormaps.currentText())
        if colormap == 'jet':
            t = lambda i, v: int(min(max(-4.0 * abs(i - 255 * v / 4) + 255 * 3 / 2, 0), 255))
            self.color_table = [QtGui.qRgb(t(i, 3), t(i, 2), t(i, 1)) for i in range(256)]
        elif colormap == 'gray':
            self.color_table = [QtGui.qRgb(i, i, i) for i in range(256)]


if __name__ == "__main__":
    MainEventThread = QtWidgets.QApplication([])
    MainApp = Imager()
    MainApp.show()
    MainEventThread.exec()


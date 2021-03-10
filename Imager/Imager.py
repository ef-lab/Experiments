from PyQt5 import uic, QtWidgets, QtCore
from PyQt5.QtGui import QPixmap, QImage
from PyQt5 import QtGui
import os, numpy, sys
from pathlib import Path
sys.path.append(str(Path.home()) + '/github/Experiments')
from Camera import *
from ExpUtils.Communicator import *


class Imager(QtWidgets.QWidget):
    def __init__(self, dtype=numpy.int16, shape=(600,600)):
        super(Imager, self).__init__()
        self.queue = Queue()
        self.dtype = dtype
        self.shape = shape
        self.basename = ''
        self.basepath = str(Path.home()) + '/data/'
        self.filename = ''

        # load ui
        path = os.path.join(os.path.dirname(__file__), "form.ui")
        self.ui = uic.loadUi(path, self)
        self.setColorTable()
        self.fps = self.ui.fps_input.value()
        self.cam = self.setCamera()                    # handle inputs
        self.shape = (self.ui.X_sz.value(), self.ui.Y_sz.value())
        self.ui.stop_button.clicked.connect(self.stop_rec)
        self.ui.rec_button.clicked.connect(self.start_rec)
        self.ui.fps_input.valueChanged.connect(self.updateFPS)
        self.ui.exposure_input.valueChanged.connect(self.updateExposure)
        self.ui.colormaps.currentIndexChanged.connect(self.setColorTable)

        # set view window
        self.scene = QtWidgets.QGraphicsScene()
        self.ui.graphicsView.setScene(self.scene)
        self.ui.graphicsView.show()
        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.updateplot)
        timer.start(100)
        self.updateplot()
        self.conn = Communicator(role='client')
        self.conn.register_callback(dict(start=self.start_rec))
        self.conn.register_callback(dict(stop=self.stop_rec))
        self.conn.register_callback(dict(basename=self.set_basename))

    def set_basename(self, key):
        self.basename = key['basename']

    def start_rec(self, *args):
        self.ui.rec_button.setDown(True)
        self.ui.stop_button.setDown(False)
        self.filename = self.cam.rec(basename=self.basepath + self.basename)
        self.conn.send(dict(started=True, filename=self.filename, program='Imager'))

    def stop_rec(self, *args):
        self.ui.rec_button.setDown(False)
        self.cam.stop()
        self.conn.send(dict(stopped=True))

    def updateFPS(self):
        self.fps = self.ui.fps_input.value()
        self.cam.set_frame_rate(self.fps)

    def updateExposure(self):
        self.cam.namespace.scale = self.ui.exposure_input.value()

    def setCamera(self):
        cam = Camera(shape=self.shape)
        cam.fps = self.fps
        cam.set_queue(self.queue)
        cam.start()
        return cam

    def updateplot(self):
        if not self.queue.empty():
            item = self.queue.get()
            image = QImage(item['frames'], self.cam.height, self.cam.width, self.cam.height, QImage.Format_Indexed8)
            image.setColorTable(self.color_table)
            self.scene.clear()
            self.scene.addPixmap(QPixmap(image))
            self.ui.graphicsView.fitInView(self.scene.sceneRect(), QtCore.Qt.KeepAspectRatio)
            self.ui.graphicsView.update()
            self.ui.frames.display(self.cam.iframe)

    def closeEvent(self, event):
        print('stopping')
        self.cam.stop()
        self.cam.quit()
        self.conn.quit()
        print('stopped')
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


# !/usr/bin/env python
from PyQt5 import uic, QtWidgets, QtCore
from PyQt5.QtGui import QPixmap, QImage
from PyQt5 import QtGui
import os, numpy
from queue import Queue
from Camera import *


class Imager(QtWidgets.QWidget):
    def __init__(self, shape=(600, 600), dtype=numpy.int16):
        super(Imager, self).__init__()
        self.queue = Queue()
        self.dtype = dtype
        self.shape = shape
        self.colormap = 'gray'

        # load ui
        path = os.path.join(os.path.dirname(__file__), "form.ui")
        self.ui = uic.loadUi(path, self)

        self.fps = self.ui.fps_input.value()
        self.cam = self.setCamera()                    # handle inputs
        
        self.ui.stop_button.clicked.connect(self.cam.stop)
        self.ui.rec_button.clicked.connect(lambda: self.cam.rec('%s_%s' % (self.ui.animal_input.text(),
                                                                           self.ui.session_input.text())))
        self.ui.color_input.stateChanged.connect(self.setColorMap)
        self.ui.fps_input.valueChanged.connect(self.updateFPS)
        self.ui.exposure_input.valueChanged.connect(self.updateExposure)

        # set view window
        self.scene = QtWidgets.QGraphicsScene()
        self.ui.graphicsView.setScene(self.scene)
        self.ui.graphicsView.show()
        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.updateplot)
        timer.start(100)
        self.updateplot()

    def updateFPS(self):
        self.fps = self.ui.fps_input.value()
        self.cam.set_frame_rate(self.fps)

    def updateExposure(self):
        self.cam.namespace.scale = self.ui.exposure_input.value()

    def setCamera(self):
        cam = Camera()
        cam.fps = self.fps
        cam.set_queue(self.queue)
        cam.start()
        return cam

    def updateplot(self):
        if not self.queue.empty():
            item = self.queue.get()
            image = QImage(item['frames'], self.cam.height, self.cam.width, self.cam.height, QImage.Format_Indexed8)
            image.setColorTable(self.getColorTable())
            self.scene.clear()
            self.scene.addPixmap(QPixmap(image))
            self.ui.graphicsView.fitInView(self.scene.sceneRect(), QtCore.Qt.KeepAspectRatio)
            self.ui.graphicsView.update()
            self.ui.frames.display(self.cam.iframe)

    def closeEvent(self, event):
        print('stopping')
        self.cam.stop()
        self.cam.quit()
        print('stopped')
        event.accept()  # let the window close

    def getColorTable(self):
        if self.colormap == 'jet':
            t = lambda i, v: int(min(max(-4.0 * abs(i - 255 * v / 4) + 255 * 3 / 2, 0), 255))
            color_table = [QtGui.qRgb(t(i, 3), t(i, 2), t(i, 1)) for i in range(256)]
        elif self.colormap == 'gray':
            color_table = [QtGui.qRgb(i, i, i) for i in range(256)]
        return color_table

    def setColorMap(self):
        if self.ui.color_input.checkState():
            self.colormap = 'jet'
        else:
            self.colormap = 'gray'


if __name__ == "__main__":
    MainEventThread = QtWidgets.QApplication([])
    MainApp = Imager()
    MainApp.show()
    MainEventThread.exec()


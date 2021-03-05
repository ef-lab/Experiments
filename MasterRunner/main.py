# !/usr/bin/env python
from PyQt5 import uic, QtWidgets, QtCore
from PyQt5 import QtGui
import os, numpy, sys, threading, time
from queue import Queue
from Camera import *
from Connector import *


sys.path.insert(0, "~/github/PyMouse")


class MasterRunner(QtWidgets.QWidget):
    def __init__(self, shape=(600, 600), dtype=numpy.int16):
        super(MasterRunner, self).__init__()
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
        timer.timeout.connect(self.runner)
        timer.start(100)
        self.updateplot()

    def runTask(self):
        global logger
        logger = Logger(protocol=protocol)  # setup logger
        exec(open(logger.get_protocol()).read())

    def runner(self):


    def closeEvent(self, event):
        print('stopping')
        self.cam.stop()
        self.cam.quit()
        print('stopped')
        event.accept()  # let the window close


if __name__ == "__main__":
    MainEventThread = QtWidgets.QApplication([])
    MainApp = MasterRunner()
    MainApp.show()
    MainEventThread.exec()


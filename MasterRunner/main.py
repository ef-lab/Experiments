# This Python file uses the following encoding: utf-8
import os
from PyQt5 import uic, QtWidgets
from PyQt5.QtGui import QPixmap

class MasterRunner(QtWidgets.QWidget):
    def __init__(self):
        super(MasterRunner, self).__init__()
        self.load_ui()
        self.ui.pushButton.clicked.connect(self.Pushed)
        self.ui.radioButton.toggled.connect(self.Selected)
        self.scene = QtWidgets.QGraphicsScene()
        pix = QPixmap('image2.png')
        self.scene.addPixmap(pix)
        self.ui.graphicsView.setScene(self.scene)
        self.ui.graphicsView.show()

    def load_ui(self):
        path = os.path.join(os.path.dirname(__file__), "form.ui")
        self.ui = uic.loadUi(path, self)

    def Pushed(self):
        print('I was pushed')
        pix2 = QPixmap('image.png')
        self.scene.clear()
        self.scene.addPixmap(pix2)
        self.ui.graphicsView.update()

    def Selected(self):
        if self.ui.radioButton.isChecked():
            print('I am selected')


if __name__ == "__main__":
    MainEventThread = QtWidgets.QApplication([])
    MainApp = MasterRunner()
    MainApp.show()
    MainEventThread.exec()

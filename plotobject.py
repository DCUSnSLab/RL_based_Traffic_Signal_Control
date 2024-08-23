import numpy as np
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, pyqtSlot
import pyqtgraph as pg
from pyqtgraph import PlotWidget

from Infra import Direction, Infra, SECTION_RESULT, TOTAL_RESULT


class PlotObject():
    def __init__(self, title, l_bottom, l_left, ismoving=False):
        self.__title = title
        self.__label_bottom = l_bottom
        self.__label_left = l_left
        self._isMoving = ismoving

        self._plotwidget: PlotWidget = None
        self._plots = []
        self._labels = []

        self.colorset = ('r', 'g', 'b', 'c') #SB, NB, EB, WB
        self.__ymax = 0

        self.__initUI()

        #data
        self.rtinfra: Infra = None
        self.total_result_comp = None

    def __initUI(self):
        self._plotwidget = pg.PlotWidget(title=self.__title)
        self._plotwidget.plotItem.setLabels(bottom=self.__label_bottom, left=self.__label_left)
        self._plotwidget.plotItem.getAxis('bottom').setPen(pg.mkPen(color='#000000', width=3))
        self._plotwidget.plotItem.getAxis('left').setPen(pg.mkPen(color='#000000', width=3))
        self._plotwidget.setBackground('w')
        self._plotwidget.setStyleSheet(
            "border: 1px solid black; padding-left:10px; padding-right:10px; background-color: white;")

    def getWidtget(self):
        return self._plotwidget

    def setPlotYRange(self, min, max):
        self._plotwidget.plotItem.setYRange(min, max)
        self.__y_max = self._plotwidget.plotItem.viewRange()[1][1]

    def setLabelPos(self, x, y_max):
        d_gap = y_max * 0.07
        y_max -= d_gap
        for label in self._labels:
            label.setPos(x, y_max)
            y_max -= d_gap

    def addPlot(self, name='default', color='black'):
        self._plots.append(self._plotwidget.plot(pen=color))

        #add label
        label = pg.TextItem(text='── ' + name + ' (' + color + ')',color=color)
        label.setFont(QFont("Arial", 12))
        self._plotwidget.addItem(label)
        self._labels.append(label)

    def updateLabels(self, xmin=0):
        y_max = self._plotwidget.plotItem.viewRange()[1][1]
        self.setLabelPos(xmin, y_max)

    def updatePlot(self):
        pass

    def update(self, rtinfra, total_result_comp):
        self.rtinfra = rtinfra
        self.total_result_comp = total_result_comp
        self.updateLabels()
        self.updatePlot()



class PlotSection(PlotObject):
    def __init__(self, title, l_bottom, l_left, sel_data, ismoving=False):
        super().__init__(title, l_bottom, l_left, ismoving)
        self.sectionColor = {}
        self.__initSectionColor()
        self.__initSectionplot()
        self.__sel_data: SECTION_RESULT = sel_data

    def __initSectionColor(self):
        for i, dr in enumerate(Direction):
            print(dr.value[0])
            self.sectionColor[dr.value[0]] = (dr.name, self.colorset[i])

    def __initSectionplot(self):
        for i in range(4):
            self.addPlot(self.sectionColor[i][0], self.sectionColor[i][1])

    def updatePlot(self):
        sections = self.rtinfra.getSections()
        time_data = None#self.rtinfra.getTime()
        data = None
        for i, plot in enumerate(self._plots):
            time_data = sections[str(i)].getDatabyID(SECTION_RESULT.TIME)
            data = sections[str(i)].getDatabyID(self.__sel_data)
            if self._isMoving is True:
                time_data = list(time_data)[-500:]
                data = list(data)[-500:]
            plot.setData(time_data, data)

        if self._isMoving is True:
            self._plotwidget.plotItem.setXRange(max(time_data[-1] - 500, 0), time_data[-1])
            self.updateLabels(max(time_data[-1] - 500, 0))

class PlotSectionInfra(PlotObject):
    def __init__(self, title, l_bottom, l_left, sel_data, ismoving=False):
        super().__init__(title, l_bottom, l_left, ismoving)
        self.__sel_data: TOTAL_RESULT = sel_data
        self.addPlot('data', 'r')
    def updatePlot(self):
        time_data = self.rtinfra.getTime()
        data = self.rtinfra.getDatabyID(self.__sel_data)
        if self.__sel_data == TOTAL_RESULT.TOTAL_CO2:
            data = np.array(data) / 1000
        self._plots[0].setData(time_data, data)
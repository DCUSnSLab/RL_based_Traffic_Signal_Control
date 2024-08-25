import random
from typing import List

import numpy as np
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, pyqtSlot
import pyqtgraph as pg
from pyqtgraph import PlotWidget
from scipy.signal import butter, filtfilt

from Infra import Direction, Infra, SECTION_RESULT, TOTAL_RESULT


class PlotObject():
    def __init__(self, title, l_bottom, l_left, compInfra: List[Infra]=None, ismoving=False):
        self.__title = title
        self.__label_bottom = l_bottom
        self.__label_left = l_left
        self._isMoving = ismoving

        self._plotwidget: PlotWidget = None
        self._plots = []
        self._labels = []
        self._compInfra: List[Infra] = compInfra

        self.colorset = ('r', 'g', 'b', 'c') #SB, NB, EB, WB
        self.__ymax = 0

        self.__initUI()

        #data
        self.rtinfra: Infra = None
        self.compare_infra: List[Infra] = None

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

        color_str = f"RGB{color}"
        #add label
        label = pg.TextItem(text='── ' + name + ' (' + color_str + ')',color=color)
        label.setFont(QFont("Arial", 12))
        self._plotwidget.addItem(label)
        self._labels.append(label)

    def setLabelText(self, idx, name):
        self._labels[idx].setPlainText(name)

    def low_pass_filter(self, data, cutoff=0.2, fs=1.0, order=1):
        if len(data) <= 9:  # 필터의 padlen보다 작은 경우
            return data  # 필터링을 건너뛰고 원래 데이터를 반환
        nyq = 0.5 * fs  # Nyquist Frequency
        normal_cutoff = cutoff / nyq
        b, a = butter(order, normal_cutoff, btype='low', analog=False)
        y = filtfilt(b, a, data, padlen=3)  # padlen 값을 줄여서 설정
        return y

    def updateLabels(self, xmin=0):
        y_max = self._plotwidget.plotItem.viewRange()[1][1]
        self.setLabelPos(xmin, y_max)

    def updatePlot(self):
        pass

    def update(self, rtinfra, compare_infras):
        self.rtinfra = rtinfra
        self.compare_infra = compare_infras
        self.updateLabels()
        self.updatePlot()

    def generate_random_color(self):
        # 0에서 255 사이의 랜덤한 RGB 값을 생성
        r = random.randint(0, 255)
        g = random.randint(0, 255)
        b = random.randint(0, 255)
        return (r, g, b)



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

            data = self.low_pass_filter(data)
            plot.setData(time_data, data)

        if self._isMoving is True:
            self._plotwidget.plotItem.setXRange(max(time_data[-1] - 500, 0), time_data[-1])
            self.updateLabels(max(time_data[-1] - 500, 0))

class PlotInfra(PlotObject):
    def __init__(self, title, l_bottom, l_left, sel_data, selType, compinfra=None, ismoving=False):
        super().__init__(title, l_bottom, l_left, compinfra, ismoving)
        self.__sel_data: TOTAL_RESULT = sel_data
        self.__selType = selType
        self.colorset = ('g','b','c')
        if self._compInfra is not None:
            for i, ci in enumerate(self._compInfra):
                color = 'b'
                if i < 3:
                    color = self.colorset[i]
                else:
                    color = self.generate_random_color()
                self.addPlot(ci.sigType+'_'+ci.getSavedTime().strftime("%Y-%m-%d"), color)

        self.addPlot('Proposed', 'r')

    def updatePlot(self):
        time_data = self.rtinfra.getTime()
        data = self.rtinfra.getDatabyID(self.__sel_data)
        if self.__sel_data == TOTAL_RESULT.TOTAL_CO2:
            data = np.array(data) / 1000
        self._plots[-1].setData(time_data, data)

        if self._compInfra is not None:
            for i, ci in enumerate(self._compInfra):
                comptime = ci.getTime()
                compinfra = ci.getDatabyID(self.__sel_data) if ci is not None else 0

                if self.__sel_data == TOTAL_RESULT.TOTAL_CO2:
                    compinfra = np.array(compinfra) / 1000
                self._plots[i].setData(comptime, compinfra)

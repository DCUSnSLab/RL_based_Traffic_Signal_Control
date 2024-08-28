import random
from enum import Enum
from typing import List

import numpy as np
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, pyqtSlot
import pyqtgraph as pg
from pyqtgraph import PlotWidget
from scipy.signal import butter, filtfilt

from Infra import Direction, Infra, SECTION_RESULT, TOTAL_RESULT, SMUtil


class PLOTMODE(Enum):
    GREENTIME = (lambda: PlotSection('Section Signal Green Time', 'Time(s)', 'green time', SECTION_RESULT.GREEN_TIME), SECTION_RESULT.GREEN_TIME.name)
    QUEUE = (lambda: PlotSection('Queue', 'Time(s)', 'Queue Length (Number of Vehicles)', SECTION_RESULT.TRAFFIC_QUEUE), SECTION_RESULT.TRAFFIC_QUEUE.name)
    CO2TOTALACC = (lambda: PlotInfra('Accumulative Total CO2 Emissions', 'Time(s)', 'CO2 Emission(Ton)', TOTAL_RESULT.TOTAL_CO2_ACC), TOTAL_RESULT.TOTAL_CO2_ACC.name)
    CO2SECTION = (lambda: PlotSection('CO2 Emissions by Bound', 'Time(s)', 'CO2 Emission(kg)', SECTION_RESULT.SECTION_CO2, ismoving=False), SECTION_RESULT.SECTION_CO2.name)
    SECTIONSPEEDINT = (lambda: PlotSection('Section Speed by Interval('+str(SMUtil.interval)+'s)', 'Time(every '+str(SMUtil.interval)+'s)', 'Speed(km/h)', SECTION_RESULT.SPEED_INT,ismoving=False, interval=100, istimeinterval=True), SECTION_RESULT.SPEED_INT.name)
    TOTALCO2 = (lambda: PlotInfra('Total CO2 Emissions', 'Time(s)', 'CO2 Emission(Ton)', TOTAL_RESULT.TOTAL_CO2), TOTAL_RESULT.TOTAL_CO2.name, 0)
    TOTALVOLUMEACC = (lambda: PlotInfra('Accumulative Total Volume', 'Time(s)', 'Volumes(Number of Vehicles)', TOTAL_RESULT.TOTAL_VOLUME), TOTAL_RESULT.TOTAL_VOLUME.name)
    @classmethod
    def from_string(cls, result):
        for mode in cls:
            if mode.value[1] == result:
                return mode
        raise ValueError(f"{result} is not a valid SignalMode value")

class PlotObject():
    def __init__(self, title, l_bottom, l_left, sel_data, useComp=False, compInfra: List[Infra]=None, ismoving=False, interval=500, isTimeInterval=False):
        self._title = title
        self.__label_bottom = l_bottom
        self.__label_left = l_left
        self._sel_data: SECTION_RESULT = sel_data
        self._isMoving = ismoving
        self._movingInterval = interval
        self._isTimeInterval = isTimeInterval
        self._ymax = 0
        self._ymin = 0

        self._plotwidget: PlotWidget = None
        self._plots = []
        self._labels = []
        self._compInfra: List[Infra] = compInfra
        self.isCompAdded = False
        self.useComp = useComp

        self.colorset = ('r', 'g', 'b', (255, 204, 0)) #SB, NB, EB, WB


        self.__initUI()

        #data
        self.rtinfra: Infra = None
        self.compare_infra: List[Infra] = None

    def __initUI(self):
        self._plotwidget = pg.PlotWidget(title=self._title)
        self._plotwidget.plotItem.setLabels(bottom=self.__label_bottom, left=self.__label_left)
        self._plotwidget.plotItem.getAxis('bottom').setPen(pg.mkPen(color='#000000', width=3))
        self._plotwidget.plotItem.getAxis('left').setPen(pg.mkPen(color='#000000', width=3))
        self._plotwidget.setBackground('w')
        self._plotwidget.setStyleSheet(
            "border: 1px solid black; padding-left:10px; padding-right:10px; background-color: white;")

    def getWidtget(self):
        return self._plotwidget
    def getYMax(self):
        return self._ymax

    def setPlotYRange(self, data):
        if len(data) > 0:
            data = np.array(data)
            min_v = np.min(data)
            max_v = np.max(data)
            self._ymax = max(self._ymax, max_v)
            self._ymin = min(self._ymin, min_v)
            self._plotwidget.plotItem.setYRange(self._ymin, self._ymax)

    def setLabelPos(self, x, y_max):
        d_gap = (y_max) * 0.1
        #y_max -= d_gap
        for label in self._labels:
            label.setPos(x, y_max)
            y_max -= d_gap

    def addPlot(self, name='default', color='black'):
        if self._sel_data != SECTION_RESULT.GREEN_TIME:
            self._plots.append(self._plotwidget.plot(pen=color))
        else:
            self._plots.append(self._plotwidget.plot(pen=None, symbol='o', symbolSize=3, symbolBrush=color, symbolPen=None))

        color_str = f"RGB{color}"
        #add label
        label = pg.TextItem(text='── ' + name + ' (' + color_str + ')',color=color)
        label.setFont(QFont("Arial", 12))
        self._plotwidget.addItem(label)
        self._labels.append(label)

    def addCompPlot(self, compInfra):
        if compInfra is not None and self.useComp is True:
            if len(self._plots) > 0:
                while len(self._plots) > 0:
                    self._plotwidget.removeItem(self._plots.pop())
                    self._plotwidget.removeItem(self._labels.pop())

            for i, ci in enumerate(self._compInfra):
                color = 'b'
                if i < 3:
                    color = self.colorset[i]
                else:
                    color = self.generate_random_color()
                self.addPlot(ci.sigType+'_'+ci.getSavedTime().strftime("%Y-%m-%d"), color)
            self.isCompAdded = True
            self.addPlot('Proposed', 'r')


    def setLabelText(self, idx, name):
        self._labels[idx].setPlainText(name)

    def low_pass_filter(self, data, cutoff=0.05, fs=1.0, order=8):
        if len(data) <= 15:  # 필터의 padlen보다 작은 경우
            return data  # 필터링을 건너뛰고 원래 데이터를 반환
        nyq = 0.5 * fs  # Nyquist Frequency
        normal_cutoff = cutoff / nyq
        b, a = butter(order, normal_cutoff, btype='low', analog=False)
        y = filtfilt(b, a, data, padlen=5)  # padlen 값을 줄여서 설정
        return y

    def moving_average(self, data, window_size=None):
        dsize = len(data)
        if window_size is None:
            window_size = max(1, int(dsize * 0.05))

        if len(data) < window_size:
            return data  # 데이터가 창 크기보다 작으면 필터링을 건너뜁니다.
        return np.convolve(data, np.ones(window_size) / window_size, mode='same')

    def updateLabels(self, xmin=0):
        #y_max = self._plotwidget.plotItem.viewRange()[1][1]
        self.setLabelPos(xmin, self._ymax)

    def trimData(self, time, raw):
        a = np.array(time)
        b = np.array(raw)

        if len(a) == 0 or len(b) == 0:
            return a, b
        else:
            # 두 배열 중 더 짧은 길이 찾기
            min_length = min(len(a), len(b))

            # 더 짧은 길이에 맞춰 자르기
            a_trimmed = a[:min_length]
            b_trimmed = b[:min_length]
            return a_trimmed, b_trimmed

    def updatePlot(self):
        pass

    def update(self, rtinfra, compare_infras):
        self.rtinfra = rtinfra
        self._compInfra = compare_infras
        if self._compInfra is not None and self.isCompAdded is False:
            self.addCompPlot(self._compInfra)
        self.updatePlot()
        self.updateLabels()

    def generate_random_color(self):
        # 0에서 255 사이의 랜덤한 RGB 값을 생성
        r = random.randint(0, 255)
        g = random.randint(0, 255)
        b = random.randint(0, 255)
        return (r, g, b)

    def resetCompAdded(self):
        self.isCompAdded = False


class PlotSection(PlotObject):
    def __init__(self, title, l_bottom, l_left, sel_data, ismoving=False, interval=500, istimeinterval=False):
        super().__init__(title, l_bottom, l_left, sel_data, useComp=False, ismoving=ismoving, interval=interval, isTimeInterval=istimeinterval)
        self.sectionColor = {}
        self.__initSectionColor()
        self.__initSectionplot()

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
            if self._isTimeInterval is False:
                time_data = sections[str(i)].getDatabyID(SECTION_RESULT.TIME)
            else:
                time_data = sections[str(i)].getDatabyID(SECTION_RESULT.TIMEINT)

            rawdata = sections[str(i)].getDatabyID(self._sel_data)
            if self._isMoving is True:
                time_data = list(time_data)[-self._movingInterval:]
                rawdata = list(rawdata)[-self._movingInterval:]

            time_data, rawdata = self.trimData(time_data, rawdata)

            if self._sel_data != SECTION_RESULT.GREEN_TIME:
                #rawdata = self.low_pass_filter(rawdata)
                rawdata = self.moving_average(rawdata)

            # min_length = min(len(time_data), len(data))
            # time_data = list(time_data)[:min_length]
            # data = list(data)[:min_length]

            plot.setData(time_data, rawdata)
            self.setPlotYRange(rawdata)
            #self._plotwidget.plotItem.setYRange(min(min(data), 0), max(data)+)

        if self._isMoving is True:
            self._plotwidget.plotItem.setXRange(max(time_data[-1] - self._movingInterval, 0), time_data[-1])
            self.updateLabels(max(time_data[-1] - self._movingInterval, 0))


class PlotInfra(PlotObject):
    def __init__(self, title, l_bottom, l_left, sel_data, selType=None, compinfra=None, ismoving=False, istimeinterval=False):
        super().__init__(title, l_bottom, l_left, sel_data, True, compinfra, ismoving, isTimeInterval=istimeinterval)
        self.__selType = selType
        self.colorset = ('g','b','c')
        self.addCompPlot(self._compInfra)
        self.addPlot('Proposed', 'r')

    def updatePlot(self):
        time_data = self.rtinfra.getTime()
        data = self.rtinfra.getDatabyID(self._sel_data)

        if self._sel_data == TOTAL_RESULT.TOTAL_CO2 or self._sel_data == TOTAL_RESULT.TOTAL_CO2_ACC:
            data = np.array(data) / 1000

        # min_length = min(len(time_data), len(data))
        # time_data = list(time_data)[:min_length]
        # data = list(data)[:min_length]

        time_data, rawdata = self.trimData(time_data, data)
        if self._sel_data == TOTAL_RESULT.TOTAL_CO2:
            rawdata = self.low_pass_filter(rawdata)
        self._plots[-1].setData(time_data, rawdata)
        self.setPlotYRange(data)

        compinfra = None
        if self._compInfra is not None:
            for i, ci in enumerate(self._compInfra):
                comptime = ci.getTime()
                compinfra = ci.getDatabyID(self._sel_data) if ci is not None else 0

                if self._sel_data == TOTAL_RESULT.TOTAL_CO2  or self._sel_data == TOTAL_RESULT.TOTAL_CO2_ACC:
                    compinfra = np.array(compinfra) / 1000

                # min_length = min(len(comptime), len(compinfra))
                # comptime = list(comptime)[:min_length]
                # compinfra = list(compinfra)[:min_length]
                comptime, compinfra = self.trimData(comptime, compinfra)
                if self._sel_data == TOTAL_RESULT.TOTAL_CO2:
                    compinfra = self.low_pass_filter(compinfra)
                self._plots[i].setData(comptime, compinfra)
                self.setPlotYRange(compinfra)

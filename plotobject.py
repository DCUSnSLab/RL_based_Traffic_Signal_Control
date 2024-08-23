from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, pyqtSlot
import pyqtgraph as pg
from pyqtgraph import PlotWidget

from Infra import Direction
from RunSimulation import SECTION_RESULT


class PlotObject():
    def __init__(self, title, l_bottom, l_left):
        self.__title = title
        self.__label_bottom = l_bottom
        self.__label_left = l_left

        self._plotwidget: PlotWidget = None
        self._plots = []
        self._labels = []

        self.colorset = ('r', 'g', 'b', 'c') #SB, NB, EB, WB
        self.__ymax = 0

        self.__initUI()

        #data
        self.section_results = None
        self.total_results = None
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

    def addPlot(self, name='default', color='black'):
        self._plots.append(self._plotwidget.plot(pen=color))

        #add label
        label = pg.TextItem(text='── ' + name + ' (' + color + ')',color=color)
        label.setFont(QFont("Arial", 12))
        self._plotwidget.addItem(label)
        self._labels.append(label)

    def updateData(self):
        pass

    def update(self, section_results, total_results, total_result_comp):
        self.section_results = section_results
        self.total_results = total_results
        self.total_result_comp = total_result_comp
        self.updateData()


class PlotSection(PlotObject):
    def __init__(self, title, l_bottom, l_left, sel_data):
        super().__init__(title, l_bottom, l_left)
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

    def updateData(self):
        # Section Emission Graph 데이터 준비
        sections = {
            '0': ([], [], []),
            '1': ([], [], []),
            '2': ([], [], []),
            '3': ([], [], [])
        }
        sections = {}

        for result in self.section_results:
            section = result['Section']
            if section in sections:
                for sr in SECTION_RESULT:
                    sections[section][sr.value[0]].append(result[sr.value[1]])
            else:
                sections[section] = []
                for sr in SECTION_RESULT:
                    sections[section].append([])

        for i, plot in enumerate(self._plots):
            plot.setData(sections[str(i)][SECTION_RESULT.TIME.value[0]], sections[str(i)][self.__sel_data.value[0]])

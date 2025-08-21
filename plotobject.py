import random
from enum import Enum
from typing import List
from hashlib import md5

import numpy as np
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, pyqtSlot
import pyqtgraph as pg
from pyqtgraph import PlotWidget
from scipy.signal import butter, filtfilt

from Infra import Direction, Infra, SMUtil, INTERSECTION_RESULT, NETWORK_RESULT


class PLOTMODE(Enum):
    # Intersection
    CO2INTERSECTION = (lambda: PlotSection('CO2 Emissions by Intersection', 'Time(s)', 'CO2 Emission(Ton)', INTERSECTION_RESULT.TOTAL_CO2, ismoving=False), INTERSECTION_RESULT.TOTAL_CO2.name)
    QUEUE = (lambda: PlotSection('Queue', 'Time(s)', 'Queue Length (Number of Vehicles)', INTERSECTION_RESULT.TOTAL_QUEUE), INTERSECTION_RESULT.TOTAL_QUEUE.name)
    # Infra(Network)
    TOTALCO2 = (lambda: PlotInfra('Total CO2 Emissions', 'Time(s)', 'CO2 Emission(Ton)', NETWORK_RESULT.NET_TOTAL_CO2), NETWORK_RESULT.NET_TOTAL_CO2.name, 0)
    CO2TOTALACC = (lambda: PlotInfra('Accumulative Total CO2 Emissions', 'Time(s)', 'CO2 Emission(Ton)', NETWORK_RESULT.NET_TOTAL_CO2_ACC), NETWORK_RESULT.NET_TOTAL_CO2_ACC.name)
    TOTALVOLUME = (lambda: PlotInfra('Accumulative Total Volume', 'Time(s)', 'Volumes(Number of Vehicles)', NETWORK_RESULT.NET_TOTAL_VOLUME), NETWORK_RESULT.NET_TOTAL_VOLUME.name)
    TOTALQUEUE = (lambda: PlotInfra('Total Queue', 'Time(s)', 'Queue Length (Number of Vehicles)', NETWORK_RESULT.NET_TOTAL_QUEUE), NETWORK_RESULT.NET_TOTAL_QUEUE.name, 0)
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
        self._sel_data: INTERSECTION_RESULT = sel_data
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
        self._plots.append(self._plotwidget.plot(pen=color))

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
        self.sectionColor = {}              # intid -> (label, color)
        self._plots_by_intid = {}           # intid -> PlotDataItem
        self._labels_by_intid = {}          # intid -> TextItem

    # ---------- 내부 유틸 ----------

    def __ensure_initialized(self) -> bool:
        """rtinfra가 준비되면 색/플롯을 1회 초기화한다."""
        if self.rtinfra is None:
            return False
        if not self.sectionColor:
            self.__initIntersectionColor()
            self.__initIntersectionplot()
        return True

    def __initIntersectionColor(self):
        """교차로 ID(intid)별 고정 색 초기화."""
        inters = self.rtinfra.get_intersections()
        if not inters:
            self.sectionColor = {}
            return

        # 팔레트: 기본 제공 or colorset 사용
        base_palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
                        "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
                        "#bcbd22", "#17becf"]
        colors = list(self.colorset) if getattr(self, "colorset", None) else base_palette

        self.sectionColor.clear()
        for i, intid in enumerate(sorted(inters.keys())):
            label = f"INT {intid}"
            color = colors[i % len(colors)]
            self.sectionColor[intid] = (label, color)

    def __initIntersectionplot(self):
        """교차로별 PlotDataItem / Label 생성."""
        inters = self.rtinfra.get_intersections()
        if not inters:
            return

        self._plots_by_intid.clear()
        self._labels_by_intid.clear()

        for intid in sorted(inters.keys()):
            label, color = self.sectionColor[intid]
            # 선 생성
            plot_item = self._plotwidget.plot(pen=color)
            self._plots.append(plot_item)  # 기존 리스트에도 넣어 GUI 스타일 유지
            self._plots_by_intid[intid] = plot_item

            # 라벨 생성(기존 addPlot의 표시 형식 유지)
            color_str = f"RGB{color}"
            text = pg.TextItem(text='── ' + label + ' (' + color_str + ')', color=color)
            text.setFont(QFont("Arial", 12))
            self._plotwidget.addItem(text)
            self._labels.append(text)
            self._labels_by_intid[intid] = text

    # ---------- 업데이트 ----------

    def updatePlot(self):
        # 1) 초기화 보장
        if not self.__ensure_initialized():
            return  # rtinfra 아직 없음

        inters = self.rtinfra.get_intersections()
        if not inters:
            return

        present_ids = set(inters.keys())
        line_ids    = set(self._plots_by_intid.keys())

        # 2) 신규 교차로: 라인/라벨 추가
        added = sorted(present_ids - line_ids)
        if added:
            # 색 맵 없으면 재초기화
            if not self.sectionColor:
                self.__initIntersectionColor()
            for intid in added:
                label, color = self.sectionColor.get(intid, (f"INT {intid}", 'k'))
                plot_item = self._plotwidget.plot(pen=color)
                self._plots.append(plot_item)
                self._plots_by_intid[intid] = plot_item

                text = pg.TextItem(text='── ' + label + f' (RGB{color})', color=color)
                text.setFont(QFont("Arial", 12))
                self._plotwidget.addItem(text)
                self._labels.append(text)
                self._labels_by_intid[intid] = text

        # 3) 사라진 교차로: 라인/라벨 제거
        removed = sorted(line_ids - present_ids)
        for intid in removed:
            plot_item = self._plots_by_intid.pop(intid, None)
            label_item = self._labels_by_intid.pop(intid, None)
            if plot_item is not None:
                try: self._plotwidget.removeItem(plot_item)
                except Exception: pass
                if plot_item in self._plots:
                    self._plots.remove(plot_item)
            if label_item is not None:
                try: self._plotwidget.removeItem(label_item)
                except Exception: pass
                if label_item in self._labels:
                    self._labels.remove(label_item)
            if intid in self.sectionColor:
                self.sectionColor.pop(intid, None)

        # 4) 데이터 갱신 + 축 범위 계산
        xmin = None; xmax = None; ymin = None; ymax = None
        for intid, inter in inters.items():
            plot_item = self._plots_by_intid.get(intid)
            if plot_item is None:
                continue

            xs = list(inter.get_databy_id(INTERSECTION_RESULT.TIME))
            ys = list(inter.get_databy_id(self._sel_data))  # ← PLOTMODE에서 넘긴 INTERSECTION_RESULT 사용

            # Ton 단위로 그리려면 여기서 /1000 (현재 Infra는 kg)
            if self._sel_data in (INTERSECTION_RESULT.TOTAL_CO2, INTERSECTION_RESULT.TOTAL_CO2_ACC):
                ys = list(np.array(ys) / 1000.0)

            xs, ys = self.trimData(xs, ys)
            plot_item.setData(xs, ys)

            if (len(xs) > 0) and (len(ys) > 0):  # 또는 (xs.size > 0) and (ys.size > 0)
                _xmin, _xmax = float(xs[0]), float(xs[-1])
                _ymin, _ymax = float(np.min(ys)), float(np.max(ys))
                xmin = _xmin if xmin is None else min(xmin, _xmin)
                xmax = _xmax if xmax is None else max(xmax, _xmax)
                ymin = _ymin if ymin is None else min(ymin, _ymin)
                ymax = _ymax if ymax is None else max(ymax, _ymax)

            plot_item.setData(xs, ys)

        # 5) Y-range 갱신(기존 헬퍼 사용)
        #   (여기서는 전체 y 범위를 계산해 setYRange 하는 게 UX상 더 빠름)
        if ymin is not None and ymax is not None:
            if ymin == ymax:
                pad = 1.0 if ymax == 0 else abs(ymax) * 0.05
                self._plotwidget.plotItem.setYRange(ymin - pad, ymax + pad)
                self._ymin, self._ymax = ymin - pad, ymax + pad
            else:
                pad = (ymax - ymin) * 0.1
                self._plotwidget.plotItem.setYRange(ymin - pad, ymax + pad)
                self._ymin, self._ymax = ymin - pad, ymax + pad

        # 6) 레이아웃 라벨(텍스트) 위치 조정
        if xmin is not None:
            self.updateLabels(xmin)


class PlotInfra(PlotObject):
    def __init__(self, title, l_bottom, l_left, sel_data, selType=None, compinfra=None, ismoving=False, istimeinterval=False):
        super().__init__(title, l_bottom, l_left, sel_data, True, compinfra, ismoving, isTimeInterval=istimeinterval)
        self.__selType = selType
        self.colorset = ('g','b','c')
        self.addCompPlot(self._compInfra)
        self.addPlot('Proposed', 'r')

    def updatePlot(self):
        # ① 네트워크 시간/데이터 (새 인터페이스 사용)
        time_data = self.rtinfra.get_databy_id(NETWORK_RESULT.NET_TIME)
        data = self.rtinfra.get_databy_id(self._sel_data)

        # CO2는 Ton 표기
        if self._sel_data in (NETWORK_RESULT.NET_TOTAL_CO2, NETWORK_RESULT.NET_TOTAL_CO2_ACC):
            data = np.array(data) / 1000.0

        time_data, rawdata = self.trimData(time_data, data)
        if self._sel_data == NETWORK_RESULT.NET_TOTAL_CO2:
            rawdata = self.low_pass_filter(rawdata)

        # 'Proposed' 라인은 항상 마지막으로 추가되어 있음
        if self._plots:
            self._plots[-1].setData(time_data, rawdata)
        self.setPlotYRange(data)

        # ② 비교 인프라 (있다면)
        if self._compInfra is not None:
            for i, ci in enumerate(self._compInfra):
                comptime = ci.get_databy_id(NETWORK_RESULT.NET_TIME)
                compinfra = ci.get_databy_id(self._sel_data) if ci is not None else []

                if self._sel_data in (NETWORK_RESULT.NET_TOTAL_CO2, NETWORK_RESULT.NET_TOTAL_CO2_ACC):
                    compinfra = np.array(compinfra) / 1000.0

                comptime, compinfra = self.trimData(comptime, compinfra)
                if self._sel_data == NETWORK_RESULT.NET_TOTAL_CO2:
                    compinfra = self.low_pass_filter(compinfra)

                # 비교 곡선은 앞쪽 플롯 슬롯들(i) 사용
                if i < len(self._plots) - 1:
                    self._plots[i].setData(comptime, compinfra)
                self.setPlotYRange(compinfra)
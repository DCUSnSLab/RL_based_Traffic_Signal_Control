from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QPushButton, QVBoxLayout, QComboBox

from Infra import SECTION_RESULT, TOTAL_RESULT
from plotobject import PlotSection, PlotInfra, PLOTMODE, PlotObject


class GraphLayout(QGridLayout):
    def __init__(self):
        super().__init__()

        # QHBoxLayout 4개 생성하여 리스트에 추가
        self.hbox_list = [QVBoxLayout() for _ in range(4)]
        self.combo_boxes = []
        self.plotlist = {}
        self.initGraph()

    def initGraph(self):

        for i, hbox in enumerate(self.hbox_list):
            # 각 QHBoxLayout에 버튼 추가
            combo_box = QComboBox()
            combo_box.setFixedWidth(250)
            font = combo_box.font()
            font.setPointSize(13)
            font.setBold(True)

            # 콤보박스에 아이템 추가
            for plot in PLOTMODE:
                combo_box.addItem(plot.value[1])
            combo_box.setCurrentIndex(i)
            combo_box.currentIndexChanged.connect(lambda index, cb=combo_box, idx=i: self.update_layout(cb, idx))
            hbox.addWidget(combo_box)
            # 콤보박스 리스트에 추가
            self.combo_boxes.append(combo_box)
            self.plotlist[i] = None

        print(PLOTMODE)
        for i, plot in enumerate(PLOTMODE):
            p = plot.value[0]()
            self.plotlist[i] = p
            if i < 4:
                self.hbox_list[i].addWidget(p.getWidtget())

        # QHBoxLayout을 QGridLayout의 각 위치에 추가
        for i, hbox in enumerate(self.hbox_list):
            row = i // 2  # 행 계산
            col = i % 2  # 열 계산
            self.addLayout(hbox, row, col)

    def getPlotList(self):
        return self.plotlist

    def resetPlotCompAdded(self):
        for pl in self.plotlist.values():
            pl.resetCompAdded()

    def update_layout(self, combo_box, index):
        # combo_box의 인덱스를 기준으로 해당 레이아웃의 레이블을 업데이트
        selected_text = combo_box.currentText()

        hbox = self.hbox_list[index]
        plot: PlotObject = self.plotlist[index]
        hbox.removeWidget(plot.getWidtget())
        plot.getWidtget().deleteLater()
        #print(PLOTMODE.from_string(selected_text))
        self.plotlist[index] = PLOTMODE.from_string(selected_text).value[0]()
        hbox.addWidget(self.plotlist[index].getWidtget())

    def getPlotList(self):
        return self.plotlist
    def submitLayout(self, mainlayout):
        pass
        #.data_list[0].setText('test')
        # mainlayout.addLayout(state_layout)
        # mainlayout.addLayout(emission_layout)
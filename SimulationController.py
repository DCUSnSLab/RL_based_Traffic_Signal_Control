import os
import sys
from datetime import datetime
from time import sleep

from PyQt5.QtWidgets import *
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, pyqtSlot, Qt
import pyqtgraph as pg

from Infra import Direction, Infra, SECTION_RESULT, TOTAL_RESULT, Config_SUMO
from graphmanager import GraphLayout
from plotobject import PlotSection, PlotInfra
from runactuated import RunActuated
from RunSimulation import RunSimulation
from collections import deque
from PyQt5.QtGui import QFont
from scipy.signal import butter, filtfilt

from runemulator import RunEmulator
from signaltype import SignalMode

from typing import List, Tuple


class TrafficSimulatorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.DEBUG = False
        self.controller: RunSimulation = None  # 시뮬레이션 컨트롤러 초기화
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)  # 타이머가 update_data 메서드를 호출

        # signalControl Mode
        self.signalControlType = None
        self.compData: List[str] = list()
        self.comparedInfras: List[Infra] = None

        self.sectionColor = {}
        self.initSectionColor()

        self.plotlist = dict()

        # 그래프 업데이트 제어 플래그 (True이면 업데이트 중지)
        self.graph_paused = False

        self.initUI()

    def initSectionColor(self):
        colorset = ('r', 'g', 'b', 'c')
        for i, dr in enumerate(Direction):
            print(dr.value[0])
            self.sectionColor[dr.value[0]] = (dr.name, colorset[i])

    def initUI(self):
        self.setWindowTitle("Traffic Simulator Visualization")
        self.setGeometry(0, 0, 1280, 1000)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        select_layout = QVBoxLayout()
        combo1_layout = QVBoxLayout()
        combo2_layout = QVBoxLayout()
        menu1_layout = QHBoxLayout()
        menu2_layout = QHBoxLayout()
        top_layout = QHBoxLayout()

        state_layout = QHBoxLayout()
        signal_layout = QVBoxLayout()
        queue_layout = QVBoxLayout()
        state_layout.addLayout(signal_layout)
        state_layout.addLayout(queue_layout)
        emission_layout = QHBoxLayout()
        self.emit1 = QHBoxLayout()
        bottom_layout = QHBoxLayout()

        # --- 그래프 레이아웃을 QWidget에 감싸서 생성 (업데이트 제어를 위해) ---
        self.graphlayout = GraphLayout()  # QLayout 객체
        self.graph_widget = QWidget()  # 그래프용 컨테이너 위젯 생성
        self.graph_widget.setLayout(self.graphlayout)

        # 레이아웃 추가 순서
        main_layout.addLayout(select_layout)
        main_layout.addLayout(top_layout)

        # 그래프 업데이트 on/off 체크박스 추가 (그래프는 그대로 표시되며 업데이트만 멈춥니다)
        graph_option_layout = QHBoxLayout()
        self.chk_enable_graph = QCheckBox("Graph on/off", self)
        self.chk_enable_graph.setChecked(True)
        self.chk_enable_graph.stateChanged.connect(self.on_graph_option_changed)
        graph_option_layout.addWidget(self.chk_enable_graph)
        graph_option_layout.addStretch()  # 왼쪽 정렬
        main_layout.addLayout(graph_option_layout)

        # 그래프 위젯 추가 (컨테이너 위젯 사용)
        main_layout.addWidget(self.graph_widget)

        # (필요 시 아래 주석 처리된 레이아웃들을 추가)
        # main_layout.addLayout(state_layout)
        # main_layout.addLayout(emission_layout)
        main_layout.addLayout(bottom_layout)

        # --- Signal Plot ---
        ps = PlotSection('Section Signal Green Time', 'Time(s)', 'green time', SECTION_RESULT.GREEN_TIME)
        self.plotlist['greentime'] = ps
        signal_layout.addWidget(ps.getWidtget())

        # --- Queue Plot ---
        qs = PlotSection('Queue', 'Time(s)', 'Queue Length (Number of Vehicles)', SECTION_RESULT.TRAFFIC_QUEUE)
        self.plotlist['queue'] = qs
        queue_layout.addWidget(qs.getWidtget())

        # --- Total CO2 Emission Plot ---
        self.totalte = PlotInfra('Total CO2 Emissions', 'Time(s)', 'CO2 Emission(Ton)', TOTAL_RESULT.TOTAL_CO2,
                                 self.signalControlType)
        self.plotlist['totalco2'] = self.totalte
        self.emit1.addWidget(self.totalte.getWidtget())
        emission_layout.addLayout(self.emit1)

        # --- CO2 Emission by Bound Plot ---
        co2 = PlotSection('CO2 Emissions by Bound', 'Time(s)', 'CO2 Emission(kg)', SECTION_RESULT.SECTION_CO2,
                          ismoving=True)
        self.plotlist['co2bound'] = co2
        emission_layout.addWidget(co2.getWidtget())

        # --- Select Signal Type ---
        lb_sigtype = QLabel(self)
        font = lb_sigtype.font()
        font.setPointSize(13)
        font.setBold(True)
        lb_sigtype.setFont(font)
        lb_sigtype.setText("Select Signal Type: ")
        combo1_layout.addWidget(lb_sigtype)
        cb_sigtype = QComboBox(self)
        font = cb_sigtype.font()
        font.setPointSize(13)
        cb_sigtype.setFont(font)
        for sigmode in SignalMode:
            cb_sigtype.addItem(sigmode.value[1])
        cb_sigtype.activated[str].connect(self.onSigTypeActivated)
        cb_sigtype.setCurrentIndex(0)
        self.onSigTypeActivated(cb_sigtype.currentText())
        combo1_layout.addWidget(cb_sigtype)
        menu1_layout.addLayout(combo1_layout)

        # --- Select Compare Data ---
        lb_comp = QLabel(self)
        font = lb_comp.font()
        font.setPointSize(13)
        font.setBold(True)
        lb_comp.setFont(font)
        lb_comp.setText("  Select Comparing Data: ")
        combo2_layout.addWidget(lb_comp)
        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QListWidget.MultiSelection)  # 다중 선택 가능
        font = self.list_widget.font()
        font.setPointSize(12)
        self.list_widget.setFont(font)
        self.refreshComplist()
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        combo2_layout.addWidget(self.list_widget)
        menu1_layout.addLayout(combo2_layout)

        # --- Simulation Control Buttons ---
        start_button = QPushButton("Start Simulation")
        font = start_button.font()
        font.setPointSize(15)
        start_button.setFont(font)
        start_button.clicked.connect(self.start_simulation)
        menu2_layout.addWidget(start_button)

        stop_button = QPushButton("Stop Simulation")
        font = stop_button.font()
        font.setPointSize(15)
        stop_button.setFont(font)
        stop_button.clicked.connect(self.stop_simulation)
        menu2_layout.addWidget(stop_button)

        save_button = QPushButton("SaveData")
        font = save_button.font()
        font.setPointSize(15)
        save_button.setFont(font)
        save_button.clicked.connect(self.saveData_button_clicked)
        menu2_layout.addWidget(save_button)

        extract_button = QPushButton("Extract to Excel")
        font = extract_button.font()
        font.setPointSize(15)
        extract_button.setFont(font)
        extract_button.clicked.connect(self.extract_button_clicked)
        menu2_layout.addWidget(extract_button)

        select_layout.addLayout(menu1_layout)
        select_layout.addLayout(menu2_layout)

    def refreshComplist(self):
        # 저장된 파일 목록으로 리스트 위젯 갱신
        self.list_widget.clear()
        for orin, fn in self.getSavedFileList():
            item = QListWidgetItem(fn)
            item.setData(Qt.UserRole, orin)  # orin 값을 사용자 데이터로 저장
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.list_widget.addItem(item)

    def on_graph_option_changed(self, state):
        # 체크박스 상태에 따라 그래프 업데이트를 멈추거나 재개
        if state == Qt.Checked:
            self.graph_paused = False
        else:
            self.graph_paused = True

    def onSigTypeActivated(self, typestr):
        self.signalControlType = SignalMode.from_string(typestr)
        print('selected Signal Control Mode : ', self.signalControlType.value[1])

    def on_item_clicked(self, item):
        if item.checkState() == Qt.Checked:
            item.setCheckState(Qt.Unchecked)
        else:
            item.setCheckState(Qt.Checked)
        self.on_selection_changed()

    def on_selection_changed(self):
        self.compData.clear()
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item.checkState() == Qt.Checked:
                self.compData.append(item.data(Qt.UserRole))
        # print("Selected data:", self.compData)

    def initialize_controller(self, extract=False):
        print(self.signalControlType)
        if extract is not True:
            self.controller = self.signalControlType.value[0]()  # 예: RunActuated(config=Config_SUMO())
        else:
            self.controller = RunSimulation(config=Config_SUMO(), name="Extract Mode", isExtract=True)
        if self.compData is not None:
            emul = RunEmulator(self.compData)
            self.comparedInfras = emul.getInfras()
            self.graphlayout.resetPlotCompAdded()

    def start_simulation(self):
        self.initialize_controller()  # 컨트롤러 초기화
        self.simulation_thread = SimulationThread(self.controller)
        if self.DEBUG is not True:
            self.simulation_thread.results_signal.connect(self.update_graph)
        self.simulation_thread.start()
        self.timer.start(100)  # 100ms 간격으로 GUI 업데이트

    def stop_simulation(self):
        self.graphlayout.submitLayout(None)
        if self.controller:
            self.controller.terminate()
            self.timer.stop()

    def extract_savedData(self):
        if self.controller is None:
            self.initialize_controller(extract=True)
            self.controller.extract_excel(True)

    def extract_button_clicked(self):
        if self.controller:
            self.controller.extract_excel()

    def saveData_button_clicked(self):
        if self.controller:
            default_filename = 'FileName'
            dialog = QInputDialog(self)
            dialog.setWindowTitle('Save Data')
            dialog.setLabelText('Enter file name:')
            dialog.setTextValue(default_filename)
            dialog.resize(400, 200)
            font = QFont()
            font.setPointSize(13)
            dialog.setFont(font)
            if dialog.exec_() == QInputDialog.Accepted:
                filename = dialog.textValue()
                if filename:
                    self.controller.saveData(filename)
                    self.refreshComplist()

    def format_filename(self, filename: str) -> str:
        *base_parts, base_name, timestamp = filename.rsplit('_', 2)
        base_filename = '_'.join(base_parts)
        date_time_obj = datetime.strptime(timestamp, '%Y%m%d%H%M%S')
        formatted_time = date_time_obj.strftime('%Y.%m.%d %H:%M')
        return f"{base_filename} [{base_name} : {formatted_time}]"

    def getSavedFileList(self) -> List[Tuple[str, str]]:
        data_files = [f for f in os.listdir('.') if f.endswith('.data')]
        result = []
        for f in data_files:
            without_extension = os.path.splitext(f)[0]
            formatted_without_extension = self.format_filename(without_extension)
            result.append((f, formatted_without_extension))
        return result

    @pyqtSlot(object)
    def draw_bar_chart(self, rtinfra: Infra):
        self.bar_x = []
        self.bar_y = []
        labels = dict()
        try:
            sections = rtinfra.getSections().values()
            for i, section in enumerate(sections):
                self.bar_x.append(i + 1)
                self.bar_y.append(section.getCurrentQueue())
                labels[i + 1] = section.direction.name

            self.queue_graph.clear()
            bg = pg.BarGraphItem(x=self.bar_x, height=self.bar_y, width=0.6, brush='y', pen='y')
            self.queue_graph.addItem(bg)

            for i in range(len(self.bar_x)):
                text_item = pg.TextItem(text=labels[self.bar_x[i]], anchor=(0.5, 1.5))
                text_item.setColor('k')
                self.queue_graph.addItem(text_item)
                text_item.setPos(self.bar_x[i], 0)
                value_item = pg.TextItem(text=str(self.bar_y[i]), anchor=(0.5, -0.3))
                value_item.setColor('k')
                self.queue_graph.addItem(value_item)
                value_item.setPos(self.bar_x[i], self.bar_y[i])
        except IndexError:
            pass

    @pyqtSlot(object)
    def update_graph(self, rtinfra):
        # graph_paused가 True이면 그래프 업데이트를 중지
        if self.graph_paused:
            return

        for pl in self.graphlayout.getPlotList().values():
            pl.update(rtinfra, self.comparedInfras)

    def draw_filtered_graph(self, section_results, total_results, total_result_comp):
        cx = [result['Time'] for result in total_result_comp]
        cy = [result['Total_Emission'] for result in total_result_comp]
        filtered_comp_y = self.low_pass_filter(cy)
        self.comp_emission_curve.setData(cx, filtered_comp_y)

        self.x = [result['Time'] for result in total_results]
        self.y = [result['Total_Emission'] for result in total_results]
        filtered_y = self.low_pass_filter(self.y)
        self.emission_curve.setData(self.x, filtered_y)

        sections = {
            '0': ([], [], []),
            '1': ([], [], []),
            '2': ([], [], []),
            '3': ([], [], [])
        }

        for result in section_results:
            section = result['Section']
            if section in sections:
                sections[section][0].append(result['Time'])
                sections[section][1].append(result['Section_CO2_Emission'])
                sections[section][2].append(result['green_time'])

        filtered_sections = {}
        for key in sections:
            time_data = sections[key][0][-500:]
            co2_data = sections[key][1][-500:]
            filtered_sections[key] = (time_data, self.low_pass_filter(co2_data))

        self.Sb_emission_curve.setData(filtered_sections['0'][0], filtered_sections['0'][1])
        self.Nb_emission_curve.setData(filtered_sections['1'][0], filtered_sections['1'][1])
        self.Eb_emission_curve.setData(filtered_sections['2'][0], filtered_sections['2'][1])
        self.Wb_emission_curve.setData(filtered_sections['3'][0], filtered_sections['3'][1])

        if time_data:
            self.bound_emission_graph.plotItem.setXRange(max(time_data[-1] - 500, 0), time_data[-1])
            y_max = self.bound_emission_graph.plotItem.viewRange()[1][1]
            self.labels['SB'].setPos(max(time_data[-1] - 500, 0), y_max - 10)
            self.labels['NB'].setPos(max(time_data[-1] - 500, 0), y_max - 30)
            self.labels['EB'].setPos(max(time_data[-1] - 500, 0), y_max - 50)
            self.labels['WB'].setPos(max(time_data[-1] - 500, 0), y_max - 70)

    def update_data(self):
        if self.simulation_thread is not None:
            self.simulation_thread.emit_results()

    def closeEvent(self, event):
        if self.parent():
            self.parent().show()
        event.accept()


class SimulationThread(QThread):
    results_signal = pyqtSignal(object)

    def __init__(self, controller):
        super().__init__()
        self.controller: RunSimulation = controller

    def run(self):
        self.controller.run_simulation()

    def emit_results(self):
        self.results_signal.emit(
            self.controller.getInfra(),
        )


def my_exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)


def main():
    sys._excepthook = sys.excepthook
    sys.excepthook = my_exception_hook
    app = QApplication(sys.argv)
    window = TrafficSimulatorApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

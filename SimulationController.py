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
        self.controller: RunSimulation = None  # Initialize the controller to None initially
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)  # Connect the timer to update_data method

        #signalControl Mode
        self.signalControlType = None
        self.compData: List[str] = list()
        self.comparedInfras: List[Infra] = None

        self.sectionColor = {}
        self.initSectionColor()

        self.plotlist = dict()

        self.initUI()

    def initSectionColor(self):
        colorset = ('r','g','b','c')
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
        self.graphlayout = GraphLayout()
        main_layout.addLayout(select_layout)
        main_layout.addLayout(top_layout)
        main_layout.addLayout(self.graphlayout)
        # main_layout.addLayout(state_layout)
        # main_layout.addLayout(emission_layout)
        main_layout.addLayout(bottom_layout)


        #signal_layout.addWidget(sigplot)
        ps = PlotSection('Section Signal Green Time', 'Time(s)', 'green time', SECTION_RESULT.GREEN_TIME)
        self.plotlist['greentime'] = ps
        signal_layout.addWidget(ps.getWidtget())

        # signal_layout.addWidget(sigplot)

        qs = PlotSection('Queue', 'Time(s)', 'Queue Length (Number of Vehicles)', SECTION_RESULT.TRAFFIC_QUEUE)
        self.plotlist['queue'] = qs
        queue_layout.addWidget(qs.getWidtget())

        self.totalte = PlotInfra('Total CO2 Emissions', 'Time(s)', 'CO2 Emission(Ton)', TOTAL_RESULT.TOTAL_CO2, self.signalControlType)
        self.plotlist['totalco2'] = self.totalte
        self.emit1.addWidget(self.totalte.getWidtget())
        emission_layout.addLayout(self.emit1)

        co2 = PlotSection('CO2 Emissions by Bound', 'Time(s)', 'CO2 Emission(kg)', SECTION_RESULT.SECTION_CO2, ismoving=True)
        self.plotlist['co2bound'] = co2
        emission_layout.addWidget(co2.getWidtget())

        #Select Signal Type
        #label
        lb_sigtype = QLabel(self)
        font = lb_sigtype.font()
        font.setPointSize(13)
        font.setBold(True)
        lb_sigtype.setFont(font)
        lb_sigtype.setText("Select Signal Type: ")
        combo1_layout.addWidget(lb_sigtype)
        #Combobox
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

        #Select Compare Data
        lb_comp = QLabel(self)
        font = lb_comp.font()
        font.setPointSize(13)
        font.setBold(True)
        lb_comp.setFont(font)
        lb_comp.setText("  Select Comparing Data: ")
        combo2_layout.addWidget(lb_comp)
        # Combobox
        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QListWidget.MultiSelection)  # 다중 선택 가능
        font = self.list_widget.font()
        font.setPointSize(12)
        self.list_widget.setFont(font)
        #self.list_widget.setFixedWidth(500)
        #self.list_widget.setFixedHeight(100)

        self.refreshComplist()

        self.list_widget.itemClicked.connect(self.on_item_clicked)
        combo2_layout.addWidget(self.list_widget)

        # extract_savedData = QPushButton("Extract Saved Data")
        # font = extract_savedData.font()
        # font.setPointSize(15)
        # extract_savedData.setFont(font)
        # extract_savedData.clicked.connect(self.extract_savedData)
        # combo2_layout.addWidget(extract_savedData)
        # spacer = QSpacerItem(40, 30, QSizePolicy.Expanding, QSizePolicy.Minimum)
        # combo2_layout.addItem(spacer)
        menu1_layout.addLayout(combo2_layout)

        #s_button.clicked.connect(self.start_simulation)
        #bottom_layout.addWidget(s_button)
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

        # Create a Custom Button(extract)
        save_button = QPushButton("SaveData")
        font = save_button.font()
        font.setPointSize(15)
        save_button.setFont(font)
        save_button.clicked.connect(self.saveData_button_clicked)
        menu2_layout.addWidget(save_button)

        # Create a Custom Button(extract)
        extract_button = QPushButton("Extract to Excel")
        font = extract_button.font()
        font.setPointSize(15)
        extract_button.setFont(font)
        extract_button.clicked.connect(self.extract_button_clicked)
        menu2_layout.addWidget(extract_button)

        # # Create a Custom(show graph)
        # graph_button = QPushButton("Show Graph")
        # font = graph_button.font()
        # font.setPointSize(15)
        # graph_button.setFont(font)
        # menu2_layout.addWidget(graph_button)

        select_layout.addLayout(menu1_layout)
        select_layout.addLayout(menu2_layout)



    def refreshComplist(self):
        # 파일 리스트 항목 추가
        self.list_widget.clear()
        for orin, fn in self.getSavedFileList():
            item = QListWidgetItem(fn)
            item.setData(Qt.UserRole, orin)  # orin 값을 사용자 데이터로 저장
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.list_widget.addItem(item)

    def onSigTypeActivated(self, typestr):
        self.signalControlType = SignalMode.from_string(typestr)
        print('selected Signal Control Mode : ',self.signalControlType.value[1])

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
        #print("Selected data:", self.compData)

    def initialize_controller(self, extract=False):
        print(self.signalControlType)
        if extract is not True:
            self.controller = self.signalControlType.value[0]()#RunActuated(config=Config_SUMO())
        else:
            self.controller = RunSimulation(config=Config_SUMO(), name="Extract Mode", isExtract=True)
        if self.compData is not None:
            emul = RunEmulator(self.compData)
            self.comparedInfras = emul.getInfras()
            self.graphlayout.resetPlotCompAdded()


    def start_simulation(self):
        self.initialize_controller()  # Initialize the controller if it hasn't been initialized
        self.simulation_thread = SimulationThread(self.controller)
        if self.DEBUG is not True:
            self.simulation_thread.results_signal.connect(self.update_graph)
        self.simulation_thread.start()
        self.timer.start(100)  # Start the timer to update the GUI every second

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

            # 다이얼로그 크기 조정
            dialog.resize(400, 200)
            # 폰트 설정
            font = QFont()
            font.setPointSize(13)
            dialog.setFont(font)

            if dialog.exec_() == QInputDialog.Accepted:
                filename = dialog.textValue()
                if filename:  # 사용자가 파일 이름을 입력하고 확인을 눌렀을 때
                    self.controller.saveData(filename)
                    self.refreshComplist()

    def format_filename(self, filename: str) -> str:
        *base_parts, base_name, timestamp = filename.rsplit('_', 2)
        base_filename = '_'.join(base_parts)  # 나머지 부분을 다시 합침
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
        #print('length of sections : ', len(section_results), type(section_results))
        labels = dict()

        try:
            sections = rtinfra.getSections().values()
            for i, section in enumerate(sections):
                self.bar_x.append(i+1)
                self.bar_y.append(section.getCurrentQueue())
                labels[i+1] = section.direction.name

            self.queue_graph.clear()
            bg = pg.BarGraphItem(x=self.bar_x, height=self.bar_y, width=0.6, brush='y', pen='y')
            self.queue_graph.addItem(bg)


            for i in range(len(self.bar_x)):
                # 이름 출력
                text_item = pg.TextItem(text=labels[self.bar_x[i]], anchor=(0.5, 1.5))
                text_item.setColor('k')
                self.queue_graph.addItem(text_item)
                text_item.setPos(self.bar_x[i], 0)  # x 좌표는 막대의 x 위치, y 좌표는 막대의 아래쪽

                # 값 출력
                value_item = pg.TextItem(text=str(self.bar_y[i]), anchor=(0.5, -0.3))
                value_item.setColor('k')
                self.queue_graph.addItem(value_item)
                value_item.setPos(self.bar_x[i], self.bar_y[i])  # x 좌표는 막대의 x 위치, y 좌표는 막대의 높이 위치
        except IndexError:
            pass

    @pyqtSlot(object)
    def update_graph(self, rtinfra):
        #self.draw_filtered_graph(rtinfra, total_results, total_result_comp)

        for pl in self.graphlayout.getPlotList().values():
            pl.update(rtinfra, self.comparedInfras)


    def draw_filtered_graph(self, section_results, total_results, total_result_comp):
        # comp Total Emission Graph
        cx = [result['Time'] for result in total_result_comp]
        cy = [result['Total_Emission'] for result in total_result_comp]

        # 필터 적용
        filtered_comp_y = self.low_pass_filter(cy)
        self.comp_emission_curve.setData(cx, filtered_comp_y)

        # Total Emission Graph
        self.x = [result['Time'] for result in total_results]
        self.y = [result['Total_Emission'] for result in total_results]

        # 필터 적용
        filtered_y = self.low_pass_filter(self.y)
        self.emission_curve.setData(self.x, filtered_y)

        # # Total Volume
        # total_x = [result['Time'] for result in total_results]
        # total_y = [result['Total_Volume'] for result in total_results]
        #
        # # 필터 적용
        # self.total_volume_curve.setData(total_x, total_y)

        # Section Emission Graph 데이터 준비
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

        # 각 섹션에서 마지막 500개의 데이터만 선택
        filtered_sections = {}
        for key in sections:
            time_data = sections[key][0][-500:]  # 마지막 500개의 Time 데이터
            co2_data = sections[key][1][-500:]  # 마지막 500개의 CO2 데이터

            filtered_sections[key] = (time_data, self.low_pass_filter(co2_data))

        # 필터링된 데이터를 그래프에 설정
        self.Sb_emission_curve.setData(filtered_sections['0'][0], filtered_sections['0'][1])
        self.Nb_emission_curve.setData(filtered_sections['1'][0], filtered_sections['1'][1])
        self.Eb_emission_curve.setData(filtered_sections['2'][0], filtered_sections['2'][1])
        self.Wb_emission_curve.setData(filtered_sections['3'][0], filtered_sections['3'][1])

        # X축 범위를 실시간으로 최신 데이터에 맞게 조정 (마지막 time 값 기준)
        if time_data:
            # X축을 마지막 time 값 기준으로 500 단위로 설정
            self.bound_emission_graph.plotItem.setXRange(max(time_data[-1] - 500, 0), time_data[-1])

            # Y축 최대값 가져오기
            y_max = self.bound_emission_graph.plotItem.viewRange()[1][1]

            # 라벨의 위치를 최신 X축과 Y축 범위에 맞춰 갱신
            self.labels['SB'].setPos(max(time_data[-1] - 500, 0), y_max - 10)
            self.labels['NB'].setPos(max(time_data[-1] - 500, 0), y_max - 30)
            self.labels['EB'].setPos(max(time_data[-1] - 500, 0), y_max - 50)
            self.labels['WB'].setPos(max(time_data[-1] - 500, 0), y_max - 70)

        # for i, sig in enumerate(self.signalgreenplot):
        #     sig.setData(sections[str(i)][0], sections[str(i)][2])

    def update_data(self):
        # Periodically update the data from the simulation
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
    # Print the error and traceback
    print(exctype, value, traceback)
    # Call the normal Exception hook after
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
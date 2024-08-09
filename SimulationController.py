import sys
import traci
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, pyqtSlot
import pyqtgraph as pg
import RunSimulation
from collections import deque
from PyQt5.QtGui import QFont
from scipy.signal import butter, filtfilt

class TrafficSimulatorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.DEBUG = False
        self.controller = None  # Initialize the controller to None initially
        self.initUI()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)  # Connect the timer to update_data method

    def initUI(self):
        self.setWindowTitle("Traffic Simulator Visualization")
        self.setGeometry(100, 100, 1920, 1080)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        select_layout = QVBoxLayout()
        top_layout = QHBoxLayout()
        state_layout = QHBoxLayout()
        emission_layout = QHBoxLayout()
        bottom_layout = QHBoxLayout()

        if self.DEBUG is not True:
            # Traffic Lights
            self.traffic_sign = pg.PlotWidget(title="Traffic Sign (temp)")
            self.traffic_sign.setBackground('w')
            state_layout.addWidget(self.traffic_sign)

            # Queue graph
            self.queue_graph = pg.PlotWidget(title="Queue")
            self.queue_graph.plotItem.setLabels(bottom='Bound', left="Queue Length")
            self.queue_graph.plotItem.getAxis('bottom').setPen(pg.mkPen(color='#000000', width=3))
            self.queue_graph.plotItem.getAxis('left').setPen(pg.mkPen(color='#000000', width=3))
            self.queue_graph.setBackground('w')
            self.queue_graph.setYRange(0, 100)

            state_layout.addWidget(self.queue_graph)

            # Emissions graph
            self.emission_graph = pg.PlotWidget(title="Total Emissions")
            self.emission_graph.plotItem.setLabels(bottom='Time(s)', left="Emission(kg)")
            self.emission_graph.plotItem.getAxis('bottom').setPen(pg.mkPen(color='#000000', width=3))
            self.emission_graph.plotItem.getAxis('left').setPen(pg.mkPen(color='#000000', width=3))
            self.emission_graph.setBackground('w')
            self.emission_graph.setStyleSheet("border: 1px solid black; padding-left:10px; padding-right:10px; background-color: white;")
            self.emission_curve = self.emission_graph.plot(pen="g")
            emission_layout.addWidget(self.emission_graph)

            # Emission graph by bound
            self.bound_emission_graph = pg.PlotWidget(title="Emissions by Bound")
            self.bound_emission_graph.plotItem.setLabels(bottom='Time(s)', left="Emission(kg)")
            self.bound_emission_graph.plotItem.getAxis('bottom').setPen(pg.mkPen(color='#000000', width=3))
            self.bound_emission_graph.plotItem.getAxis('left').setPen(pg.mkPen(color='#000000', width=3))
            self.bound_emission_graph.setBackground('w')
            self.bound_emission_graph.addLegend()
            self.bound_emission_graph.setStyleSheet("border: 1px solid black; padding-left:10px; padding-right:10px; background-color: white;")
            self.Sb_emission_curve = self.bound_emission_graph.plot(pen="r")
            self.Nb_emission_curve = self.bound_emission_graph.plot(pen="b")
            self.Eb_emission_curve = self.bound_emission_graph.plot(pen="g")
            self.Wb_emission_curve = self.bound_emission_graph.plot(pen="c")

            # Y축 범위 설정
            self.bound_emission_graph.plotItem.setYRange(0, 300)

            # ViewBox 좌표계를 사용하여 라벨을 고정된 위치에 추가
            vb = self.bound_emission_graph.getPlotItem().getViewBox()

            self.labels = {
                'SB': pg.TextItem(text='── SB (Red)', color='r'),
                'NB': pg.TextItem(text='── NB (Blue)', color='b'),
                'EB': pg.TextItem(text='── EB (Green)', color='g'),
                'WB': pg.TextItem(text='── WB (Cyan)', color='c')
            }
            # 각 라벨의 초기 설정 (한 번만 실행)
            for key, label in self.labels.items():
                label.setFont(QFont("Arial", 12))
                self.bound_emission_graph.addItem(label)

            # 위젯을 레이아웃에 추가
            emission_layout.addWidget(self.bound_emission_graph)

        start_button = QPushButton("Start Simulation")
        font = start_button.font()
        font.setPointSize(15)
        start_button.setFont(font)
        start_button.clicked.connect(self.start_simulation)
        bottom_layout.addWidget(start_button)

        stop_button = QPushButton("Stop Simulation")
        font = stop_button.font()
        font.setPointSize(15)
        stop_button.setFont(font)
        stop_button.clicked.connect(self.stop_simulation)
        bottom_layout.addWidget(stop_button)

        # Create a Custom Button(extract)
        extract_button = QPushButton("Extract")
        font = extract_button.font()
        font.setPointSize(15)
        extract_button.setFont(font)
        extract_button.clicked.connect(self.extract_button_clicked)
        bottom_layout.addWidget(extract_button)

        # Create a Custom(show graph)
        graph_button = QPushButton("Show Graph")
        font = graph_button.font()
        font.setPointSize(15)
        graph_button.setFont(font)
        bottom_layout.addWidget(graph_button)

        main_layout.addLayout(select_layout)
        main_layout.addLayout(top_layout)
        main_layout.addLayout(state_layout)
        main_layout.addLayout(emission_layout)
        main_layout.addLayout(bottom_layout)

    def initialize_controller(self):
        self.controller = RunSimulation.SumoController(config=RunSimulation.Config_SUMO())

    def start_simulation(self):
        if self.controller is None:
            self.initialize_controller()  # Initialize the controller if it hasn't been initialized
        self.simulation_thread = SimulationThread(self.controller)
        if self.DEBUG is not True:
            self.simulation_thread.results_signal.connect(self.draw_bar_chart)
            self.simulation_thread.results_signal.connect(self.update_co2_graph)
        self.simulation_thread.start()
        self.timer.start(100)  # Start the timer to update the GUI every second

    def stop_simulation(self):
        if self.controller:
            traci.close()
            self.timer.stop()

    def extract_button_clicked(self):
        if self.controller:
            self.controller.extract_excel()

    @pyqtSlot(object)
    def draw_bar_chart(self, section_results):
        self.bar_x = []
        self.bar_y = []
        #print('length of sections : ', len(section_results), type(section_results))
        labels = dict()

        try:
            section_results = deque(section_results, maxlen=4)
            for result in section_results:
                #print('Sid : ', result['Section'], ', Queue : ', result['Section_Queue'])
                if result['Section'] == '0':
                    self.bar_x.append(1)
                    self.bar_y.append(result['Section_Queue'])
                    labels[1] = result['sectionBound']
                elif result['Section'] == '1':
                    self.bar_x.append(2)
                    self.bar_y.append(result['Section_Queue'])
                    labels[2] = result['sectionBound']
                elif result['Section'] == '2':
                    self.bar_x.append(3)
                    self.bar_y.append(result['Section_Queue'])
                    labels[3] = result['sectionBound']
                elif result['Section'] == '3':
                    self.bar_x.append(4)
                    self.bar_y.append(result['Section_Queue'])
                    labels[4] = result['sectionBound']
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

    @pyqtSlot(object, object)
    def update_co2_graph(self, section_results, total_results):
        self.draw_filtered_graph(section_results, total_results)

    def low_pass_filter(self, data, cutoff=0.3, fs=1.0, order=1):
        if len(data) <= 9:  # 필터의 padlen보다 작은 경우
            return data  # 필터링을 건너뛰고 원래 데이터를 반환
        nyq = 0.5 * fs  # Nyquist Frequency
        normal_cutoff = cutoff / nyq
        b, a = butter(order, normal_cutoff, btype='low', analog=False)
        y = filtfilt(b, a, data, padlen=3)  # padlen 값을 줄여서 설정
        return y

    def draw_filtered_graph(self, section_results, total_results):
        # Total Emission Graph
        self.x = [result['Time'] for result in total_results]
        self.y = [result['Total_Emission'] for result in total_results]

        # 필터 적용
        filtered_y = self.low_pass_filter(self.y)
        self.emission_curve.setData(self.x, filtered_y)

        # Section Emission Graph 데이터 준비
        sections = {
            '0': ([], []),
            '1': ([], []),
            '2': ([], []),
            '3': ([], [])
        }

        for result in section_results:
            section = result['Section']
            if section in sections:
                sections[section][0].append(result['Time'])
                sections[section][1].append(result['Section_CO2_Emission'])

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

    def update_data(self):
        # Periodically update the data from the simulation
        if self.simulation_thread is not None:
            self.simulation_thread.emit_results()

    def closeEvent(self, event):
        if self.parent():
            self.parent().show()
        event.accept()

class SimulationThread(QThread):
    results_signal = pyqtSignal(object,object)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller

    def run(self):
        self.controller.run_simulation()

    def emit_results(self):
        self.results_signal.emit(
            self.controller.section_results,
            self.controller.total_results
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

import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, pyqtSlot

import pyqtgraph as pg

import RunSimulation

class TrafficSimulatorApp(QMainWindow):
    def __init__(self):
        super().__init__()
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

        # Traffic Lights
        # self.traffic_sign = QLabel(self)
        # pixmap = QGraphicsPixmapItem("")
        self.traffic_sign = pg.PlotWidget(title="Traffic Sign(temp)")
        # self.queue_graph.plotItem.setLabels(bottom='Time(s)', left="Count")
        # self.queue_graph.plotItem.getAxis('bottom').setPen(pg.mkPen(color='#000000', width=3))
        # self.queue_graph.plotItem.getAxis('left').setPen(pg.mkPen(color='#000000', width=3))
        self.traffic_sign.setBackground('w')
        state_layout.addWidget(self.traffic_sign)

        # Queue graph
        self.queue_graph = pg.PlotWidget(title="Queue")
        # self.queue_graph.plotItem.setLabels(bottom='Time(s)', left="Count")
        # self.queue_graph.plotItem.getAxis('bottom').setPen(pg.mkPen(color='#000000', width=3))
        # self.queue_graph.plotItem.getAxis('left').setPen(pg.mkPen(color='#000000', width=3))
        self.queue_graph.setBackground('w')
        state_layout.addWidget(self.queue_graph)

        # Emissions graph
        self.emission_graph = pg.PlotWidget(title="Total Emissions")
        self.emission_graph.plotItem.setLabels(bottom='Time(s)', left="Emission(g)")
        self.emission_graph.plotItem.getAxis('bottom').setPen(pg.mkPen(color='#000000', width=3))
        self.emission_graph.plotItem.getAxis('left').setPen(pg.mkPen(color='#000000', width=3))
        self.emission_graph.setBackground('w')
        self.emission_graph.setStyleSheet("border: 1px solid black; padding-left:10px; padding-right:10px; background-color: white;")

        # pen = pg.mkPen(color=(0, 255, 0), width=5, style=QtCore.Qt.SolidLine)
        self.CO2_curve = self.emission_graph.plot(pen="g")
        emission_layout.addWidget(self.emission_graph)

        # Emission graph by bound
        self.bound_emission_graph = pg.PlotWidget(title="Emissions by Bound")
        self.bound_emission_graph.plotItem.setLabels(bottom='Time(s)', left="Emission(g)")
        self.bound_emission_graph.plotItem.getAxis('bottom').setPen(pg.mkPen(color='#000000', width=3))
        self.bound_emission_graph.plotItem.getAxis('left').setPen(pg.mkPen(color='#000000', width=3))
        self.bound_emission_graph.setBackground('w')
        self.bound_emission_graph.setStyleSheet("border: 1px solid black; padding-left:10px; padding-right:10px; background-color: white;")

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
        # graph_button.clicked.connect(self.get_data)
        bottom_layout.addWidget(graph_button)

        main_layout.addLayout(select_layout)
        main_layout.addLayout(top_layout)
        main_layout.addLayout(state_layout)
        main_layout.addLayout(emission_layout)
        main_layout.addLayout(bottom_layout)

    def initialize_controller(self):
        self.controller = RunSimulation.SumoController(config=RunSimulation.Config_SUMO)

    def start_simulation(self):
        if self.controller is None:
            self.initialize_controller()  # Initialize the controller if it hasn't been initialized
        self.simulation_thread = SimulationThread(self.controller)
        self.simulation_thread.results_signal.connect(self.update_co2_graph)
        self.simulation_thread.start()
        self.timer.start(1000)  # Start the timer to update the GUI every second

    def stop_simulation(self):
        self.controller.traci.stop()

    def extract_button_clicked(self):
        self.simulation_thread.bt_extract_excel()

    def custom_button3_clicked(self):
        pass

    def show_graph(self):
        self.graph_window = GraphWindow()

    @pyqtSlot(list, list, list, list)
    def update_co2_graph(self, detectors, detection_result_flow_merge, detection_result_co2_merge,
                         detection_result_co2_flow_merge):
        self.x = []
        self.y = []
        for row_idx, row_data in enumerate(detection_result_co2_merge):
            CO2_value = 0
            for col_idx, value in enumerate(row_data):
                if col_idx == 0:
                    self.x.append(int(value))
                else:
                    CO2_value += int(value)
            CO2_value = CO2_value/1000
            self.y.append(CO2_value)
            self.CO2_curve.setData(self.x, self.y)
    def update_data(self):
        # Periodically update the data from the simulation
        if self.simulation_thread is not None:
            self.simulation_thread.emit_results()

    def closeEvent(self, event):
        if self.parent():
            self.parent().show()
        event.accept()

class SimulationThread(QThread):
    results_signal = pyqtSignal(list, list, list, list)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller

    def run(self):
        self.controller.run_simulation()

    def emit_results(self):
        self.results_signal.emit(
            self.controller.detectors,
            self.controller.detection_result_flow_merge,
            self.controller.detection_result_co2_merge,
            self.controller.detection_result_co2_flow_merge
        )
    def bt_extract_excel(self):
        self.controller.extract_excel()

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

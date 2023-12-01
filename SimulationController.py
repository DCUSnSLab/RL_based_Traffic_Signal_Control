import sys
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QThread, pyqtSignal, QTimer

import SimulationController

from ShowGraph import GraphWindow

class TrafficSimulatorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = None  # Initialize the controller to None initially
        self.initUI()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)  # Connect the timer to update_data method

    def initUI(self):
        self.setWindowTitle("Traffic Simulator Visualization")
        self.setGeometry(100, 100, 1350, 800)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        select_layout = QVBoxLayout()
        top_layout = QHBoxLayout()

        # Create a Custom Button 2
        select_button = QPushButton("Select File")
        font = select_button.font()
        font.setPointSize(15)
        select_button.setFont(font)
        select_button.clicked.connect(self.select_button_clicked)
        select_layout.addWidget(select_button)

        start_button = QPushButton("Start Simulation")
        font = start_button.font()
        font.setPointSize(15)
        start_button.setFont(font)
        start_button.clicked.connect(self.start_simulation)
        top_layout.addWidget(start_button)

        stop_button = QPushButton("Stop Simulation")
        font = stop_button.font()
        font.setPointSize(15)
        stop_button.setFont(font)
        stop_button.clicked.connect(self.stop_simulation)
        top_layout.addWidget(stop_button)

        self.result_table = QTableWidget()
        font = self.result_table.font()
        font.setPointSize(12)
        self.result_table.setFont(font)
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.setColumnCount(13)
        self.result_table.setHorizontalHeaderLabels(["Time", "sb_1", "sb_2", "sb_3", "eb_1", "eb_2", "eb_3", "nb_1", "nb_2", "nb_3", "wb_1", "wb_2", "wb_3"])
        top_layout.addWidget(self.result_table)

        bottom_layout = QHBoxLayout()

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
        graph_button.clicked.connect(self.show_graph)
        bottom_layout.addWidget(graph_button)

        main_layout.addLayout(select_layout)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.result_table)
        main_layout.addLayout(bottom_layout)

    def initialize_controller(self):
        self.controller = SimulationController.SumoController(config=SimulationController.Config_SUMO)

    def select_button_clicked(self):
        fname = QFileDialog.getOpenFileName(self, 'Select File', r'C:\Users\kwon\Desktop\dataset', 'Config File(*.sumocfg)')
        pass

    def start_simulation(self):
        if self.controller is None:
            self.initialize_controller()  # Initialize the controller if it hasn't been initialized
        self.simulation_thread = SimulationThread(self.controller)
        self.simulation_thread.results_signal.connect(self.add_result_to_table)
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

    def add_result_to_table(self, detectors, detection_result_flow_merge, detection_result_co2_merge, detection_result_co2_flow_merge):
        # Use the values in your GUI, for example, populate the table
        self.result_table.setRowCount(len(detection_result_co2_flow_merge))  # Set the number of rows
        for row_idx, row_data in enumerate(detection_result_co2_flow_merge):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                self.result_table.setItem(row_idx, col_idx, item)

        self.should_scroll = False  # Disable scrolling

        QTimer.singleShot(1000, self.enable_scroll)  # Re-enable scrolling after 1 second

    def enable_scroll(self):
        self.should_scroll = True
        # Scroll to the bottom of the table
        v_scrollbar = self.result_table.verticalScrollBar()
        v_scrollbar.setValue(v_scrollbar.maximum())


    def update_data(self):
        # Periodically update the data from the simulation
        if self.simulation_thread is not None:
            self.simulation_thread.emit_results()

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
    if 'SUMO_HOME' in os.environ:
        tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
        sys.path.append(tools)
    else:
        sys.exit("please declare environment variable 'SUMO_HOME'")
    main()

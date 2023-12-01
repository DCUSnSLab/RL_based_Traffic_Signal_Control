import pandas as pd
from PyQt5.QtWidgets import *
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class GraphWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)

        canvas = FigureCanvas(Figure(figsize=(4, 3)))
        vbox = QVBoxLayout(self.main_widget)
        vbox.addWidget(canvas)

        # Navigation Tool Bar
        # self.addToolBar(NavigationToolbar(canvas, self))

        df = pd.read_excel("detection_results_4.xlsx", sheet_name="Flow")

        columns_to_plot = df.columns[df.columns != 'Time']

        self.ax = canvas.figure.subplots()
        for column in columns_to_plot:
            self.ax.plot(df['Time'], df[column], label=column)
        self.ax.set_title('Simulation Flow')
        self.ax.set_xlabel('Time')
        self.ax.set_ylabel('Flow')
        self.ax.legend()

        self.setWindowTitle('Show Graph')
        self.setGeometry(300, 100, 600, 400)
        self.show()
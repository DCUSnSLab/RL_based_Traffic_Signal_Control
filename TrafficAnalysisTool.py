import sys

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import *


class AnalysisTools(QTabWidget):

    def __init__(self):
        super().__init__()

        self.tab1 = QWidget()
        self.tab2 = QWidget()
        self.tab3 = QWidget()

        self.addTab(self.tab1, "Tab 1")
        self.addTab(self.tab2, "Tab 2")
        self.addTab(self.tab3, "Tab 3")
        self.tab1UI()
        self.tab2UI()
        self.tab3UI()
        self.setWindowTitle('Integrated Analysis Tools')
        self.setGeometry(300, 300, 1000, 800)

    def tab1UI(self):
        grid = QGridLayout()
        grid.addWidget(self.SelectDataGroup(), 0, 0, 4, 5)
        grid.addWidget(self.RunSimulationGroup(), 4, 0, 2, 5)
        grid.addWidget(self.TrafficDataGroup(), 0, 5, 1, 4)
        grid.addWidget(self.EvalMeasurementsGroup(), 1, 5, 3, 4)
        grid.addWidget(self.EmissionMeasurementsGroup(), 4, 5, 2, 4)
        grid.addWidget(self.ExtractResults(), 6, 0, 2, 9)
        self.setTabText(0, "Tools")
        self.tab1.setLayout(grid)

    def SelectDataGroup(self):
        groupbox = QGroupBox('Select Data')
        font = groupbox.font()
        font.setPointSize(11)
        groupbox.setFont(font)

        label1 = QLabel('Route')
        route_box = QComboBox()

        cal = QCalendarWidget(self)
        cal.setGridVisible(True)
        # cal.clicked[QDate].connect(self.showDate)
        #
        # self.lbl = QLabel(self)
        # date = cal.selectedDate()
        # self.lbl.setText(date.toString())

        grid = QGridLayout()
        grid.addWidget(label1, 0, 0)
        grid.addWidget(route_box, 1, 0)
        grid.addWidget(cal, 2, 0)

        grid.setRowStretch(grid.rowCount(), 1)
        groupbox.setLayout(grid)

        return groupbox

    # def showDate(self, date):
    #     self.lbl.setText(date.toString())

    def RunSimulationGroup(self):
        groupbox = QGroupBox('Run Simulation')
        font = groupbox.font()
        font.setPointSize(11)
        groupbox.setFont(font)

        label1 = QLabel('Select Algorithm')
        label_algorithm = QLabel('None')
        label_algorithm.setStyleSheet('border-style: solid; border-width: 1px;')
        # cmb1 = QComboBox()
        btn_add = QPushButton(self)
        btn_add.setText('Add')
        btn_del = QPushButton(self)
        btn_del.setText('Del')
        blank = QLabel('')

        label2 = QLabel('Select Simulator')
        cmb2 = QComboBox()
        cmb2.addItem('SUMO')
        btn_run = QPushButton(self)
        btn_run.setText('Run')
        # checkbox1 = QCheckBox('Extract Data from Simulation Results')
        result_group = QGroupBox('Extract Data from Simulation Results')
        result_group.setCheckable(True)
        result_group.setChecked(False)
        label1 = QLabel('Output Folder')
        # label_folder = QLineEdit(self)
        # label_folder.setStyleSheet('border-style: solid; border-width: 1px;')
        sel_button = QPushButton('Find')
        label2 = QLabel('Option')



        grid = QGridLayout()

        grid.addWidget(label1, 0, 0)
        grid.addWidget(label_algorithm, 1, 0, 1, 3)
        grid.addWidget(btn_add, 1, 3, 1, 1)
        grid.addWidget(btn_del, 1, 4, 1, 1)
        grid.addWidget(blank, 2, 0)
        grid.addWidget(label2, 3, 0)
        grid.addWidget(cmb2, 4, 0, 1, 4)
        grid.addWidget(btn_run, 4, 4, 1, 1)
        # grid.addWidget(checkbox1, 5, 0)
        grid.addWidget(result_group, 5, 0)

        grid.setRowStretch(grid.rowCount(), 1)
        # grid.setColumnStretch(grid.columnCount(), 1)

        groupbox.setLayout(grid)

        return groupbox

    def onActivated(self, text):
        self.lbl.setText(text)
        self.lbl.adjustSize()

    def TrafficDataGroup(self):
        groupbox = QGroupBox('Traffic Data')
        font = groupbox.font()
        font.setPointSize(11)
        groupbox.setFont(font)


        checkbox1 = QCheckBox('Spped')
        checkbox2 = QCheckBox('Density')
        checkbox3 = QCheckBox('Total Flow')
        checkbox4 = QCheckBox('Avg. Lane Flow')
        checkbox5 = QCheckBox('Acceleration')


        grid = QGridLayout()
        grid.addWidget(checkbox1, 0, 0)
        grid.addWidget(checkbox2, 0, 1)
        grid.addWidget(checkbox3, 0, 2)
        grid.addWidget(checkbox4, 1, 0)
        grid.addWidget(checkbox5, 1, 1)
        groupbox.setLayout(grid)

        return groupbox

    def EvalMeasurementsGroup(self):
        groupbox = QGroupBox('Evaluation Measurements')
        font = groupbox.font()
        font.setPointSize(11)
        groupbox.setFont(font)

        checkbox1 = QCheckBox('VKT(Vehicle Kilometers Traveled)')
        checkbox2 = QCheckBox('LVKT(Lost VKT for Congestion)')
        checkbox3 = QCheckBox('TT(Time Travel)')
        checkbox4 = QCheckBox('DVH(Delayed Vehicle Hours)')
        checkbox5 = QCheckBox('VHT(Vehicle Hour Traveled)')
        checkbox6 = QCheckBox('MRFR(Mainlane and Ramp Flow Rates)')
        checkbox7 = QCheckBox('SV(Speed Variation)')
        checkbox8 = QCheckBox('CK(Congested Kilometers)')

        vbox = QVBoxLayout()
        vbox.addWidget(checkbox1)
        vbox.addWidget(checkbox2)
        vbox.addWidget(checkbox3)
        vbox.addWidget(checkbox4)
        vbox.addWidget(checkbox5)
        vbox.addWidget(checkbox6)
        vbox.addWidget(checkbox7)
        vbox.addWidget(checkbox8)
        groupbox.setLayout(vbox)

        return groupbox

    def EmissionMeasurementsGroup(self):
        groupbox = QGroupBox('Evaluation Measurements')
        font = groupbox.font()
        font.setPointSize(11)
        groupbox.setFont(font)

        checkbox1 = QCheckBox('PMx (Particulate Matter)')
        checkbox2 = QCheckBox('CO2 (Carbon Dioxide)')
        checkbox3 = QCheckBox('CO (Carbon monoxide)')
        checkbox4 = QCheckBox('HC (Hydrocarbon')
        checkbox5 = QCheckBox('NOx (Nitrogen oxides)')

        vbox = QVBoxLayout()
        vbox.addWidget(checkbox1)
        vbox.addWidget(checkbox2)
        vbox.addWidget(checkbox3)
        vbox.addWidget(checkbox4)
        vbox.addWidget(checkbox5)
        groupbox.setLayout(vbox)

        return groupbox

    def ExtractResults(self):
        groupbox = QGroupBox('Extract Analysis Results')
        font = groupbox.font()
        font.setPointSize(11)
        groupbox.setFont(font)

        label = QLabel("Output Format")
        check_excel = QCheckBox('Excel')
        check_csv = QCheckBox('CSV')
        blank = QLabel('')
        label1 = QLabel('Output Folder')
        label_folder = QLineEdit(self)
        # label_folder.setStyleSheet('border-style: solid; border-width: 1px;')
        sel_button = QPushButton('Find')
        label2 = QLabel('Option')
        extract_button = QPushButton('Extrcation')
        extract_button.setMaximumHeight(80)


        grid = QGridLayout()
        grid.addWidget(label, 0, 0, 1, 5)
        grid.addWidget(check_excel, 1, 0)
        grid.addWidget(check_csv, 1, 1)
        grid.addWidget(blank, 2, 0, 1, 5)
        grid.addWidget(label1, 3, 0, 1, 5)
        grid.addWidget(label_folder, 4, 0, 1, 4)
        grid.addWidget(sel_button, 4, 4, 1, 1)

        grid.addWidget(label2, 0, 5, 1, 3)

        grid.addWidget(extract_button, 3, 8, 2, 1)

        # grid.setRowStretch(grid.rowCount(), 1)
        groupbox.setLayout(grid)

        return groupbox

    def tab2UI(self):
        grid2 = QGridLayout()
        grid2.addWidget(self.TrafficLightsCycle(), 0, 0, 4, 5)
        self.setTabText(1, "Generate")
        self.tab2.setLayout(grid2)

    def TrafficLightsCycle(self):
        groupbox = QGroupBox('Traffic Lights Cycle')
        font = groupbox.font()
        font.setPointSize(11)
        groupbox.setFont(font)

        label = QLabel("test")


        grid = QGridLayout()
        grid.addWidget(label, 0, 0, 1, 1)
        groupbox.setLayout(grid)

        return groupbox

    def tab3UI(self):
        layout = QHBoxLayout()
        self.setTabText(2, "Tab3")
        self.tab3.setLayout(layout)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = AnalysisTools()
    ex.show()
    sys.exit(app.exec_())
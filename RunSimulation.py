import os

import traci
import pandas as pd

class Config_SUMO:
    sumocfg_path = r'input your sumocfg path'
    scenario_path = r'input your scenario path'
    scenario_file = "input your scenario file"

    sumoBinary = r'C:/Program Files (x86)/Eclipse/Sumo/bin/sumo-gui'

# Detector
class Detector:
    def __init__(self, id):
        self.id = id
        self.vehicle_list = []
        self.vehicle_interval_list = []
        self.vehicle_total_count = 0
        self.vehicle_interval_count = 0
        self.vehicle_total_co2 = 0
        self.vehicle_interval_co2 = 0
        self.tmp = 0

    def update(self):
        if traci.inductionloop.getLastStepVehicleIDs(self.id) in self.vehicle_list:
            pass
        else:
            self.vehicle_interval_list += traci.inductionloop.getLastStepVehicleIDs(self.id)
            self.vehicle_interval_count = len(list(set(self.vehicle_interval_list)))
            for v_id in self.vehicle_interval_list:
                self.vehicle_interval_co2 += traci.vehicle.getCO2Emission(v_id)
                self.vehicle_total_co2 += traci.vehicle.getCO2Emission(v_id)

    def interval_reset(self):
        self.vehicle_list += self.vehicle_interval_list
        self.vehicle_interval_list = []
        self.vehicle_total_count = len(list(set(self.vehicle_list)))
        self.vehicle_interval_co2 = 0

def merge_data(list):
    # Create a DataFrame from the detection results
    df = pd.DataFrame(list)

    # Fill in missing values
    df.fillna(0)

    #  Combine rows with the same value in the time column
    merge_df = df.groupby('Time').agg('sum').reset_index()

    list_result = merge_df.values.tolist()

    return list_result

class SumoController:
    def __init__(self,config):
        self.config = config
        self.__set_SUMO()
        self.detectors = [Detector(detector_id) for detector_id in self.__get_detector_ids(self.config)]
        self.detection_result_flow = []
        self.detection_result_co2 = []
        self.detection_result_co2_flow = []
        self.detection_result_flow_merge = []
        self.detection_result_co2_merge = []
        self.detection_result_co2_flow_merge = []
        self.detection_co2=[]
        pass

    def __get_detector_ids(self, config):
        detector_ids = []
        with open(os.path.join(config.scenario_path, config.scenario_file), "r") as f:
            for line in f:
                if "inductionLoop" in line:
                    parts = line.split('"')
                    detector_ids.append(parts[1])
        return detector_ids

    def __set_SUMO(self):
        traci.start(["sumo-gui", "-c", self.config.sumocfg_path, "--start"])
        traci.simulationStep()

    def extract_excel(self):
        # Create a DataFrame from the detection results
        df1 = pd.DataFrame(self.detection_result_flow)
        df2 = pd.DataFrame(self.detection_result_co2)
        df3 = pd.DataFrame(self.detection_result_co2_flow)

        # Fill in missing values
        df1.fillna(0)
        df2.fillna(0)
        df3.fillna(0)

        #  Combine rows with the same value in the time column
        merge_df1 = df1.groupby('Time').agg('sum').reset_index()
        merge_df2 = df2.groupby('Time').agg('sum').reset_index()
        merge_df3 = df3.groupby('Time').agg('sum').reset_index()

        excel_writer = pd.ExcelWriter("results_new.xlsx", engine="xlsxwriter")

        merge_df1.to_excel(excel_writer, sheet_name="Flow", index=False)
        merge_df2.to_excel(excel_writer, sheet_name="CO2", index=False)
        merge_df3.to_excel(excel_writer, sheet_name="CO2_Flow", index=False)
        excel_writer.close()

    def run_simulation(self):
        step = 0
        while step <= 360:
            traci.simulationStep()
            for detector in self.detectors:
                detector.update()

            if (step % 30) == 0:
                # print("Current simulation time:", traci.simulation.getTime())
                for detector in self.detectors:
                    self.detection_result_flow.append({"Time": traci.simulation.getTime(), detector.id: int(f"{detector.vehicle_interval_count}")})
                    self.detection_result_co2.append({"Time": traci.simulation.getTime(), detector.id: float(f"{detector.vehicle_interval_co2:.2f}")})
                    self.detection_result_co2_flow.append({"Time": traci.simulation.getTime(), detector.id : f"{detector.vehicle_interval_co2:.2f}/{detector.vehicle_interval_count}"})
                    detector.interval_reset()

                self.detection_result_flow_merge = merge_data(self.detection_result_flow)
                self.detection_result_co2_merge = merge_data(self.detection_result_co2)
                self.detection_result_co2_flow_merge = merge_data(self.detection_result_co2_flow)
            step += 1

        traci.close()
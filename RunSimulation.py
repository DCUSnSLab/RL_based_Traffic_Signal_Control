import os
import traci
import pandas as pd
from collections import defaultdict

class Config_SUMO:
    # SUMO Configuration File
    sumocfg_path = "New_TestWay/test_cfg.sumocfg"
    # SUMO Scenario File Path
    scenario_path = "New_TestWay"
    # SUMO Scenario File(.add.xml)
    scenario_file = "New_detector.add.xml"

    sumoBinary = r'C:/Program Files (x86)/Eclipse/Sumo/bin/sumo-gui'

# Detector
class Detector:
    def __init__(self, id):
        self.id = id
        self.aux, self.bound, self.station_id, self.detector_id = self.parse_detector_id(id)
        self.minInterval = 30
        self.speed = 0
        self.volume = 0
        self.data = []

    def parse_detector_id(self, id):
        parts = id.split('_')
        if len(parts) != 2 or not parts[0].startswith("Det"):
            raise ValueError(f"Invalid detector ID format: {id}")
        det_info = parts[1][3:]
        aux = det_info[0]
        bound = det_info[1]
        station_id = det_info[1:6]
        detector_id = det_info[6:]
        return aux, bound, station_id, detector_id

    def get_data(self):
        vehicles = traci.inductionloop.getLastStepVehicleIDs(self.id)
        self.volume = traci.inductionloop.getLastStepVehicleNumber(self.id)
        self.speed = traci.inductionloop.getLastStepMeanSpeed(self.id)
        co2_emission = sum(traci.vehicle.getCO2Emission(vehicle) for vehicle in vehicles) / 1000
        self.data.append({
            'Time': traci.simulation.getTime(),
            'speed': self.speed,
            'volume': self.volume,
            'co2_emission': co2_emission
        })
        return co2_emission, self.volume

class Station:
    def __init__(self, id, detectors):
        self.id = id
        self.dets = detectors

    # def add_detector(self, detector):
    #     self.dets.append(detector)

    def collect_co2_emission(self):
        total_co2_emission = 0
        total_volume = 0
        for det in self.dets:
            co2_emission, volume = det.get_data()
            total_co2_emission += co2_emission
            total_volume += volume
        return total_co2_emission, total_volume

class Section:
    def __init__(self, id, stations):
        self.id = id
        self.stations = stations

    def add_station(self, station):
        self.stations.append(station)

    def collect_data(self):
        section_co2_emission = 0
        section_volume = 0
        for station in self.stations:
            co2_emission, volume = station.collect_co2_emission()
            section_co2_emission += co2_emission
            section_volume += volume
        return section_co2_emission, section_volume

class SumoController:
    def __init__(self, config):
        self.config = config
        self.__set_SUMO()
        self.detectors = [Detector(detector_id) for detector_id in self.__get_detector_ids(self.config)]
        self.stations = {}
        self.sections = {}
        self.section_results = []
        self.total_results = []

        for detector in self.detectors:
            if detector.station_id not in self.stations:
                self.stations[detector.station_id] = []
            self.stations[detector.station_id].append(detector)

        self.station_objects = {station_id: Station(station_id, detectors) for station_id, detectors in self.stations.items()}

        for station_id in self.stations:
            section_id = station_id[0]
            if section_id not in self.sections:
                self.sections[section_id] = []
            self.sections[section_id].append(self.station_objects[station_id])

        self.section_objects = {section_id : Section(section_id, stations) for section_id, stations in self.sections.items()}

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
        df = pd.DataFrame(self.section_results)
        df.to_excel("results_new.xlsx", index=False)

    def run_simulation(self):
        step = 0
        while step <= 360:
            traci.simulationStep()
            self.collect_data()
            # if step % 30 == 0:
            #     self.collect_data()
            step += 1
        traci.close()
        self.extract_excel()

    def Check_TrafficLight_State(self):
        try:
            signal_states = traci.trafficlight.getRedYellowGreenState("TLS_0")
        except traci.exceptions.TraCIException:
            signal_states = 'N/A'

    def collect_data(self):
        time = traci.simulation.getTime()
        total_emission = 0
        total_volume = 0
        for section_id, section in self.section_objects.items():
            section_co2_emission, section_volume = section.collect_data()
            total_emission += section_co2_emission
            total_volume += section_volume
            self.section_results.append({
                'Time': time,
                'Section': section_id,
                'Section_CO2_Emission': section_co2_emission,
                'Section_Volume': section_volume
            })
        self.total_results.append({
            'Time': time,
            'Total_Emission': total_emission,
            'Total_Volume': total_volume
        })
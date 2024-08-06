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
        self.vehicles = set()
        self.input_vehicles = set()
        self.out_vehicles = set()

    def parse_detector_id(self, id):
        parts = id.split('_')
        if len(parts) != 2 or not parts[0].startswith("Det"):
            raise ValueError(f"Invalid detector ID format: {id}")
        det_info = parts[1]
        aux = det_info[0]
        bound = det_info[1]
        station_id = det_info[0:6]
        detector_id = det_info[6:]
        return aux, bound, station_id, detector_id

    def get_data(self):
        vehicle_ids = traci.inductionloop.getLastStepVehicleIDs(self.id)
        if self.aux == "1":
            self.out_vehicles.update(vehicle_ids)
        elif self.station_id[4:] == "00":
            self.input_vehicles.update(vehicle_ids)
        else:
            self.vehicles.update(vehicle_ids)
        return list(self.out_vehicles), list(self.input_vehicles), list(self.vehicles)

    def IntervalReset(self):
        self.input_vehicles = set()
        self.out_vehicles = set()
        self.vehicles = set()

    def update(self):
        self.get_data()

class Station:
    def __init__(self, id, detectors):
        self.id = id
        self.dets = detectors

    def get_station_data(self):
        station_inputs = set()
        station_outputs = set()
        station_vehicles = set()
        for det in self.dets:
            out_vehicles, input_vehicles, vehicles = det.get_data()
            station_inputs.update(input_vehicles)
            station_outputs.update(out_vehicles)
            station_vehicles.update(vehicles)
        return list(station_inputs), list(station_outputs), list(station_vehicles)

    def IntervalReset(self):
        for det in self.dets:
            det.IntervalReset()

    def update(self):
        for det in self.dets:
            det.update()

class Section:
    def __init__(self, id, stations):
        self.id = id
        self.stations = stations
        self.section_co2_emission = 0
        self.section_volume = 0
        self.section_queue = 0
        self.section_vehicles = set()
        self.stop_x, self.stop_y = self.StopLane_position()

    def collect_data(self):
        self.section_co2_emission = 0
        self.section_volume = 0
        self.section_queue = 0
        self.section_vehicles = set()
        for station in self.stations:
            input, output, vehicles = station.get_station_data()
            self.section_vehicles.update(vehicles)
            if station.id[4:] == "00":
                self.section_volume = len(input)
            elif station.id[0] == "1":
                for vehicle in output:
                    if vehicle in self.section_vehicles:
                        self.section_vehicles.remove(vehicle)
                    else:
                        pass
        self.section_queue = len(self.section_vehicles)
        for vehicle in self.section_vehicles:
            if traci.vehicle.getCO2Emission(vehicle) < 0:
                pass
            else:
                self.section_co2_emission += traci.vehicle.getCO2Emission(vehicle) / 1000
        return self.section_co2_emission, self.section_volume, self.section_queue, list(self.section_vehicles)

    def IntervalReset(self):
        self.section_co2_emission = 0
        self.section_volume = 0
        self.section_queue = 0
        self.section_vehicles = set()
        for station in self.stations:
            station.IntervalReset()

    def update(self):
        for station in self.stations:
            station.update()
        self.collect_data()

class SumoController:
    def __init__(self, config):
        self.config = config
        self.__set_SUMO()
        self.detectors = [Detector(detector_id) for detector_id in self.__get_detector_ids(self.config)]
        self.stations = {}
        self.sections = {}
        self.section_results = []
        self.total_results = []
        self.traffic_light_id = "TLS_0"
        self.fixed_cycle = [
            {"state": "rrrrrrrrrrrgggg", "duration": 30},  # Eb : Green Lights
            {"state": "rrrrrrrrrrryyyy", "duration": 5},   # Eb : Yellow Lights
            {"state": "rrrrggggrrrrrrr", "duration": 33},  # Wb : Green Lights
            {"state": "rrrryyyyrrrrrrr", "duration": 5},   # Wb : Yellow Lights
            {"state": "ggggrrrrrrrrrrr", "duration": 89},  # Sb : Green Lights
            {"state": "yyyyrrrrrrrrrrr", "duration": 5},   # Sb : Yellow Lights
            {"state": "rrrrrrrrgggrrrr", "duration": 28},  # Nb : Green Lights
            {"state": "rrrrrrrryyyrrrr", "duration": 5}    # Nb : Yellow Lights
        ]
        # self.fixed_cycle = [
        #     {"state": "rrrrrrrrrrrgggg", "duration": 35},  # Eb : Green Lights
        #     {"state": "rrrrrrrrrrryyyy", "duration": 5},  # Eb : Yellow Lights
        #     {"state": "rrrrggggrrrrrrr", "duration": 33},  # Wb : Green Lights
        #     {"state": "rrrryyyyrrrrrrr", "duration": 5},  # Wb : Yellow Lights
        #     {"state": "ggggrrrrrrrrrrr", "duration": 27},  # Sb : Green Lights
        #     {"state": "yyyyrrrrrrrrrrr", "duration": 5},  # Sb : Yellow Lights
        #     {"state": "rrrrrrrrgggrrrr", "duration": 55},  # Nb : Green Lights
        #     {"state": "rrrrrrrryyyrrrr", "duration": 5}  # Nb : Yellow Lights
        # ]
        self.total_co2_emission = 0

        for detector in self.detectors:
            if detector.station_id not in self.stations:
                self.stations[detector.station_id] = []
            self.stations[detector.station_id].append(detector)

        self.station_objects = {station_id: Station(station_id, detectors) for station_id, detectors in self.stations.items()}

        for station_id in self.stations:
            section_id = station_id[1]
            if section_id not in self.sections:
                self.sections[section_id] = []
            self.sections[section_id].append(self.station_objects[station_id])

        self.section_objects = {section_id: Section(section_id, stations) for section_id, stations in self.sections.items()}

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

        co2_emission_df = df.pivot(index='Time', columns='Section', values='Section_CO2_Emission')
        volume_df = df.pivot(index='Time', columns='Section', values='Section_Volume')
        queue_df = df.pivot(index='Time', columns='Section', values='Section_Queue')

        with pd.ExcelWriter('section_results.xlsx') as writer:
            co2_emission_df.to_excel(writer, sheet_name='Section_CO2_Emission')
            volume_df.to_excel(writer, sheet_name='Section_Volume')
            queue_df.to_excel(writer, sheet_name='Section_Queue')

        print("Maked Excel")

    def set_fixed_cycle(self, traffic_light_id, step, fixed_cycle):
        total_duration = sum([phase["duration"] for phase in fixed_cycle])
        current_time_in_cycle = step % total_duration

        elapsed_time = 0
        for phase in fixed_cycle:
            if elapsed_time + phase["duration"] > current_time_in_cycle:
                traci.trafficlight.setRedYellowGreenState(traffic_light_id, phase["state"])
                break
            elapsed_time += phase["duration"]

    def run_simulation(self):
        step = 0
        while step <= 11700:
            traci.simulationStep()
            self.set_fixed_cycle(self.traffic_light_id, step, self.fixed_cycle)
            for section_id, section in self.section_objects.items():
                section.update()
            self.check_total_co2(step)
            if step % 30 == 0:
                self.collect_data()
            step += 1
        traci.close()

    def Check_TrafficLight_State(self):
        try:
            signal_states = traci.trafficlight.getRedYellowGreenState("TLS_0")
        except traci.exceptions.TraCIException:
            signal_states = 'N/A'

    def collect_data(self):
        time = traci.simulation.getTime()
        for section_id, section in self.section_objects.items():
            section_co2_emission, section_volume, section_queue, section_vehicles = section.collect_data()
            section_vehicles.sort()
            self.section_results.append({
                'Time': time,
                'Section': section_id,
                'Section_CO2_Emission': section_co2_emission,
                'Section_Volume': section_volume,
                'Section_Queue': section_queue,
                'Section_Vehicles': section_vehicles
            })
            section.IntervalReset()

    def check_total_co2(self, step):
        time = traci.simulation.getTime()
        vehicle_ids = traci.vehicle.getIDList()
        for vehicle_id in vehicle_ids:
            self.total_co2_emission += traci.vehicle.getCO2Emission(vehicle_id)
        if step % 30 == 0:
            self.total_results.append({
                'Time': time,
                'Total_Emission': self.total_co2_emission
            })
            self.total_co2_emission = 0
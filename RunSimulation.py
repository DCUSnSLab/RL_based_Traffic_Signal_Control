import os
import traci
import pandas as pd
import math
from collections import defaultdict

class Config_SUMO:
    # SUMO Configuration File
    sumocfg_path = "New_TestWay/test_cfg.sumocfg"
    # SUMO Scenario File Path
    scenario_path = "New_TestWay"
    # SUMO Scenario File(.add.xml)
    scenario_file = "new_test.add.xml"

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

    # def get_data(self):
    #     vehicle_ids = traci.inductionloop.getLastStepVehicleIDs(self.id)
    #     self.volume = traci.inductionloop.getLastStepVehicleNumber(self.id)
    #     if self.aux == "1":
    #         self.del_vehicle(vehicle_ids)
    #     else:
    #         self.vehicles.update(vehicle_ids)
    #     co2_emission = sum(traci.vehicle.getCO2Emission(vehicle) for vehicle in vehicle_ids) / 1000
    #     return co2_emission, self.volume, list(self.vehicles)

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
        self.stop_lane = self.StopLane_position()

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
        # self.section_co2_emission += sum(traci.vehicle.getCO2Emission(vehicle) for vehicle in self.section_vehicles) / 1000
        for vehicle in self.section_vehicles:
            if traci.vehicle.getCO2Emission(vehicle) < 0:
                pass
            else:
                self.section_co2_emission += traci.vehicle.getCO2Emission(vehicle) / 1000
        # if self.section_co2_emission < 0:
        #     print(self.section_vehicles)
        #     for vehicle in self.section_vehicles:
        #         if traci.vehicle.getCO2Emission(vehicle)<0:
        #             print(vehicle)
        #             print(traci.vehicle.getCO2Emission(vehicle))
        #         else:
        #             pass
        return self.section_co2_emission, self.section_volume, self.section_queue, list(self.section_vehicles)

    def check_DilemmaZone(self, time, traffic_light_bound, MinGreenTime, MaxGreenTime):
        if traffic_light_bound == self.id:
            for vehicle in self.section_vehicles:
                vehicle_distance_list = []
                vehicle_position = traci.vehicle.getPosition(vehicle)
                vehicle_x, vehicle_y = vehicle_position
                # vehicle_distance = math.sqrt((self.stop_x - vehicle_x) ** 2 + (self.stop_y - vehicle_y) ** 2)
                for i in range(0, len(self.stop_lane),2):
                    stop_lane_x, stop_lane_y = self.stop_lane[i:i+2]
                    distance = math.sqrt((stop_lane_x - vehicle_x) ** 2 + (stop_lane_y - vehicle_y) ** 2)
                    vehicle_distance_list.append(distance)
                vehicle_distance = min(vehicle_distance_list)
                vehicle_speed = traci.vehicle.getSpeed(vehicle)
                vehicle_type = traci.vehicle.getTypeID(vehicle)
                check_value = self.DilemmaZoneControl(time, vehicle_speed, vehicle_distance, vehicle_type, MinGreenTime, MaxGreenTime)
                if check_value == True:
                    return True
                else:
                    return False
        else:
            pass

    def StopLane_position(self):
        # print(type(self.id))
        stop_lane = ()
        last_station = self.stations[-1]
        for stop_detector in last_station.dets:
            lane_id = traci.inductionloop.getLaneID(stop_detector.id)
            lane_shape = traci.lane.getShape(lane_id)
            stop_lane_position = lane_shape[-1]
            # stop_x, stop_y = stop_lane_position
            stop_lane += stop_lane_position
        return stop_lane

    def DilemmaZoneControl(self, time, s, d, car_type, MinGreenTime, MaxGreenTime):
        s = s*3.6
        if time >= MinGreenTime:
            if time < MaxGreenTime:
                if car_type == "passenger":
                    T1 = s / 14
                    D1 = s * T1
                    if D1 < d:
                        # signal extension
                        return True
                    else:
                        return False
                else:
                    T2 = s / 9
                    D2 = s * T2
                    if D2 < d:
                        # signal extension
                        return True
                    else:
                        return False
            else:
                return False

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
        self.total_co2_emission = 0
        self.__get_station()
        self.station_objects = {station_id: Station(station_id, detectors) for station_id, detectors in self.stations.items()}
        self.__get_section()
        self.section_objects = {section_id: Section(section_id, stations) for section_id, stations in self.sections.items()}
        self.original_phase_durations={}

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

    def __get_station(self):
        for detector in self.detectors:
            if detector.station_id not in self.stations:
                self.stations[detector.station_id] = []
            self.stations[detector.station_id].append(detector)

    def __get_section(self):
        for station_id in self.stations:
            section_id = station_id[1]
            if section_id not in self.sections:
                self.sections[section_id] = []
            self.sections[section_id].append(self.station_objects[station_id])


    def extract_excel(self):
        df = pd.DataFrame(self.section_results)

        co2_emission_df = df.pivot(index='Time', columns='Section', values='Section_CO2_Emission')
        volume_df = df.pivot(index='Time', columns='Section', values='Section_Volume')
        queue_df = df.pivot(index='Time', columns='Section', values='Section_Queue')
        # vehicle_df = df.pivot(index='Time', columns='Section', values='Section_Vehicles')

        with pd.ExcelWriter('section_results.xlsx') as writer:
            co2_emission_df.to_excel(writer, sheet_name='Section_CO2_Emission')
            volume_df.to_excel(writer, sheet_name='Section_Volume')
            queue_df.to_excel(writer, sheet_name='Section_Queue')
            # vehicle_df.to_excel(writer, sheet_name='Section_Vehicles')

        print("Maked Excel")

    def run_simulation(self):
        MinGreenTime = 0
        count=0
        step = 0
        # current_phase_index = traci.trafficlight.getPhase("TLS_0")
        # logic = traci.trafficlight.getAllProgramLogics("TLS_0")[0]
        # current_phase = logic.phases[current_phase_index]

        while step <= 11700:
            traci.simulationStep()

            current_phase_index = traci.trafficlight.getPhase("TLS_0")
            logic = traci.trafficlight.getAllProgramLogics("TLS_0")[0]
            current_phase = logic.phases[current_phase_index]

            tls = self.Check_TrafficLight_State()
            # print(tls)
            if tls == "rrrrrrrrrrrgggg":
                bound = "2"
                MinGreenTime = current_phase.minDur
            elif tls == "rrrrggggrrrrrrr":
                bound = "3"
                MinGreenTime = current_phase.minDur
            elif tls == "ggggrrrrrrrrrrr":
                bound = "0"
                MinGreenTime = current_phase.minDur
            elif tls == "rrrrrrrrgggrrrr":
                bound = "1"
                MinGreenTime = current_phase.minDur
            else:
                bound = "yellow"
                count = 0

            if bound == "yellow":
                pass
            else:
                MaxGreenTime = MinGreenTime + 10
                time = traci.trafficlight.getPhaseDuration("TLS_0")
                for section_id, section in self.section_objects.items():
                    section.update()
                    check_control = section.check_DilemmaZone(time, bound, MinGreenTime, MaxGreenTime)
                    if check_control == True:
                        new_duration = current_phase.duration+1
                        remaining_time = traci.trafficlight.getNextSwitch("TLS_0")
                        traci.trafficlight.setPhaseDuration("TLS_0", new_duration)
                        count+=1
                        print("step", step)
                        print("time", time)
                        print("remaining_time", remaining_time)
                        print("duration +", count)
                    else:
                        pass

            self.check_total_co2(step)

            # check traffic state(interval)
            if step % 30 == 0:
                self.collect_data()
            step += 1

        traci.close()

    def Check_TrafficLight_State(self):
        try:
            signal_states = traci.trafficlight.getRedYellowGreenState("TLS_0")
        except traci.exceptions.TraCIException:
            signal_states = 'N/A'
        return signal_states

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
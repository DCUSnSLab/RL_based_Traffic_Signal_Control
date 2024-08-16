import os
import traci
import pandas as pd
from collections import deque
from Infra import SDetector, SStation, SSection
from Actuated_TLC import traffic_signal_control

class Config_SUMO:
    # SUMO Configuration File
    sumocfg_path = "New_TestWay/test_cfg.sumocfg"
    # SUMO Scenario File Path
    scenario_path = "New_TestWay"
    # SUMO Scenario File(.add.xml)
    scenario_file = "new_test.add.xml"

    sumoBinary = r'C:/Program Files (x86)/Eclipse/Sumo/bin/sumo-gui'

class Direction(Enum):
    SB = 0
    NB = 1
    EB = 2
    WB = 3

class InputStation(Enum):
    SB = '000000'
    NB = '010021'
    EB = '020018'
    WB = '030017'

def get_input_station_value(direction: Direction) -> str:
    # Direction의 name으로 InputStation을 찾아서 value를 반환
    return InputStation[direction.name].value

# Detector
class Detector:
    def __init__(self, id):
        self.id = id
        self.aux, self.bound, self.station_id, self.detector_id = self.parse_detector_id(id)
        self.minInterval = 30
        self.speed = 0
        self.volume = 0
        self.prevVehicles = tuple()
    def parse_detector_id(self, id):
        parts = id.split('_')
        if len(parts) != 2 or not parts[0].startswith("Det"):
            raise ValueError(f"Invalid detector ID format: {id}")
        det_info = parts[1]
        aux = det_info[0]
        bound = Direction(int(det_info[1]))
        station_id = det_info[0:6]
        detector_id = det_info[6:]
        return aux, bound, station_id, detector_id

    #update detection data by interval
    def update(self):
        vehicle_ids = traci.inductionloop.getLastStepVehicleIDs(self.id)
        #check duplicated vehicles
        dupvol = 0
        if self.prevVehicles is not None:
            for veh in vehicle_ids:
                if veh in self.prevVehicles:
                    dupvol += 1

        self.prevVehicles = vehicle_ids

        self.volume = traci.inductionloop.getLastStepVehicleNumber(self.id) - dupvol
        # if self.id == 'Det_02000000' or self.id == 'Det_02000001' or self.id == 'Det_12002604':
        #     print("%s -> v : %d" % (self.id, self.volume))
            #print('--- lsvid : ', vehicle_ids, type(vehicle_ids))

    def getVolume(self):
        return self.volume

    def getVehicles(self):
        return self.prevVehicles

class Station:
    def __init__(self, id, detectors):
        self.id = id
        self.dets = detectors
        self.direction = None if len(self.dets) == 0 else self.dets[0].bound
        self.volume = 0
        self.exitVolume = 0
        self.inputVeh = set()
        self.exitVeh = set()


    def update(self):
        self.volume = 0
        self.exitVolume = 0
        self.inputVeh = set()
        self.exitVeh = set()

        for det in self.dets:
            det.update()

            if det.aux == '1':
                self.exitVolume += det.getVolume()
                self.exitVeh.update(det.getVehicles())
            else:
                self.volume += det.getVolume()
                self.inputVeh.update(det.getVehicles())

        self.volume = self.volume if self.volume == 0 or self.volume < len(self.inputVeh) else len(self.inputVeh)
        self.exitVolume = self.exitVolume if self.exitVolume == 0 or self.exitVolume < len(self.exitVeh) else len(self.exitVeh)

        # if self.id == '020000' or self.id == '120026':
        #     print('station id',self.id,', volume: ',self.getVolume())
            #print('station id : ', self.id, 'iv: ',self.inputVeh, 'ev: ', self.exitVeh)

    def getVolume(self):
        return self.volume

    def getExitVolume(self):
        return self.exitVolume

    def getVehicleData(self):
        return list(self.inputVeh), list(self.exitVeh)

    def getInputVehIds(self):
        return self.inputVeh

    def getExitVehIds(self):
        return self.exitVeh

class Section:
    def __init__(self, id, stations):
        self.id = id
        self.stations = stations
        self.direction = None if len(self.stations) == 0 else self.stations[0].direction
        self.section_co2_emission = 0
        self.section_volume = 0
        self.traffic_queue = 0
        self.section_vehicles = set()
        self.stop_lane = self.StopLane_position()
        self.in_dilemmaZone=set()


    def check_DilemmaZone(self, time, traffic_light_bound, MinGreenTime, MaxGreenTime):
        if traffic_light_bound == self.id:
            DilemmaZone_results = []
            for vehicle in self.section_vehicles:
                vehicle_position = traci.vehicle.getPosition(vehicle)
                vehicle_x, vehicle_y = vehicle_position
                for i in range(0, len(self.stop_lane),2):
                    stop_lane_x, stop_lane_y = self.stop_lane[i:i+2]
                    distance = math.sqrt((stop_lane_x - vehicle_x) ** 2 + (stop_lane_y - vehicle_y) ** 2)
                    if distance <= 120:
                        vehicle_speed = traci.vehicle.getSpeed(vehicle)
                        vehicle_type = traci.vehicle.getTypeID(vehicle)
                        check_value = self.DilemmaZoneControlSignal(time, vehicle_speed, distance, vehicle_type, MinGreenTime, MaxGreenTime)
                        DilemmaZone_results.append(check_value)
                    else:
                        pass
            if "pass" in DilemmaZone_results:
                return "pass"
            elif "pass" not in DilemmaZone_results and "yellow" in DilemmaZone_results:
                return "yellow"
            else:
                return "none"
        else:
            check_value = "none"
            return check_value

    def StopLane_position(self):
        stop_lane = ()
        last_station = self.stations[-1]
        for stop_detector in last_station.dets:
            lane_id = traci.inductionloop.getLaneID(stop_detector.id)
            lane_shape = traci.lane.getShape(lane_id)
            stop_lane_position = lane_shape[-1]
            stop_lane += stop_lane_position
        return stop_lane

    def DilemmaZoneControlSignal(self, time, s, d, car_type, MinGreenTime, MaxGreenTime):
        check = "none"
        s = s*3.6
        if time >= MinGreenTime:
            # if time < MaxGreenTime:
            if MaxGreenTime <= 5:
                if car_type == "passenger":
                    T1 = s / 14
                    D1 = s * T1
                    if D1 < d:
                        check="yellow"
                        return check
                    else:
                        # signal extension
                        print(s, d, car_type, D1)
                        check = "pass"
                        return check
                else:
                    T2 = s / 9
                    D2 = s * T2
                    if D2 < d:
                        check = "yellow"
                        return check
                    else:
                        # signal extension
                        print(s, d, car_type, D2)
                        check = "pass"
                        return check
            else:
                check="yellow"
                return check
        else:
            return check

    def collect_data(self):
        return self.section_co2_emission, self.section_volume, self.traffic_queue, list(self.section_vehicles)

    def update(self):
        self.section_co2_emission = 0
        self.section_volume = 0
        removal_veh = list()
        for i, station in enumerate(self.stations):
            station.update()
            if i == 0:
                self.section_volume += station.getVolume()
            #update input station data according to InputStation Setup
            if station.id == get_input_station_value(self.direction):
                self.traffic_queue += station.getVolume()
                self.section_vehicles.update(station.getInputVehIds())

            self.traffic_queue -= station.getExitVolume()
            self.section_vehicles.difference_update(station.getExitVehIds())

        for vehicle in self.section_vehicles:
            try:
                if traci.vehicle.getCO2Emission(vehicle) >= 0:
                    self.section_co2_emission += traci.vehicle.getCO2Emission(vehicle) / 1000
            except TraCIException:
                removal_veh.append(vehicle)

        self.section_vehicles.difference_update(removal_veh)

class SumoController:
    def __init__(self, config):
        self.config = config
        self.__set_SUMO()
        self.detectors = [SDetector(detector_id) for detector_id in self.__get_detector_ids(self.config)]
        self.stations = {}
        self.sections = {}
        self.section_results = deque()
        self.total_results = deque()
        self.traffic_light_id = "TLS_0"
        self.total_co2_emission = 0
        self.total_volume = 0
        self.__init_station()
        self.station_objects = {station_id: SStation(station_id, detectors) for station_id, detectors in self.stations.items()}
        self.__get_section()
        self.section_objects = {section_id: SSection(section_id, stations) for section_id, stations in self.sections.items()}
        self.original_phase_durations={}
        self.stepbySec = 1
        self.colDuration = 30 #seconds
        self.cycle_time = 200
        self.total_yellow_time = 20

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

    def __init_station(self):
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
        queue_df = df.pivot(index='Time', columns='Section', values='traffic_queue')

        with pd.ExcelWriter('section_results.xlsx') as writer:
            co2_emission_df.to_excel(writer, sheet_name='Section_CO2_Emission')
            volume_df.to_excel(writer, sheet_name='Section_Volume')
            queue_df.to_excel(writer, sheet_name='traffic_queue')

        print("Maked Excel")

    def run_simulation(self):
        MinGreenTime = 0
        extended_time = 0
        step = 0

        while step <= 11700:
            #start_time = time.time()
            traci.simulationStep()

            current_phase_index = traci.trafficlight.getPhase("TLS_0")
            logic = traci.trafficlight.getAllProgramLogics("TLS_0")[0]
            num_phases = len(logic.phases)
            next_phase_index = (current_phase_index + 1) % num_phases
            current_phase = logic.phases[current_phase_index]

            current_simulation_time = traci.simulation.getTime()
            current_phase_duration = traci.trafficlight.getPhaseDuration("TLS_0")
            next_switch_time = traci.trafficlight.getNextSwitch("TLS_0")
            elapsed_time = current_simulation_time - (next_switch_time - current_phase_duration)

            remaining_time = next_switch_time - current_simulation_time

            if current_phase_index == num_phases-1 and remaining_time == 0:
                print(step)
                traffic_signal_control(self.section_objects, self.cycle_time, self.total_yellow_time)
                # green_times, surplus_rates, waiting_times = traffic_signal_control(self.section_objects, self.cycle_time, self.total_yellow_time)
                # print(f"Simulation step {step}: Green times: {green_times}, Surplus rates: {surplus_rates}, Waiting times: {waiting_times}")

            # print("step:", step, logic)
            # print("remaining time:", remaining_time)

            tls = self.Check_TrafficLight_State()
            # print(tls)
            #print("step", step)
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
                extended_time = 0

            MaxGreenTime = MinGreenTime + 10

            for section_id, section in self.section_objects.items():
                section.update()
                # if bound == "yellow":
                #     pass
                # else:
                #     check_control = section.check_DilemmaZone(elapsed_time, bound, MinGreenTime, extended_time)
                #     if check_control == "pass":
                #         print("*" * 50)
                #         print("section id :", section_id)
                #         print("increase 1s")
                #         print("extended count", extended_time)
                #         new_duration = remaining_time+1
                #         traci.trafficlight.setPhaseDuration("TLS_0", new_duration)
                #         print("*" * 50)
                #         extended_time += 1
                #     elif check_control == "yellow":
                #         traci.trafficlight.setPhase("TLS_0", next_phase_index)

            # if current_phase_index == 0 and remaining_time == 0:
            #     for section_id, section in self.section_objects.items():
            #         print("Section ID:", section_id)
            #         print("Traffic Queue:", section.traffic_queue)
            #     print("*"*50)

            self.make_data()
            self.make_total(step)

            step += 1

        traci.close()

    def Check_TrafficLight_State(self):
        try:
            signal_states = traci.trafficlight.getRedYellowGreenState("TLS_0")
        except traci.exceptions.TraCIException:
            signal_states = 'N/A'
        return signal_states

    def make_data(self):
        #print('collect data')
        time = traci.simulation.getTime()
        append_result = self.section_results.append

        for section_id, section in self.section_objects.items():
            section_co2_emission, section_volume, traffic_queue = section.collect_data()

            #make total volume
            self.total_volume += section_volume

            #print("%s - v: %d, Q: %d"%(section_id, section_volume, section_queue))
            append_result({
                'Time': time,
                'Section': section_id,
                'Section_CO2_Emission': section_co2_emission,
                'Section_Volume': section_volume,
                'traffic_queue': traffic_queue,
                'sectionBound': str(section.direction)
            })

    def make_total(self, step):
        time = traci.simulation.getTime()
        vehicle_ids = traci.vehicle.getIDList()
        append_result = self.total_results.append
        for vehicle_id in vehicle_ids:
            self.total_co2_emission += traci.vehicle.getCO2Emission(vehicle_id)
        # print(self.total_volume)
        append_result({
            'Time': time,
            'Total_Emission': self.total_co2_emission,
            'Total_Volume': self.total_volume
        })

import os
import traci
import pandas as pd
from collections import deque

from Infra import SDetector, SStation, SSection


class Config_SUMO:
    # SUMO Configuration File
    sumocfg_path = "New_TestWay/test_cfg.sumocfg"
    # SUMO Scenario File Path
    scenario_path = "New_TestWay"
    # SUMO Scenario File(.add.xml)
    scenario_file = "new_test.add.xml"

    sumoBinary = r'C:/Program Files (x86)/Eclipse/Sumo/bin/sumo-gui'

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
        # current_phase_index = traci.trafficlight.getPhase("TLS_0")
        # logic = traci.trafficlight.getAllProgramLogics("TLS_0")[0]
        # current_phase = logic.phases[current_phase_index]

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
                if bound == "yellow":
                    pass
                else:
                    # MaxGreenTime = MinGreenTime + 10
                    # current_simulation_time = traci.simulation.getTime()
                    # current_phase_duration = traci.trafficlight.getPhaseDuration("TLS_0")
                    # next_switch_time = traci.trafficlight.getNextSwitch("TLS_0")
                    # elapsed_time = current_simulation_time - (next_switch_time - current_phase_duration)
                    # check_control = section.check_DilemmaZone(elapsed_time, bound, MinGreenTime, MaxGreenTime)
                    check_control = section.check_DilemmaZone(elapsed_time, bound, MinGreenTime, extended_time)
                    if check_control == "pass":
                        print("*" * 50)
                        print("sectino id :", section_id)
                        print("increase 1s")
                        print("extended count", extended_time)
                        new_duration = remaining_time+1
                        traci.trafficlight.setPhaseDuration("TLS_0", new_duration)
                        print("*" * 50)
                        extended_time += 1
                    elif check_control == "yellow":
                        traci.trafficlight.setPhase("TLS_0", next_phase_index)
                count = 0

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
        print(self.total_volume)
        append_result({
            'Time': time,
            'Total_Emission': self.total_co2_emission,
            'Total_Volume': self.total_volume
        })

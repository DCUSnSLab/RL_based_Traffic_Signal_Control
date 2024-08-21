import os
import pickle
from enum import Enum
import traci
import pandas as pd
from collections import deque
from Infra import SDetector, SStation, SSection, DDetector, Infra


class Config_SUMO:
    # SUMO Configuration File
    sumocfg_path = "New_TestWay/test_cfg.sumocfg"
    # SUMO Scenario File Path
    scenario_path = "New_TestWay"
    # SUMO Scenario File(.add.xml)
    scenario_file = "new_test.add.xml"

    sumoBinary = r'C:/Program Files (x86)/Eclipse/Sumo/bin/sumo-gui'

class RunSimulation:
    def __init__(self, config, name="Static Control"):
        self.sigTypeName = name
        self.config = config
        self.__set_SUMO()
        self.section_results = deque()
        self.total_results = deque()

        self.total_co2_emission = 0
        self.total_volume = 0
        self.stepbySec = 1
        self.colDuration = 30  # seconds

        self.traffic_light_id = "TLS_0"
        self.isStop = True

        #init Infra
        self.rtInfra = self.__make_Infra(isNew=True)
        #self.dataInfra = self.__make_Infra(isNew=False)

    def __make_Infra(self, isNew=True):
        infra = None
        DetectorClass = None
        StationClass = None
        SectionClass = None

        if isNew is True:
            DetectorClass = SDetector
            StationClass = SStation
            SectionClass = SSection

            dets = self.__init_detector(DetectorClass)
            station_objects = self.__init_station(dets, StationClass)
            section_objects = self.__init_section(station_objects, SectionClass)
            return Infra(Config_SUMO.sumocfg_path, Config_SUMO.scenario_path, Config_SUMO.scenario_file, section_objects)
        else:
            # 역직렬화
            with open("infra.pkl", "rb") as f:
                loaded_infra = pickle.load(f)

            print("직렬화된 Infra 객체:", type(loaded_infra), loaded_infra)
            print(loaded_infra.getSections())

    def __get_detector_ids(self, config):
        detector_ids = []
        with open(os.path.join(config.scenario_path, config.scenario_file), "r") as f:
            for line in f:
                if "inductionLoop" in line:
                    parts = line.split('"')
                    detector_ids.append(parts[1])
        return detector_ids

    def __init_detector(self, detectorclass=SDetector):
        return [detectorclass(detector_id) for detector_id in self.__get_detector_ids(self.config)]

    def __init_station(self, dets, stationclass=SStation):
        station_objects = {}
        for detector in dets:
            if detector.station_id not in station_objects:
                station_objects[detector.station_id] = stationclass(detector.station_id)
            station_objects[detector.station_id].addDetector(detector)
        return station_objects

    def __init_section(self, stations, sectionclass=SSection):
        section_objects = {}
        for station_id in stations:
            section_id = station_id[1]
            if section_id not in section_objects:
                section_objects[section_id] = sectionclass(section_id)
            section_objects[section_id].addStation(stations[station_id])
        return section_objects

    def __set_SUMO(self):
        traci.start(["sumo-gui", "-c", self.config.sumocfg_path, "--start"])
        traci.simulationStep()

    def __str__(self):
        return self.sigTypeName

    def terminate(self):
        self.isStop = True

    def isTermiated(self):
        return self.isStop

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

        # with open("infra.pkl", "wb") as f:
        #     pickle.dump(self.rtInfra, f)

    def _signalControl(self):
        pass

    def run_simulation(self):
        print('---- start Simulation (signController : ',self.sigTypeName, ") ----")
        step = 0
        self.isStop = False

        while not self.isStop and step <= 11700:
            #start_time = time.time()
            traci.simulationStep()

            self._signalControl()

            for section_id, section in self.rtInfra.getSections().items():
                section.update()

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

        for section_id, section in self.rtInfra.getSections().items():
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
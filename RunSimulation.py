import os
import pickle
from enum import Enum
from typing import Dict

import traci
import pandas as pd
from collections import deque
from Infra import SDetector, SStation, SSection, DDetector, Infra, SECTION_RESULT


class Config_SUMO:
    # SUMO Configuration File
    sumocfg_path = "New_TestWay/test_cfg.sumocfg"
    # SUMO Scenario File Path
    scenario_path = "New_TestWay"
    # SUMO Scenario File(.add.xml)
    scenario_file = "new_test.add.xml"

    sumoBinary = r'C:/Program Files (x86)/Eclipse/Sumo/bin/sumo-gui'

class RunSimulation:
    def __init__(self, config, name="Static Control", isExtract=False):
        self.sigTypeName = name
        self.config = config
        self.setDone = False
        if isExtract is False:
            self.__set_SUMO()
        self.section_results = deque()
        self.total_results = deque()
        self.total_results_comp = deque()

        self.total_co2_emission = 0
        self.total_volume = 0
        self.stepbySec = 1
        self.colDuration = 30  # seconds

        self.traffic_light_id = "TLS_0"
        self.isStop = True

        self.original_logic = None
        self.logic = None

        #init Infra
        self.rtInfra = self.__make_Infra(isNew=True)
        self.compareInfra: Infra = None

    def __make_Infra(self, isNew=True, fileName=None):
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
            return Infra(Config_SUMO.sumocfg_path, Config_SUMO.scenario_path, Config_SUMO.scenario_file, section_objects, self.sigTypeName)
        else:
            # 역직렬화
            with open(fileName, "rb") as f:
                self.compareInfra = pickle.load(f)

            print("Loaded Infra:", type(self.compareInfra), self.compareInfra)

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

    def __init_section(self, stations, sectionclass=SSection) -> Dict[int, SSection]:
        section_objects = {}
        logic = None
        if sectionclass is SSection:
            if self.setDone is True:
                logic = traci.trafficlight.getAllProgramLogics("TLS_0")[0]

        for station_id in stations:
            section_id = station_id[1]
            if section_id not in section_objects:
                section_objects[section_id] = sectionclass(section_id)
            section_objects[section_id].addStation(stations[station_id])

        #set Default greentime
        for sid, section in section_objects.items():
            if logic is not None:
                section.default_greentime = logic.phases[section.direction.value[1]].duration
        return section_objects

    def __set_SUMO(self):
        traci.start(["sumo-gui", "-c", self.config.sumocfg_path, "--start"])
        traci.simulationStep()
        self.setDone = True

    def __str__(self):
        return self.sigTypeName

    def terminate(self):
        self.isStop = True

    def isTermiated(self):
        return self.isStop

    def saveData(self):
        if self.isStop is True:
            print('save data clicked')
            with open(self.rtInfra.setSaveFileName(), "wb") as f:
                pickle.dump(self.rtInfra, f)
                print('---file saved at ',self.rtInfra.getFileName())
            #self.extract_excel()

    def loadData(self, fileName):
        if fileName is not None:
            print('load Infra File - ', fileName)
            self.__make_Infra(isNew=False, fileName=fileName)
            #self.__make_total_comp()


    def extract_excel(self, saveCompare=False):
        section_results = deque()
        append_result = section_results.append
        file_name = ""
        if saveCompare is False:
            data = self.rtInfra
        else:
            data = self.compareInfra
            file_name = 'extract_'

        timedata = data.getSections()['0'].getDatabyID(SECTION_RESULT.TIME)
        for i, time in enumerate(timedata):
            for section_id, section in data.getSections().items():
                section_co2_emission, section_volume, traffic_queue, green_time = section.collect_data()

                # print("%s - v: %d, Q: %d"%(section_id, section_volume, section_queue))
                append_result({
                    'Time': time,
                    'Section': section_id,
                    'Section_CO2_Emission': section.getDatabyID(SECTION_RESULT.CO2_EMISSION)[i],
                    'Section_Volume': section.getDatabyID(SECTION_RESULT.VOLUME)[i],
                    'traffic_queue': section.getDatabyID(SECTION_RESULT.TRAFFIC_QUEUE)[i],
                    'green_time': section.getDatabyID(SECTION_RESULT.GREEN_TIME)[i],
                    'sectionBound': str(section.direction)
                })

        df = pd.DataFrame(section_results)

        co2_emission_df = df.pivot(index='Time', columns='Section', values='Section_CO2_Emission')
        volume_df = df.pivot(index='Time', columns='Section', values='Section_Volume')
        queue_df = df.pivot(index='Time', columns='Section', values='traffic_queue')
        greentime_df = df.pivot(index='Time', columns='Section', values='green_time')
        with pd.ExcelWriter(file_name+'section_results.xlsx') as writer:
            co2_emission_df.to_excel(writer, sheet_name='Section_CO2_Emission')
            volume_df.to_excel(writer, sheet_name='Section_Volume')
            queue_df.to_excel(writer, sheet_name='traffic_queue')
            greentime_df.to_excel(writer, sheet_name='traffic_queue')

        print("Maked Excel")

        # with open("infra.pkl", "wb") as f:
        #     pickle.dump(self.rtInfra, f)

    def _refreshSignalPhase(self):
        traci.trafficlight.setProgramLogic("TLS_0", self.logic)

    def _signalControl(self):
        pass

    def run_simulation(self):
        print('---- start Simulation (signController : ',self.sigTypeName, ") ----")
        step = 0
        self.isStop = False

        while not self.isStop and step <= 11700:
            #start_time = time.time()
            traci.simulationStep()

            #set logic every step
            self.logic = traci.trafficlight.getAllProgramLogics("TLS_0")[0]

            self._signalControl()
            self._refreshSignalPhase()
            # print('Green times: ', end='')

            self.rtInfra.update()
            # for section_id, section in self.rtInfra.getSections().items():
            #     section.update()

            #     print(section.direction.name, ": ", section.getCurrentGreenTime(), end=', ')
            # print()
            # print(f"Green times: {green_times}, Surplus rates: {surplus_rates}, Waiting times: {waiting_times}")

            #self.make_data()
            #self.make_total(step)

            step += 1

        self.isStop = True
        traci.close()


    def Check_TrafficLight_State(self):
        try:
            signal_states = traci.trafficlight.getRedYellowGreenState("TLS_0")
        except traci.exceptions.TraCIException:
            signal_states = 'N/A'
        return signal_states


    def make_total(self, step):
        time = traci.simulation.getTime()
        vehicle_ids = traci.vehicle.getIDList()
        append_result = self.total_results.append
        for sectionid, section in self.rtInfra.getSections().items():
            self.total_co2_emission += section.getCurrentCO2()
        # print(self.total_volume)
        append_result({
            'Time': time,
            'Total_Emission': self.total_co2_emission,
            'Total_Volume': self.total_volume
        })

        self.rtInfra.addTotalResult({
            'Time': time,
            'Total_Emission': self.total_co2_emission,
            'Total_Volume': self.total_volume
        })

    def __make_total_comp(self):
        if self.compareInfra is not None:
            self.total_results_comp = self.compareInfra.getTotalResult()
import pickle

from Infra import Detector, SDetector, SStation, SSection, Infra, DSection
from RunSimulation import Config_SUMO

detector = SDetector("Det_03001700")
detector2 = SDetector("Det_03001701")
detector3 = SDetector("Det_03001801")
detector4 = SDetector("Det_01001301")
detector.append_speeds(10)
detector.append_speeds(20)
detector.append_speeds(30)
detector.append_volumes(1)
detector.append_volumes(1)
detector.append_volumes(2)

detectors = [detector, detector2,detector3, detector4]

station_objects = {}
for detector in detectors:
    if detector.station_id not in station_objects:
        station_objects[detector.station_id] = SStation(detector.station_id)
    station_objects[detector.station_id].addDetector(detector)

section_objects = {}
for station_id in station_objects:
    section_id = station_id[1]
    if section_id not in section_objects:
        section_objects[section_id] = SSection(section_id)
    section_objects[section_id].addStation(station_objects[station_id])

section = section_objects['3']
print(type(section))
infra = Infra(Config_SUMO.sumocfg_path, Config_SUMO.scenario_path, Config_SUMO.scenario_file, list(section_objects.values()))

# with open("infra.pkl", "wb") as f:
#     pickle.dump(infra, f)

# 역직렬화
with open("infra.pkl", "rb") as f:
    loaded_infra = pickle.load(f)

print("직렬화된 Detector 객체:", type(loaded_infra), loaded_infra)

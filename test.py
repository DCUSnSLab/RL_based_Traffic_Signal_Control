import pickle

from Infra import Detector, SDetector, SStation

detector = SDetector("Det_03001700")
detector2 = SDetector("Det_03001701")
detector3 = SDetector("Det_03001801")
detector.append_speeds(10)
detector.append_speeds(20)
detector.append_speeds(30)
detector.append_volumes(1)
detector.append_volumes(1)
detector.append_volumes(2)

detectors = [detector, detector2,detector3]

station_objects = {}
for detector in detectors:
    if detector.station_id not in station_objects:
        station_objects[detector.station_id] = SStation(detector.station_id)
    station_objects[detector.station_id].addDetector(detector)


station = station_objects['030017']
print(station)

with open("station.pkl", "wb") as f:
    pickle.dump(station, f)

# 역직렬화
with open("station.pkl", "rb") as f:
    loaded_station = pickle.load(f)

print("직렬화된 Detector 객체:", type(loaded_station), loaded_station)
print(loaded_station)

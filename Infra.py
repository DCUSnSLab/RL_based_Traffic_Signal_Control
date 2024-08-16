from collections import deque
from enum import Enum
import traci
import math
from traci import TraCIException

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

class SMUtil:
    MPStoKPH = 3.6
    secPerHour = 3600
    sec = 1


def get_input_station_value(direction: Direction) -> str:
    # Direction의 name으로 InputStation을 찾아서 value를 반환
    return InputStation[direction.name].value

# Detector
class Detector:
    def __init__(self, id):
        self.id = id
        self.aux, self.bound, self.station_id, self.detector_id = self.parse_detector_id(id)
        self.flow = 0
        self.density = 0
        self.volumes = deque()
        self.speeds = deque()
        self.append_volumes = self.volumes.append
        self.append_speeds = self.speeds.append

    def __str__(self):
        return f"Detector {self.id} at station {self.station_id} volumes {len(self.volumes)} and speeds {len(self.speeds)}"

    def __repr__(self):
        return f""
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
        pass

    def getVolume(self):
        return self.volumes[-1]

    def getVehicles(self):
        return self.prevVehicles

    def getSpeed(self):
        return self.speeds[-1]

        # 직렬화할 데이터를 정의하는 메서드
    def __getstate__(self):
        # 기본 상태를 가져온 후, flow, density와 parse_detector_id()에서 생성된 필드를 제거
        state = self.__dict__.copy()
        del state['flow']
        del state['density']
        del state['aux']
        del state['bound']
        del state['station_id']
        del state['detector_id']
        return state

    # 역직렬화된 데이터를 객체 상태에 복원하는 메서드
    def __setstate__(self, state):
        # 상태를 설정하고, flow와 density, 그리고 parse_detector_id()의 필드를 다시 설정
        self.__dict__.update(state)
        self.flow = 0
        self.density = 0
        self.aux, self.bound, self.station_id, self.detector_id = self.parse_detector_id(self.id)

class SDetector(Detector):
    def __int__(self, id):
        super().__init__(id)
        self.prevVehicles = tuple()


    def update(self):
        vehicle_ids = traci.inductionloop.getLastStepVehicleIDs(self.id)
        #check duplicated vehicles
        dupvol = 0
        speedcnt = 0
        volume = 0
        speed = 0
        for veh in vehicle_ids:
            if self.prevVehicles is not None and veh in self.prevVehicles:
                dupvol += 1
            else:
                speed +=  traci.inductionloop.getIntervalMeanSpeed(self.id)
                speedcnt += 1
            # if self.id == 'Det_02000000' or self.id == 'Det_02000001' or self.id == 'Det_12002604':
            #     print(" --- each %s %s -> u : %d"%(self.id, veh, self.speed))



        volume = traci.inductionloop.getLastStepVehicleNumber(self.id) - dupvol
        self.flow = volume * SMUtil.secPerHour / SMUtil.sec
        speed = 0 if speedcnt == 0 else speed / speedcnt
        self.density = 0 if speed == 0 else self.flow / (speed * SMUtil.MPStoKPH)
        # if self.id == 'Det_02000000' or self.id == 'Det_02000001' or self.id == 'Det_12002604':
        #     print("%s -> v : %d, u : %d, k : %d" % (self.id, self.volume, self.speed, self.density))
            #print('--- lsvid : ', vehicle_ids, self.prevVehicles, traci.inductionloop.getLastStepVehicleNumber(self.id), dupvol )
        self.prevVehicles = vehicle_ids
        self.append_volumes(volume)
        self.append_speeds(speed)

class Station:
    def __init__(self, id, detectors=None):
        self.id = id
        self.dets = [] if detectors is None else detectors
        self.direction = None if len(self.dets) == 0 else self.dets[0].bound

        self.volumes = deque()
        self.speeds = deque()
        self.exitVolumes = deque()
        self.append_volumes = self.volumes.append
        self.append_exitVolume = self.exitVolumes.append
        self.append_speeds = self.speeds.append

    def addDetector(self, detector):
        self.dets.append(detector)

    def update(self):
        pass

    def getVolume(self):
        return self.volumes[-1]

    def getSpeed(self):
        return self.speeds[-1]

    def getExitVolume(self):
        return self.exitVolumes[-1]

    # 직렬화할 데이터를 정의하는 메서드
    def __getstate__(self):
        state = self.__dict__.copy()
        del state['direction']
        return state

    # 역직렬화된 데이터를 객체 상태에 복원하는 메서드
    def __setstate__(self, state):
        self.__dict__.update(state)
        self.direction = None if len(self.dets) == 0 else self.dets[0].bound

class SStation(Station):
    def __init__(self, id, detectors=None):
        super().__init__(id, detectors)
        self.inputVeh = set()
        self.exitVeh = set()

    def update(self):
        volume = 0
        speed = 0
        exitVolume = 0
        self.inputVeh = set()
        self.exitVeh = set()

        for det in self.dets:
            det.update()

            if det.aux == '1':
                exitVolume += det.getVolume()
                self.exitVeh.update(det.getVehicles())
            else:
                volume += det.getVolume()
                speed += det.getSpeed()
                self.inputVeh.update(det.getVehicles())

        # if self.id == '020000' or self.id == '120026':
        #     print('--station id',self.id,', volume: ',self.volume, ' speed: ',self.speed)

        speed = 0 if volume == 0 else speed / volume
        volume = volume if volume == 0 or volume < len(self.inputVeh) else len(self.inputVeh)
        exitVolume = exitVolume if exitVolume == 0 or exitVolume < len(self.exitVeh) else len(self.exitVeh)

        self.append_volumes(volume)
        self.append_speeds(speed)
        self.append_exitVolume(exitVolume)
        # if self.id == '020000' or self.id == '120026':
        #     print('station id',self.id,', volume: ',self.getVolume(), ' speed: ',self.getSpeed(), (self.getSpeed() * SMUtil.MPStoKPH))
        #     #print('station id : ', self.id, 'iv: ',self.inputVeh, 'ev: ', self.exitVeh)

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

        #append data
        self.section_co2 = deque()
        self.section_volumes = deque()
        self.section_queues = deque()
        self.append_section_co2 = self.section_co2.append
        self.append_section_volumes = self.section_volumes.append
        self.append_section_queues = self.section_queues.append

    def collect_data(self):
        return self.section_co2[-1], self.section_volumes[-1], self.section_queues[-1]

    def update(self):
        pass

class SSection(Section):
    def __init__(self, id, stations):
        super().__init__(id, stations)

        #for data
        self.traffic_queue = 0
        self.section_vehicles = set()

        #for dilemmaZone
        self.stop_lane = self.StopLane_position()
        self.in_dilemmaZone = set()

    def check_DilemmaZone(self, time, traffic_light_bound, MinGreenTime, MaxGreenTime):
        if traffic_light_bound == self.id:
            DilemmaZone_results = []
            for vehicle in self.section_vehicles:
                vehicle_distance_list = []
                vehicle_position = traci.vehicle.getPosition(vehicle)
                vehicle_x, vehicle_y = vehicle_position
                # vehicle_distance = math.sqrt((self.stop_x - vehicle_x) ** 2 + (self.stop_y - vehicle_y) ** 2)
                # for i in range(0, len(self.stop_lane),2):
                #     stop_lane_x, stop_lane_y = self.stop_lane[i:i+2]
                #     distance = math.sqrt((stop_lane_x - vehicle_x) ** 2 + (stop_lane_y - vehicle_y) ** 2)
                #     vehicle_distance_list.append(distance)
                # vehicle_distance = min(vehicle_distance_list)
                # vehicle_speed = traci.vehicle.getSpeed(vehicle)
                # vehicle_type = traci.vehicle.getTypeID(vehicle)
                # check_value = self.DilemmaZoneControlSignal(time, vehicle_speed, vehicle_distance, vehicle_type, MinGreenTime, MaxGreenTime)
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

    def DilemmaZoneControlSignal(self, time, s, d, car_type, MinGreenTime, MaxGreenTime):
        check = "none"
        s = s*3.6
        if time >= MinGreenTime:
            # if time < MaxGreenTime:
            if MaxGreenTime <= 10:
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

    def update(self):
        section_co2_emission = 0
        section_volume = 0
        removal_veh = list()
        for i, station in enumerate(self.stations):
            #update station data
            station.update()

            if i == 0:
                section_volume += station.getVolume()
                self.section_vehicles.update(station.getInputVehIds())

            #update input station data according to InputStation Setup
            if station.id == get_input_station_value(self.direction):
                self.traffic_queue += station.getVolume()

            self.traffic_queue -= station.getExitVolume()
            self.section_vehicles.difference_update(station.getExitVehIds())
            # if self.id == '2':
            #     if station.getExitVolume() > 0:
            #         print('----exit vol : ',station.getExitVolume())

        for vehicle in self.section_vehicles:
            try:
                if traci.vehicle.getCO2Emission(vehicle) >= 0:
                    section_co2_emission += traci.vehicle.getCO2Emission(vehicle) / 1000
            except TraCIException:
                print('------------------------disappear -> ',vehicle)
                #self.section_vehicles.remove(vehicle)
                removal_veh.append(vehicle)

        self.section_vehicles.difference_update(removal_veh)

        self.append_section_queues(self.traffic_queue)
        self.append_section_co2(section_co2_emission)
        self.append_section_volumes(section_volume)

        # if self.id == '2':
        #     print('Sid : ',self.id, ', Queue : ')
        #     print('---- VehIds : ', self.section_vehicles)
        #self.collect_data()
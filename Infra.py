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
        state['__class__'] = Detector
        return state

    # 역직렬화된 데이터를 객체 상태에 복원하는 메서드
    def __setstate__(self, state):
        # 상태를 설정하고, flow와 density, 그리고 parse_detector_id()의 필드를 다시 설정
        self.__dict__.update(state)
        self.flow = 0
        self.density = 0
        self.aux, self.bound, self.station_id, self.detector_id = self.parse_detector_id(self.id)
        self.__class__ = DDetector #state.pop('__class__', Detector)

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

class DDetector(Detector):
    def __int__(self, id):
        super().__init__(id)

    def update(self):
        print('test')

class Station:
    def __init__(self, id, detectors=None):
        self.id = id
        self.dets = [] if detectors is None else detectors
        self.direction = None

        self.volumes = deque()
        self.speeds = deque()
        self.exitVolumes = deque()
        self.append_volumes = self.volumes.append
        self.append_exitVolume = self.exitVolumes.append
        self.append_speeds = self.speeds.append

        self.__define_direction()

    def __define_direction(self):
        if not hasattr(self, 'direction') or self.direction is None:
            self.direction = None if len(self.dets) == 0 else self.dets[0].bound

    def addDetector(self, detector):
        self.dets.append(detector)
        self.__define_direction()

    def update(self):
        pass

    def getVolume(self):
        return self.volumes[-1]

    def getSpeed(self):
        return self.speeds[-1]

    def getExitVolume(self):
        return self.exitVolumes[-1]

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['direction']
        state['__class__'] = Station
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.__define_direction()
        self.__class__ = DStation #state.pop('__class__', Station)
        #self.direction = None if len(self.dets) == 0 else self.dets[0].bound

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

class DStation(Station):
    def __init__(self, id, detectors=None):
        super().__init__(id, detectors)

    def update(self):
        pass

class Section:
    def __init__(self, id, stations):
        self.id = id
        self.stations = [] if stations is None else stations
        self.direction = None

        #append data
        self.section_co2 = deque()
        self.section_volumes = deque()
        self.section_queues = deque()
        self.append_section_co2 = self.section_co2.append
        self.append_section_volumes = self.section_volumes.append
        self.append_section_queues = self.section_queues.append

        self.__define_direction()

    def __define_direction(self):
        if not hasattr(self, 'direction') or self.direction is None:
            self.direction = None if len(self.stations) == 0 else self.stations[0].direction

    def addStation(self, station):
        self.stations.append(station)
        self.__define_direction()

    def collect_data(self):
        return self.section_co2[-1], self.section_volumes[-1], self.section_queues[-1]

    def update(self):
        pass

    def print(self):
        print('this is Section!!')

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['direction']  # direction은 계산 가능한 필드이므로 직렬화에서 제외
        state['__class__'] = Section
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        # direction은 stations의 첫 번째 항목으로부터 다시 계산하여 설정
        self.__define_direction()
        self.__class__ = DSection#state.pop('__class__', Section)

class SSection(Section):
    def __init__(self, id, stations=None):
        super().__init__(id, stations)

        #for data
        self.traffic_queue = 0
        self.section_vehicles = set()

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
    def print(self):
        print('this is SSection!!')

class DSection(Section):
    def __init__(self, id, stations=None):
        super().__init__(id, stations)

    def update(self):
        pass

    def print(self):
        print('this is DSection!!')

class Infra:
    def __init__(self, sumocfg_path, scenario_path, scenario_file, sections):
        self.sumocfg_path = sumocfg_path
        # SUMO Scenario File Path
        self.scenario_path = scenario_path
        # SUMO Scenario File(.add.xml)
        self.scenario_file = scenario_file
        self.__sections = sections

    def getSections(self):
        return self.__sections

    def __getstate__(self):
        state = self.__dict__.copy()
        return state

    # 역직렬화된 데이터를 객체 상태에 복원하는 메서드
    def __setstate__(self, state):
        self.__dict__.update(state)

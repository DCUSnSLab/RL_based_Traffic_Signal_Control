# === 공통 열거형 ===
import re
from enum import IntEnum, Enum
from collections import deque
from typing import List, Tuple, Optional, Dict, Union
from datetime import datetime

import traci
from traci import TraCIException

class Config_SUMO:
    # SUMO Configuration File
    sumocfg_path = "New_TestWay/multi_intersection.sumocfg"
    # SUMO Scenario File Path
    scenario_path = "New_TestWay"
    # SUMO Scenario File(.add.xml)
    scenario_file = "multi_intersection.add.xml"
    route_file = "single_multi_route_v2.rou.xml"
    scenario_file_rl = "New_TestWay/Goyang_multi_intersection_v2.net_mergy.xml"
    route_file_rl = "New_TestWay/generated_single_multi_flows_v2.xml"
    rl_model_path = r"C:\Users\kwon\Desktop\testplace\RL_based_Traffic_Signal_Control\dqn_model_centralized_min5.zip"

class Direction(IntEnum):
    SB = 0
    NB = 1
    EB = 2
    WB = 3

    @classmethod
    def from_code(cls, code: int):
        return Direction(code)

class Move(IntEnum):
    L = 0
    S = 1
    R = 2
    U = 3
    MIXED = 9  # 9=혼합/미지정

class DetectorType(IntEnum):
    INPUT = 0
    OUTPUT = 1
    QUEUE_INPUT = 2

# === 유틸 ===
class SMUtil:
    MPStoKPH = 3.6
    secPerHour = 3600
    sec = 1
    interval = 10  # 속도 구간 집계 간격(스텝 수)

class SECTION_RESULT(Enum):
    TIME = 'Time'
    TIMEINT = 'Time Interval'
    SECTIONID = 'Sectionid'
    SECTION_CO2 = 'Section_CO2_Emission'
    VOLUME = 'Section_Volume'
    SPEED_INT = 'Section Speed by Interval'
    TRAFFIC_QUEUE = 'traffic_queue'
    GREEN_TIME = 'green_time'
    DIRECTION = 'direction'
    WAITING_TIME = 'waiting time'

class INTERSECTION_RESULT(Enum):
    """교차로 단위 집계 결과"""
    TIME = 'Time'
    TOTAL_CO2 = 'Intersection CO2'                    # per-step (kg/step)
    TOTAL_CO2_ACC = 'Intersection CO2 ACC'            # accumulated
    TOTAL_VOLUME = 'Intersection Volume'              # per-step (veh/step)
    TOTAL_VOLUME_ACC = 'Intersection Volume ACC'      # accumulated  ← 추가
    TOTAL_WAITING_TIME = 'Intersection Waiting Time'  # per-step (sec/step)
    TOTAL_QUEUE = 'Intersection Queue'                # per-step (veh)

    @classmethod
    def from_string(cls, string_value):
        for m in cls:
            if m.value == string_value:
                return m
        raise ValueError(f"{string_value} is not a valid INTERSECTION_RESULT value")

class NETWORK_RESULT(Enum):
    """네트워크(Infra) 총합 결과 — 기존 TOTAL_RESULT 대체"""
    NET_TIME = 'Time'
    NET_TOTAL_CO2 = 'Total CO2'                    # per-step
    NET_TOTAL_CO2_ACC = 'Total CO2 ACC'            # accumulated
    NET_TOTAL_VOLUME = 'Total Volume'              # per-step        ← 의미 정정
    NET_TOTAL_VOLUME_ACC = 'Total Volume ACC'      # accumulated     ← 추가
    NET_TOTAL_WAITING_TIME = 'Total Waiting Time'  # per-step
    NET_TOTAL_QUEUE = 'Total Queue'                # per-step

    @classmethod
    def from_string(cls, string_value):
        for m in cls:
            if m.value == string_value:
                return m
        raise ValueError(f"{string_value} is not a valid NETWORK_RESULT value")


# === 새 규칙 전용 파서/포맷터 ===
DET_PATTERN = re.compile(r'^Det_(\d{4})([0-3])([0-3]|9)([0-2])(\d{3})(\d{2})$')

def parse_detector_id(det_id: str):
    m = DET_PATTERN.match(det_id)
    if not m:
        raise ValueError(f"Invalid detector ID: {det_id}")
    intid = int(m.group(1))
    bound = int(m.group(2))
    move  = int(m.group(3))
    type_ = int(m.group(4))
    sid   = int(m.group(5))
    lane  = int(m.group(6))
    return intid, bound, move, type_, sid, lane

def make_station_key(intid:int, bound:int, type_:int, sid:int) -> Tuple[int,int,int,int]:
    return (intid, bound, type_, sid)

def station_key_to_str(key: Tuple[int,int,int,int]) -> str:
    intid, bound, type_, sid = key
    return f"{intid:04d}{bound}{type_}{sid:03d}"

# =========================
# Detector / SDetector / DDetector
# =========================
class Detector:
    def __init__(self, id: str):
        self.id = id
        intid, bound, move, type_, sid, lane = parse_detector_id(id)

        # 규칙 기반 필드
        self.intid: int = intid
        self.bound: Direction = Direction.from_code(bound)
        self.move: Move = Move(move) if move in (0,1,2,3) else Move.MIXED
        self.type: DetectorType = DetectorType(type_)
        self.sid: int = sid
        self.lane: int = lane

        self.station_key = make_station_key(self.intid, int(self.bound), int(self.type), self.sid)
        self.station_id: str = station_key_to_str(self.station_key)

        # runtime
        self.flow = 0.0
        self.density = 0.0
        self.volumes = deque()
        self.speeds = deque()
        self.prevVehicles = tuple()
        self.append_volumes = self.volumes.append
        self.append_speeds = self.speeds.append

    # 헬퍼
    def is_input(self) -> bool:
        return self.type in (DetectorType.INPUT, DetectorType.QUEUE_INPUT)
    def is_output(self) -> bool:
        return self.type == DetectorType.OUTPUT
    def is_queue_input(self) -> bool:
        return self.type == DetectorType.QUEUE_INPUT

    # API
    def update(self):
        pass
    def getVolume(self):
        return self.volumes[-1] if self.volumes else -1
    def getVehicles(self):
        return self.prevVehicles
    def getSpeed(self):
        return self.speeds[-1] if self.speeds else -1

    # 직렬화
    def __getstate__(self):
        st = self.__dict__.copy()
        for k in ("flow", "density", "prevVehicles"):
            st.pop(k, None)
        return st
    def __setstate__(self, st):
        self.__dict__.update(st)
        self.flow = 0.0
        self.density = 0.0
        self.__class__ = DDetector

class SDetector(Detector):
    def __init__(self, id: str):
        super().__init__(id)

    def update(self):
        vids = traci.inductionloop.getLastStepVehicleIDs(self.id)
        dup = 0; sc = 0; ss = 0.0
        for v in vids:
            if self.prevVehicles and v in self.prevVehicles:
                dup += 1
            else:
                # 새로 감지된 차량에 대해 interval 평균속도 사용
                ss += traci.inductionloop.getIntervalMeanSpeed(self.id); sc += 1
        vol = traci.inductionloop.getLastStepVehicleNumber(self.id) - dup
        self.flow = vol * SMUtil.secPerHour / SMUtil.sec
        avg = 0.0 if sc == 0 else ss / sc
        self.density = 0.0 if avg == 0 else (self.flow / (avg * SMUtil.MPStoKPH))
        self.prevVehicles = tuple(vids)
        self.append_volumes(vol)
        self.append_speeds(avg)

class DDetector(Detector):
    def __init__(self, id: str):
        super().__init__(id)
    def update(self): return

# =========================
# Station / SStation / DStation
# =========================
class Station:
    """그룹 키: (intid, bound, type, sid)"""
    def __init__(self, station_key: Tuple[int,int,int,int], detectors: Optional[List[Detector]] = None):
        self.station_key = station_key
        self.id = station_key_to_str(station_key)
        self.dets: List[Detector] = [] if detectors is None else detectors

        intid, bound, type_, sid = self.station_key
        self.intid = intid
        self.direction: Direction = Direction.from_code(bound)
        self.type: DetectorType = DetectorType(type_)
        self.sid = sid

        self.volumes = deque()
        self.speeds = deque()
        self.speeds_int = deque()
        self.exitVolumes = deque()
        self.append_volumes = self.volumes.append
        self.append_exitVolume = self.exitVolumes.append
        self.append_speeds = self.speeds.append
        self.append_speeds_int = self.speeds_int.append

        # 내부 유지용 ID 집합
        self._inputVeh: set = set()
        self._exitVeh: set = set()

    def addDetector(self, det: Detector):
        self.dets.append(det)

    def update(self): pass

    def getVolume(self): return self.volumes[-1] if self.volumes else -1
    def getSpeed(self): return self.speeds[-1] if self.speeds else -1
    def getSpeedInt(self): return self.speeds_int[-1] if self.speeds_int else -1
    def getSpeedInts(self): return self.speeds_int
    def getExitVolume(self): return self.exitVolumes[-1] if self.exitVolumes else -1

    def getInputVehIds(self) -> set: return self._inputVeh
    def getExitVehIds(self) -> set:  return self._exitVeh

    def __getstate__(self): return self.__dict__.copy()
    def __setstate__(self, st):
        self.__dict__.update(st)
        self.__class__ = DStation

class SStation(Station):
    def __init__(self, station_key: Tuple[int,int,int,int], detectors: Optional[List[Detector]] = None):
        super().__init__(station_key, detectors)

    def update(self):
        vol = 0; sp = 0.0; xvol = 0
        self._inputVeh.clear(); self._exitVeh.clear()
        for det in self.dets:
            det.update()
            if det.is_output():
                xvol += det.getVolume()
                self._exitVeh.update(det.getVehicles())
            elif det.is_input():
                v = det.getVolume()
                vol += max(0, v)
                s = det.getSpeed()
                if s != -1:
                    sp += s
                self._inputVeh.update(det.getVehicles())

        # 볼륨 보정(중복방지) 및 평균속도
        vol = vol if vol == 0 or vol <= len(self._inputVeh) else len(self._inputVeh)
        xvol = xvol if xvol == 0 or xvol <= len(self._exitVeh) else len(self._exitVeh)
        avg = -1 if vol == 0 else (sp / vol)

        self.append_volumes(vol)
        self.append_speeds(avg)
        self.append_exitVolume(xvol)

        # 구간(Interval) 속도 집계
        if len(self.speeds) and (len(self.speeds) % SMUtil.interval == 0):
            last = list(self.speeds)[-SMUtil.interval:]
            valid = [s for s in last if s != -1]
            self.append_speeds_int(0 if not valid else sum(valid)/len(valid))

class DStation(Station):
    def __init__(self, station_key: Tuple[int,int,int,int], detectors: Optional[List[Detector]] = None):
        super().__init__(station_key, detectors)
    def update(self): return

# =========================
# Section
# =========================
class Section:
    """
    한 방면(EB/WB/NB/SB)의 집계 단위 베이스 클래스.
    - stations: 해당 방면에 속한 Station들의 리스트(S/D 혼용 가능)
    - input_station_lookup (Optional): Intersection에서 주입하는 룩업 맵
      예) { Direction.EB: { "queue_inputs": ["00022 2 2 200", ...],
                            "inputs": ["00022 2 0 018", ...] }, ... }
    """
    def __init__(self, id: str, stations: Optional[List[Station]] = None):
        self.id = id
        self.stations: List[Station] = [] if stations is None else stations
        self.direction: Optional[Direction] = None  # 첫 station 기준으로 설정
        self.default_greentime = 0

        # 섹션 시계열 버퍼
        self.__time = deque()
        self.__timeint = deque()
        self.__section_co2 = deque()
        self.__section_volumes = deque()
        self.__section_speedint = deque()
        self.__section_queues = deque()
        self._section_greentime = deque()
        self.__section_waitingtime = deque()

        # append alias
        self.append_section_time = self.__time.append
        self.append_section_timeint = self.__timeint.append
        self.append_section_co2 = self.__section_co2.append
        self.append_section_volumes = self.__section_volumes.append
        self.append_section_speedint = self.__section_speedint.append
        self.append_section_queues = self.__section_queues.append
        self.append_section_greentime = self._section_greentime.append
        self.append_section_waitingtime = self.__section_waitingtime.append

        # 조회용 맵
        self.dataDic: Dict[SECTION_RESULT, deque] = {
            SECTION_RESULT.TIME: self.__time,
            SECTION_RESULT.TIMEINT: self.__timeint,
            SECTION_RESULT.SECTION_CO2: self.__section_co2,
            SECTION_RESULT.TRAFFIC_QUEUE: self.__section_queues,
            SECTION_RESULT.GREEN_TIME: self._section_greentime,
            SECTION_RESULT.VOLUME: self.__section_volumes,
            SECTION_RESULT.SPEED_INT: self.__section_speedint,
            SECTION_RESULT.WAITING_TIME: self.__section_waitingtime,
        }

        # Intersection에서 주입될 수 있는 룩업 (없어도 동작)
        self.input_station_lookup: Optional[Dict] = None

        # 런타임 상태 (SSection에서 사용)
        self.traffic_queue = 0
        self.current_greentime = -1
        self.section_vehicles = set()

        self.__define_direction()

    # 내부: 방향 결정
    def __define_direction(self):
        if self.direction is None and self.stations:
            st0 = self.stations[0]
            self.direction = getattr(st0, "direction", None)

    # 구성 변경
    def addStation(self, station: Station):
        self.stations.append(station)
        if self.direction is None and hasattr(station, "direction"):
            self.direction = station.direction

    # 조회 도우미
    def collect_data(self):
        if len(self.dataDic[SECTION_RESULT.VOLUME]) == 0:
            return 0, 0, 0, 0
        return (
            self.getCurrentCO2(),
            self.getCurrentVol(),
            self.getCurrentQueue(),
            self.getCurrentGreenTime(),
        )

    def getCurrentQueue(self) -> int:
        q = self.dataDic[SECTION_RESULT.TRAFFIC_QUEUE]
        return q[-1] if q else 0

    def getCurrentCO2(self) -> float:
        c = self.dataDic[SECTION_RESULT.SECTION_CO2]
        return c[-1] if c else 0.0

    def getCurrentVol(self) -> int:
        v = self.dataDic[SECTION_RESULT.VOLUME]
        return v[-1] if v else 0

    def getCurrentGreenTime(self) -> float:
        g = self.dataDic[SECTION_RESULT.GREEN_TIME]
        return g[-1] if g else 0.0

    def getCurrentWaitingTime(self) -> float:
        w = self.dataDic[SECTION_RESULT.WAITING_TIME]
        return w[-1] if w else 0.0

    def getCurrentTime(self) -> float:
        t = self.dataDic[SECTION_RESULT.TIME]
        return t[-1] if t else 0.0

    def getDatabyID(self, id: SECTION_RESULT):
        return self.dataDic[id]

    # 입력 스테이션 선택(큐계산용) — 룩업 우선, 없으면 타입 기반 기본 규칙
    def _select_input_station_ids(self) -> List[str]:
        # 룩업 사용
        if self.input_station_lookup and self.direction in self.input_station_lookup:
            cfg = self.input_station_lookup[self.direction] or {}
            # 우선순위: queue_inputs > inputs
            if 'queue_inputs' in cfg and cfg['queue_inputs']:
                return list(cfg['queue_inputs'])
            if 'inputs' in cfg and cfg['inputs']:
                return list(cfg['inputs'])

        # 기본 규칙: QUEUE_INPUT 우선, 없으면 INPUT 전체
        q_ids = [st.id for st in self.stations if st.type == DetectorType.QUEUE_INPUT]
        if q_ids:
            return q_ids
        return [st.id for st in self.stations if st.type == DetectorType.INPUT]

    # 런타임 업데이트(구현은 SSection에서)
    def update(self, time: float):
        pass

    # 신호시간 기록 보조 (SSection에서 사용)
    def updateGreentime(self):
        if self.current_greentime != -1:
            self.append_section_greentime(self.current_greentime)
        else:
            g = self.dataDic[SECTION_RESULT.GREEN_TIME]
            if len(g) > 0:
                self.append_section_greentime(g[-1])
            else:
                self.append_section_greentime(self.default_greentime)

    # 디버그
    def print(self):
        print('this is Section!!')

    # 직렬화 훅
    def __getstate__(self):
        state = self.__dict__.copy()
        state['__class__'] = 'Section'
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.__define_direction()
        self.__class__ = DSection  # 오프라인 뷰 전환

class SSection(Section):
    def update(self, time: float):
        section_co2_emission = 0.0
        section_volume = 0
        removal_veh = []
        prev_cnt = len(self.getDatabyID(SECTION_RESULT.SPEED_INT))
        speed_kph_sum = 0.0;
        speed_kph_cnt = 0;
        got_new = False

        queue_input_ids = set(self._select_input_station_ids())
        inflow_sum = 0;
        outflow_sum = 0

        # ✅ 더 이상 초기화하지 않음: self.section_vehicles 는 '구역 내 추적 집합'
        if not hasattr(self, "section_vehicles") or self.section_vehicles is None:
            self.section_vehicles = set()

        for st in self.stations:
            st.update()

            # 유입 집계 및 '구역 내' 집합 갱신
            if st.type in (DetectorType.INPUT, DetectorType.QUEUE_INPUT):
                v = st.getVolume()
                section_volume += max(0, v)
                # 이 스텝에 입력 검지된 차량을 '구역 내'에 추가
                self.section_vehicles.update(st.getInputVehIds())

            # 큐/유출 집계 + '구역 내' 제거
            if st.id in queue_input_ids:
                inflow_sum += max(0, st.getVolume())
            if st.type == DetectorType.OUTPUT:
                outflow_sum += max(0, st.getExitVolume())
                # 이 스텝에 출구 검지된 차량은 '구역 내'에서 제거
                self.section_vehicles.difference_update(st.getExitVehIds())

            # 속도 interval 집계(기존 그대로)
            scnt = len(st.getSpeedInts())
            if st.type in (DetectorType.INPUT, DetectorType.QUEUE_INPUT) and scnt > prev_cnt:
                s = st.getSpeedInt()
                if s != -1:
                    got_new = True
                    speed_kph_sum += s * SMUtil.MPStoKPH
                    speed_kph_cnt += 1

        if got_new:
            self.append_section_speedint(0.0 if speed_kph_cnt == 0 else speed_kph_sum / speed_kph_cnt)
            self.append_section_timeint(time)

        #  '구역 내' 차량들의 CO2/대기시간 합산
        for veh in list(self.section_vehicles):
            try:
                section_co2_emission += traci.vehicle.getCO2Emission(veh) / 1000.0  # kg/step
            except TraCIException:
                # 시뮬에서 사라진 차량 등은 추적 집합에서 제거
                removal_veh.append(veh)
        if removal_veh:
            self.section_vehicles.difference_update(removal_veh)

        waiting_time_sum = 0.0
        for veh in list(self.section_vehicles):
            try:
                waiting_time_sum += traci.vehicle.getWaitingTime(veh)
            except TraCIException:
                pass

        # 큐/시계열(기존 그대로)
        self.traffic_queue = max(0, self.traffic_queue + inflow_sum - outflow_sum)

        self.append_section_waitingtime(waiting_time_sum)
        self.append_section_queues(self.traffic_queue)
        self.append_section_co2(section_co2_emission)
        self.append_section_volumes(section_volume)
        self.append_section_time(time)
        self.updateGreentime()

class DSection(Section):
    """오프라인(읽기 전용) 섹션. TraCI 의존 없음."""
    def __init__(self, id: str, stations: Optional[List[Station]] = None):
        super().__init__(id, stations)
    def update(self, time: float): return
    def print(self):
        print('this is DSection!!')

# =========================
# Intersection (저장 기능 제거 버전)
# =========================
class Intersection:
    """
    교차로 단위 베이스: 저장 관련 메서드 제거.
    sections: Dict[Direction, Section]
    """
    def __init__(
        self,
        intersection_id: Union[str, int],
        sections: Dict[Direction, Section],
        input_station_map: Optional[Dict[Direction, Dict[str, List[str]]]] = None,
        sig_type: Optional[str] = None
    ):
        self.id = intersection_id
        self.sections = sections
        self.input_station_map = input_station_map
        self.sigType: Optional[str] = sig_type

        # 섹션에 룩업 주입
        if self.input_station_map:
            for sec in self.sections.values():
                try:
                    sec.input_station_lookup = self.input_station_map
                except Exception:
                    pass

        # 교차로 시계열
        self._time = deque()
        self._co2 = deque()
        self._co2_acc = deque()
        self._vol = deque()
        self._vol_acc = deque()
        self._wait = deque()
        self._queue = deque()

        self.dataDic: Dict[INTERSECTION_RESULT, deque] = {
            INTERSECTION_RESULT.TIME: self._time,
            INTERSECTION_RESULT.TOTAL_CO2: self._co2,
            INTERSECTION_RESULT.TOTAL_CO2_ACC: self._co2_acc,
            INTERSECTION_RESULT.TOTAL_VOLUME: self._vol,               # per-step로 정정
            INTERSECTION_RESULT.TOTAL_VOLUME_ACC: self._vol_acc,       # 누적 추가
            INTERSECTION_RESULT.TOTAL_WAITING_TIME: self._wait,
            INTERSECTION_RESULT.TOTAL_QUEUE: self._queue,
        }

    def update(self, time: float): pass
    def get_sections(self): return self.sections
    def get_databy_id(self, tr: INTERSECTION_RESULT): return self.dataDic[tr]
    def get_current_co2(self): return self._co2[-1] if self._co2 else 0.0
    def get_current_volume(self): return self._vol[-1] if self._vol else 0.0
    def get_current_waiting(self): return self._wait[-1] if self._wait else 0.0
    def get_current_queue(self): return self._queue[-1] if self._queue else 0.0
    def get_time_series(self): return self._time

    def __getstate__(self): return self.__dict__.copy()
    def __setstate__(self, st):
        self.__dict__.update(st)
        self.__class__ = DIntersection

class SIntersection(Intersection):
    def __init__(self, intersection_id, sections, input_station_map=None, sig_type=None):
        super().__init__(intersection_id, sections, input_station_map, sig_type)

    def update(self, time: float):
        co2 = vol = wait = queue = 0.0
        for sec in self.sections.values():
            sec.update(time)
            co2   += sec.getCurrentCO2()
            vol   += sec.getCurrentVol()
            wait  += sec.getCurrentWaitingTime()
            q = sec.getCurrentQueue()
            queue += (q if q >= 0 else 0)

        self._co2.append(co2)
        self._co2_acc.append((self._co2_acc[-1] if self._co2_acc else 0.0) + co2)
        self._vol.append(vol)                                           # per-step 유지
        self._vol_acc.append((self._vol_acc[-1] if self._vol_acc else 0.0) + vol)  # 누적 유지
        self._wait.append(wait)
        self._queue.append(queue)
        self._time.append(time)

class DIntersection(Intersection):
    def __init__(self, intersection_id, sections, input_station_map=None, sig_type=None):
        super().__init__(intersection_id, sections, input_station_map, sig_type)
    def update(self, time: float): return

# =========================
# Infra
# =========================
class Infra:
    """
    - intersections: Dict[Union[str,int], Intersection]
    - 네트워크 총합(Infra 단위)만 저장 책임 보유
    """
    def __init__(self, intersections, sumocfg_path, scenario_path, scenario_file, sig_type=None):
        self.intersections: Dict[Union[str,int], Intersection] = intersections
        self.sumocfg_path = sumocfg_path
        self.scenario_path = scenario_path
        self.scenario_file = scenario_file
        self.sigType = sig_type

        # 네트워크 시계열
        self._time = deque()
        self._co2 = deque()
        self._co2_acc = deque()
        self._vol = deque()          # per-step 네트워크 볼륨  ← 추가
        self._vol_acc = deque()
        self._wait = deque()
        self._queue = deque()

        self.dataDic: Dict[NETWORK_RESULT, deque] = {
            NETWORK_RESULT.NET_TIME: self._time,
            NETWORK_RESULT.NET_TOTAL_CO2: self._co2,
            NETWORK_RESULT.NET_TOTAL_CO2_ACC: self._co2_acc,
            NETWORK_RESULT.NET_TOTAL_VOLUME: self._vol,            # per-step로 정정
            NETWORK_RESULT.NET_TOTAL_VOLUME_ACC: self._vol_acc,    # 누적 추가
            NETWORK_RESULT.NET_TOTAL_WAITING_TIME: self._wait,
            NETWORK_RESULT.NET_TOTAL_QUEUE: self._queue,
        }

        # 저장 메타 (Infra에만)
        self.__savedTime: Optional[datetime] = None
        self.__savefileName: Optional[str] = None

    def update(self):
        time = traci.simulation.getTime()
        net_co2 = net_vol = net_wait = net_queue = 0.0
        for inter in self.intersections.values():
            inter.update(time)
            net_co2   += inter.get_current_co2()
            net_vol   += inter.get_current_volume()
            net_wait  += inter.get_current_waiting()
            net_queue += inter.get_current_queue()

        self._co2.append(net_co2)
        self._co2_acc.append((self._co2_acc[-1] if self._co2_acc else 0.0) + net_co2)

        self._vol.append(net_vol)                                            # per-step 추가
        self._vol_acc.append((self._vol_acc[-1] if self._vol_acc else 0.0) + net_vol)

        self._wait.append(net_wait)
        self._queue.append(net_queue)
        self._time.append(time)

    def get_databy_id(self, tr: NETWORK_RESULT): return self.dataDic[tr]
    def get_intersections(self): return self.intersections

    def setSaveFileName(self, name: Optional[str] = None) -> str:
        if self.__savedTime is None: self.setCurrentTime()
        prefix = (self.sigType + '_') if self.sigType else ''
        if name: prefix = name + '_' + prefix
        ts = self.__savedTime.strftime("%Y%m%d%H%M%S")
        self.__savefileName = f"{prefix}NET_{ts}.data"
        return self.__savefileName

    def getFileName(self): return self.__savefileName
    def getSavedTime(self): return self.__savedTime
    def setCurrentTime(self): self.__savedTime = datetime.now()

    def __getstate__(self): return self.__dict__.copy()
    def __setstate__(self, st): self.__dict__.update(st)

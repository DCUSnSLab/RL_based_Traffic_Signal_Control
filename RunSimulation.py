import os
import pickle
from typing import Dict, List, DefaultDict
from collections import defaultdict

import traci
from inframanager import InfraManager
from Infra import (
    SDetector, SStation, SSection,
    SIntersection, Infra,
    Direction,
)

class RunSimulation(InfraManager):
    def __init__(self, config, name="Static Control", isExternalSignal=False):
        super().__init__(config, name, simMode=True, filenames=None, isExternal=isExternalSignal)
        self.stepbySec = 1
        self.colDuration = 30  # seconds

        self.traffic_light_ids = []
        self.isStop = True
        self.step = 0

        self.original_logic = None
        self.logic = None
        self._rtinfra = self.getInfra()

    # === lifecycle hooks ===
    def preinit(self):
        self.__set_SUMO()

    # === Infra build: Detector -> Station -> Section -> Intersection -> Infra ===
    def _make_Infra(self) -> List[Infra]:
        DetectorClass = SDetector
        StationClass = SStation
        SectionClass = SSection

        dets = self.__init_detector(DetectorClass)
        station_objects = self.__init_station(dets, StationClass)
        intersections = self.__build_intersections(station_objects, SectionClass)

        net = Infra(
            intersections,
            self.config.sumocfg_path,
            self.config.scenario_path,
            self.config.scenario_file,
            self.sigTypeName,
        )
        return [net]

    # ---------- detector IO ----------
    def __get_detector_ids(self, config):
        detector_ids = []
        add_path = os.path.join(config.scenario_path, config.scenario_file)
        with open(add_path, "r", encoding="utf-8") as f:
            for line in f:
                if "inductionLoop" in line:
                    parts = line.split('"')
                    if len(parts) > 1:
                        detector_ids.append(parts[1])
        return detector_ids

    def __init_detector(self, detectorclass=SDetector):
        return [detectorclass(detector_id) for detector_id in self.__get_detector_ids(self.config)]

    # ---------- stations ----------
    def __init_station(self, dets, stationclass=SStation):
        """
        반환: dict[str station_id] -> SStation
        생성자에는 (intid, bound, type_, sid) 튜플(station_key)을 전달해야 함.
        딕셔너리 키는 문자열 station_id로 유지(조회·호환성 목적).
        """
        station_objects: Dict[str, SStation] = {}
        for detector in dets:
            sid_key = detector.station_key   # tuple: (intid, bound, type_, sid)
            sid_str = detector.station_id    # string
            st = station_objects.get(sid_str)
            if st is None:
                st = stationclass(sid_key)   # ★ 생성자는 반드시 튜플!
                station_objects[sid_str] = st
            st.addDetector(detector)
        return station_objects

    # ---------- intersections ----------
    def __build_intersections(self, stations: Dict[str, SStation], sectionclass=SSection) -> Dict[int, SIntersection]:
        buckets: DefaultDict[int, Dict[Direction, SSection]] = defaultdict(dict)

        for st in stations.values():
            intid = getattr(st, "intid", None)
            direction = getattr(st, "direction", None)
            if intid is None or direction is None:
                continue

            sec_id = f"{intid}-{direction.name}"
            sec = buckets[intid].get(direction)
            if sec is None:
                sec = sectionclass(sec_id)
                buckets[intid][direction] = sec
            sec.addStation(st)

        intersections: Dict[int, SIntersection] = {}
        for intid, sec_map in buckets.items():
            inter = SIntersection(
                intersection_id=intid,
                sections=sec_map,
                input_station_map=None,
                sig_type=self.sigTypeName
            )
            intersections[intid] = inter

        return intersections

    # ---------- SUMO start (robust) ----------
    def __sumocfg_contains(self, needle: str) -> bool:
        """sumocfg 안에 특정 문자열(보통 add.xml 파일명)이 언급되어 있는지 검사"""
        cfg_path = self.config.sumocfg_path
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                content = f.read()
            return (os.path.basename(needle) in content) or (needle in content)
        except Exception:
            return False

    def __start_sumo(self, include_additional: bool):
        add_abs = os.path.abspath(os.path.join(self.config.scenario_path, self.config.scenario_file))
        cmd = [
            "sumo-gui",
            "-c", self.config.sumocfg_path,
            "--start",
            "--quit-on-end",
            "--seed", "100",
        ]
        if include_additional:
            cmd += ["--additional", add_abs]
        traci.start(cmd)
        traci.simulationStep()

    def __set_SUMO(self):
        add_abs = os.path.abspath(os.path.join(self.config.scenario_path, self.config.scenario_file))
        add_in_cfg = self.__sumocfg_contains(add_abs)

        # 1차 시도: sumocfg에 포함되어 있지 않으면 --additional로 로드
        try:
            self.__start_sumo(include_additional=not add_in_cfg)
        except traci.exceptions.FatalTraCIError:
            # 2차 시도: 반대로 시도 (중복 로드/경로 문제 대비)
            try:
                traci.close(False)
            except Exception:
                pass
            self.__start_sumo(include_additional=add_in_cfg)

        # 신호기 목록
        try:
            self.traffic_light_ids = list(traci.trafficlight.getIDList())
        except Exception:
            self.traffic_light_ids = []

        # detector 로드 검증 (부족하면 즉시 명확히 실패시켜 원인 파악 용이)
        self.__validate_detectors()

    def __validate_detectors(self):
        expected = set(self.__get_detector_ids(self.config))
        try:
            loaded = set(traci.inductionloop.getIDList())
        except Exception:
            loaded = set()
        missing = expected - loaded
        if missing:
            sample = next(iter(missing))
            raise RuntimeError(
                f"{len(missing)} induction loops from '{self.config.scenario_file}' were not loaded by SUMO "
                f"(e.g., '{sample}').\n"
                f"- If your .sumocfg already includes the add.xml, DO NOT pass --additional.\n"
                f"- Otherwise, make sure to pass --additional with the absolute path.\n"
                f"Checked path: {os.path.abspath(os.path.join(self.config.scenario_path, self.config.scenario_file))}"
            )

    # ---------- lifecycle ----------
    def terminate(self):
        self.isStop = True

    def isTermiated(self):
        return self.isStop

    def saveData(self, filename):
        if self.isStop is True:
            print('save data clicked')
            with open(self._rtinfra.setSaveFileName(filename), "wb") as f:
                pickle.dump(self._rtinfra, f)
                print('---file saved at ', self._rtinfra.getFileName())

    # ---------- signal control ----------
    def _refreshSignalPhase(self):
        try:
            if self.logic is not None and self.traffic_light_ids:
                for tl in self.traffic_light_ids:
                    traci.trafficlight.setProgramLogic(tl, self.logic)
        except Exception:
            pass

    def _signalControl(self):
        pass

    # ---------- main loop ----------
    def run_simulation(self):
        print('---- start Simulation (signController : ', self.sigTypeName, ") ----")
        self.step = 0
        self.isStop = False

        while not self.isStop and self.step <= 4800:
            traci.simulationStep()

            try:
                if self.traffic_light_ids:
                    self.logic = traci.trafficlight.getAllProgramLogics(self.traffic_light_ids[0])[0]
                else:
                    self.logic = None
            except Exception:
                self.logic = None

            self._signalControl()

            if self.sigTypeName != "Reinforement Learning based Control":
                self._refreshSignalPhase()

            self._rtinfra.update()

            self.step += 1

        self.isStop = True
        traci.close()

    # ---------- util ----------
    def Check_TrafficLight_State(self):
        try:
            if self.traffic_light_ids:
                return traci.trafficlight.getRedYellowGreenState(self.traffic_light_ids[0])
            else:
                return 'N/A'
        except traci.exceptions.TraCIException:
            return 'N/A'

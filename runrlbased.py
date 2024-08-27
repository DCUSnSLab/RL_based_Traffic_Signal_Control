from RunSimulation import RunSimulation
from stable_baselines3 import DQN
import numpy as np
import traci
from gymnasium import spaces
class RunRLBased(RunSimulation):
    def __init__(self, config, name):
        super().__init__(config, name)
        self.sumo = traci
        self.model_state = False
        self.is_yellow = False
        self.green_phase = 0
        self.delta_time = 5
        self.begin_time = 0
        self.next_action_time = 2
        self.green_phases = []
        self.yellow_dict = {}
        self.all_phases = self.green_phases.copy()
        self.yellow_time = 4
        self.min_green = 5
        self.max_green = 60
        self.time_since_last_phase_change = 0
        self.observations = {}  # observations 초기화
        self.ts_ids = list(traci.trafficlight.getIDList())
        self.current_greentime = 0
        self.tempphase = 0
        if not self.ts_ids:
            raise ValueError("No traffic light IDs found in the SUMO network. Check your SUMO network file.")

        self.id = self.ts_ids[0] if self.ts_ids else None
        if self.id:
            self._build_phases()  # 신호등 단계 초기화
        self.max_queue_capacities = {
            "0": 107,  # 섹션 0의 최대 대기 차량 수
            "1": 88,  # 섹션 1의 최대 대기 차량 수
            "2": 80,  # 섹션 2의 최대 대기 차량 수
            "3": 60,  # 섹션 3의 최대 대기 차량 수
        }
        self.max_CO2_emissions = {
            '0': 318,  # 섹션 0의 CO2 최대 배출량
            '1': 500,  # 섹션 1의 CO2 최대 배출량
            '2': 500,  # 섹션 2의 CO2 최대 배출량
            '3': 242,  # 섹션 3의 CO2 최대 배출량
        }
        if not self.model_state:
            self.model_load()

    def model_load(self):
        model_path = "New_TestWay/RL_Based_ep100_pm_worst_co2.zip"
        self.model = DQN.load(model_path)
        # print("모델 로드")
        self.model_state = True

    def _signalControl(self):
        # print("*"*30)
        # print(self.yellow_dict)

        """Control traffic signals based on the model for each section."""

        if self.time_to_act():
            print('------------------------ start time_to_act', self.step)
            # 각 섹션에 대해 관찰 수행 및 신호등 제어
            observation = self.compute_observation()
            # q_values = self.compute_q_values(observation)  # Compute Q-values

            action, _ = self.model.predict(observation, deterministic=False)  # Choose action based on policy
            # action = np.argmax(q_values)
            print(f"action_signal: {action}")
            self._apply_actions(action)


        self.traffic_update()  # 신호 업데이트 황색신호
    def observation_space(self) -> spaces.Box:
        """Return the observation space based on the Section data."""
        if not self._rtinfra.getSections():
            raise ValueError("Sections have not been initialized. Please initialize sections first.")

        # 임의로 결정된 관찰 벡터의 크기
        num_sections = len(self._rtinfra.getSections())
        observation_size = num_sections * 4  # CO2, Volume, Queue, Green Time

        return spaces.Box(
            low=np.zeros(observation_size, dtype=np.float32),
            high=np.ones(observation_size, dtype=np.float32),
        )
    def compute_observation(self):
        self.queue = []
        co2_emissions = []
        self.queue_density = []
        self.co2_density = []
        # Phase ID (assuming green_phase is an integer and num_green_phases is the total number of phases)
        phase_id = [1 if self.green_phase == i else 0 for i in range(min(self.num_green_phases, 15))]  # One-hot encoding
        min_green = [0 if self.time_since_last_phase_change < self.min_green + self.yellow_time else 1]
        print(phase_id)
        print(min_green)
        for section_id, section in self._rtinfra.getSections().items():
            section_co2_emission, _, traffic_queue, _ = section.collect_data()

            # # print(f"Section {section_id}- co2: {section_co2_emission}, max_co2: {max_CO2_emission}")
            max_co2_capacity = self.max_CO2_emissions.get(section_id)

            section_co2_emission_tmp = section_co2_emission / max_co2_capacity
            section_co2_emission = max(0, section_co2_emission_tmp)
            print(f"Section {section_id}, {section.direction}- nomalized_co2: {section_co2_emission_tmp}, {section_co2_emission}")

            co2_emissions.append(section_co2_emission)

            #max_queue_capacity = self.max_queue_capacities.get(section_id)

            # # # print(f"Section {section_id}- traffic_queue: {traffic_queue}, max_queue_capacity: {max_queue_capacity}")
            # normalized_queue = traffic_queue / max_queue_capacity
            # self.queue_density.append(max(0, 1 - normalized_queue))
            # # print(f"Section {section_id}- nomalized_queue: {self.queue_density}")
            # # print("co2_emissions:", self.co2_emissions)
        # observation = self.co2_density
        newco2 = []
        newco2.append(co2_emissions[2])
        newco2.append(co2_emissions[3])
        newco2.append(co2_emissions[0])
        newco2.append(co2_emissions[1])
        observation = phase_id + min_green + newco2

        if len(observation) < 16:
            observation.extend([0] * (16 - len(observation)))

        observation = np.array(observation, dtype=np.float32)
        print("pre_observation: ", observation)
        # # print("observation: ", observation)
        return observation
    def _get_num_phases(self, ts_id):
        """Return the number of phases for a given traffic signal ID."""
        return len(self.sumo.trafficlight.getRedYellowGreenState(ts_id))  # 신호 상태 문자열 길이를 통해 단계 수 반환

    def traffic_update(self):
        self.time_since_last_phase_change += 1
        # print(f"traffic_update에서 마지막 신호 변경 이후 경과 시간: {self.time_since_last_phase_change}")
        if self.is_yellow and self.time_since_last_phase_change == self.yellow_time:
            # print(f"황색 신호가 True이고 traffic_update의 이전 신호 변경 시간 == 황색시간")
            # print(f"교통 신호 ID {self.ts_ids[0]}를 상태 {self.all_phases[self.green_phase].state}로 설정합니다.")
            self.sumo.trafficlight.setRedYellowGreenState(self.ts_ids[0], self.all_phases[self.green_phase].state)

            self.is_yellow = False

    # def _apply_actions(self, actions):
    #     """Apply traffic signal actions."""
    #     if self.time_to_act():  # 행동할 시간이 되었는지 확인
    #         self.set_next_phase(actions)
    #         # print("행동할 시간이 아닙니다. 다음 시간에 시도합니다.")
    #         self.traffic_update()
    #     else:
    #         # print("신호 변경이 성공적으로 적용되었습니다.")
    def _apply_actions(self, actions):
        self.set_next_phase(actions)

    def time_to_act(self):
        current_time = self.sumo.simulation.getTime()
        # print(f"행동할 시간인지 확인 중. 현재 시간: {current_time}, 다음 행동 시간: {self.next_action_time}")
        return self.next_action_time == current_time

    def set_next_phase(self, new_phase: int):
        """Set the next traffic signal phase."""
        new_phase = int(new_phase)
        print(f"기존 신호: {self.green_phase}")
        print(f"새로운 신호: {new_phase}")
        if self.green_phase == new_phase or self.time_since_last_phase_change < self.yellow_time + self.min_green:
            print(f"마지막 신호 변경 이후 경과 시간: {self.time_since_last_phase_change} < 황색 신호 시간: {self.yellow_time} + 최소 녹색 신호 시간: {self.min_green}")
            print("신호 변화 조건 불충족")
            if self.green_phase >= len(self.all_phases):
                # print(f"오류: 현재 녹색 신호 단계 {self.green_phase}가 범위를 벗어났습니다.")
                return
            tls_id = self.ts_ids[0] if self.ts_ids else None
            if tls_id is None:
                return
            # print(f"교통 신호 ID {tls_id}를 상태 {self.all_phases[self.green_phase].state}로 설정합니다.")
            self.sumo.trafficlight.setRedYellowGreenState(tls_id, self.all_phases[self.green_phase].state)
            self.next_action_time = self.sumo.simulation.getTime() + self.delta_time
            self.current_greentime += self.delta_time
            print(f"다음 작업 시간 설정: {self.next_action_time}, greentime 유지시간 : {self.current_greentime}")

        else:
            yellow_index = self.yellow_dict.get((self.green_phase, new_phase), None)
            if yellow_index is None or yellow_index >= len(self.all_phases):
                print("유효한 황색 신호 단계가 없습니다.")
                return
            tls_id = self.ts_ids[0] if self.ts_ids else None
            if tls_id is None:
                return
            print(f"교통 신호 ID {tls_id}를 노란 신호 단계 상태 {self.all_phases[yellow_index].state}로 설정합니다.")
            self.sumo.trafficlight.setRedYellowGreenState(tls_id, self.all_phases[yellow_index].state)
            self.green_phase = new_phase
            print(f"현재 녹색 신호: {self.green_phase}")
            self.next_action_time = self.sumo.simulation.getTime() + self.delta_time
            print(f"현재 next_action_time은 {self.sumo.simulation.getTime() + self.delta_time}입니다")
            self.is_yellow = True
            self.time_since_last_phase_change = 0
            self.current_greentime = 0
            # print(f"초록 신호 단계를 {self.green_phase}으로 업데이트했으며, 다음 작업 시간을 {self.next_action_time}으로 설정했습니다.")

    def _build_phases(self):
        """Initialize the traffic light phases."""
        phases = self.sumo.trafficlight.getAllProgramLogics(self.ts_ids[0])[0].phases
        self.green_phases = []
        self.yellow_dict = {}
        self.all_phases = []

        for phase in phases:
            state = phase.state
            if "y" not in state and (state.count("r") + state.count("s") != len(state)):
                self.green_phases.append(self.sumo.trafficlight.Phase(60, state))
        self.num_green_phases = len(self.green_phases)
        # # print("green_phases: ", self.green_phases)
        self.all_phases = self.green_phases.copy()
        for i, p1 in enumerate(self.green_phases):
            for j, p2 in enumerate(self.green_phases):
                if i == j:
                    continue
                yellow_state = ""
                for s in range(len(p1.state)):
                    if (p1.state[s] == "G" or p1.state[s] == "g") and (p2.state[s] == "r" or p2.state[s] == "s"):
                        yellow_state += "y"
                    else:
                        yellow_state += p1.state[s]
                self.yellow_dict[(i, j)] = len(self.all_phases)
                self.all_phases.append(self.sumo.trafficlight.Phase(self.yellow_time, yellow_state))
        programs = self.sumo.trafficlight.getAllProgramLogics(self.ts_ids[0])
        logic = programs[0]
        logic.type = 0
        logic.phases = self.all_phases
        self.sumo.trafficlight.setProgramLogic(self.ts_ids[0], logic)
        self.sumo.trafficlight.setRedYellowGreenState(self.ts_ids[0], self.all_phases[0].state)

        #traci.trafficlight.setPhase("TLS_0", 1)


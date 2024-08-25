from RunSimulation import RunSimulation
from stable_baselines3 import DQN
from typing import Union, List
import numpy as np
import traci
import torch
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
        self.next_action_time = 0
        self.green_phases = []
        self.yellow_dict = {}
        self.all_phases = self.green_phases.copy()
        self.yellow_time = 5
        self.min_green = 32
        self.max_green = 60
        self.time_since_last_phase_change = 0
        self.observations = {}  # observations 초기화
        self.ts_ids = list(traci.trafficlight.getIDList())
        if not self.ts_ids:
            raise ValueError("No traffic light IDs found in the SUMO network. Check your SUMO network file.")

        # self.id = self.ts_ids[0] if self.ts_ids else None
        # if self.id:
        #     self._build_phases()  # 신호등 단계 초기화

        self.id = self.ts_ids[0]
        self._build_phases()

        self.max_queue_capacities = {
            "0": 107,  # 섹션 0의 최대 대기 차량 수
            "1": 88,  # 섹션 1의 최대 대기 차량 수
            "2": 126,  # 섹션 2의 최대 대기 차량 수
            "3": 119,  # 섹션 3의 최대 대기 차량 수
        }
        self.max_CO2_emissions = {
            '0': 318,  # 섹션 0의 CO2 최대 배출량
            '1': 394,  # 섹션 1의 CO2 최대 배출량
            '2': 297,  # 섹션 2의 CO2 최대 배출량
            '3': 242,  # 섹션 3의 CO2 최대 배출량
        }
    def model_load(self):
        model_path = "New_TestWay/RL_Based_ep100"
        self.model = DQN.load(model_path)
        print("Model loaded")
        self.model_state = True

    def _signalControl(self):
        # print("*"*30)
        """Control traffic signals based on the model for each section."""
        if not self.model_state:
            self.model_load()

        # 각 섹션에 대해 관찰 수행 및 신호등 제어
        observation = self.compute_observation()
        q_values = self.compute_q_values(observation)  # Compute Q-values

        action, _ = self.model.predict(observation, deterministic=False)  # Choose action based on policy
        # action = np.argmax(q_values)
        print(f"action: {action}")

        self.traffic_step(action)
    # def observation_space(self) -> spaces.Box:
    #     """Return the observation space based on the Section data."""
    #     if not self.rtInfra.getSections():
    #         raise ValueError("Sections have not been initialized. Please initialize sections first.")
    #
    #     # num_sections의 값을 확인하고 조정합니다. 여기서는 예시로 8을 사용합니다.
    #     num_sections = 4  # 예시 값, 실제 값에 맞게 조정 필요
    #     observation_size = num_sections * 4  # CO2, Volume, Queue, Green Time
    #
    #     # 관찰 벡터의 크기를 모델이 기대하는 크기로 맞추기 위해 패딩합니다.
    #     desired_size = 35
    #     if observation_size < desired_size:
    #         observation_size = desired_size
    #
    #     return spaces.Box(
    #         low=np.zeros(observation_size, dtype=np.float32),
    #         high=np.ones(observation_size, dtype=np.float32),
    #     )
    def observation_space(self) -> spaces.Box:
        """Return the observation space based on the Section data."""
        if not self.rtInfra.getSections():
            raise ValueError("Sections have not been initialized. Please initialize sections first.")

        # 임의로 결정된 관찰 벡터의 크기
        num_sections = len(self.rtInfra.getSections())
        observation_size = num_sections * 4  # CO2, Volume, Queue, Green Time

        return spaces.Box(
            low=np.zeros(observation_size, dtype=np.float32),
            high=np.ones(observation_size, dtype=np.float32),
        )

    def get_Section_density(self) -> List[float]:
        """Returns the density [0,1] of the vehicles in the incoming lanes of the sections."""
        densities = []

        for section_id, section in self.rtInfra.getSections().items():
            co2, volume, traffic_queue, green_time = section.collect_data()
            # print("traffic_queue:", traffic_queue)
            # 데이터 출력
            # print(f"collect_data : {co2}, {volume}, {traffic_queue}, {green_time}")
            # print(f"get_Section_density_traffic_queue for section {section_id}: {traffic_queue}")

            # 각 섹션의 최대 대기 차량 수를 가져옵니다
            max_queue_capacity = self.max_queue_capacities.get(section_id, 100)
            # print(f"Max Queue Capacity for section {section_id}: {max_queue_capacity}")
            if max_queue_capacity > 0:
                # 밀도 계산
                density = min(1, traffic_queue / max_queue_capacity)
            else:
                # capacity가 0인 경우 밀도를 0으로 설정
                density = 0

            # 디버깅을 위한 밀도 출력
            # print(f"Density for section {section_id}: {density}")

            densities.append(density)

        # print(f"Final densities: {densities}")  # 전체 밀도 리스트 출력

        return densities

    # def compute_observation(self):
        # """Compute the observation for a given section."""
        # self.queue = []
        # try:
        #     # Phase ID
        #     phase_id = [1 if self.green_phase == i else 0 for i in range(self.num_green_phases)]
        #     # print("phase_id: ", phase_id)
        #     # Minimum green time flag
        #     min_green = [0 if self.time_since_last_phase_change < self.min_green + self.yellow_time else 1]
        #     # print("min_green: ", min_green)
        #     # Density
        #     density = self.get_Section_density()
        #     # print("density: ", density)
        #     # Check density length and pad if necessary
        #     desired_density_length = 4
        #     if len(density) < desired_density_length:
        #         density = density + [0] * (desired_density_length - len(density))
        #         # print("len(density) < desired_density_length: ", density)
        #     elif len(density) > desired_density_length:
        #         density = density[:desired_density_length]
        #         # print("len(density) > desired_density_length: ", density)
        #     # Queue calculation (adjust this line according to the actual method or attribute)
        #
        #     for section_id, section in self.rtInfra.getSections().items():
        #         co2, volume, traffic_queue, green_time = section.collect_data()
        #         self.queue = traffic_queue
        #     # print("queue: ", self.queue)
        #     # Create the observation array
        #     observation = np.array(phase_id + min_green + density + [self.queue], dtype=np.float32)
        #     # print("observation: ", observation)
        #     # Padding to ensure the observation size is 35
        #     desired_size = 16
        #     if len(observation) < desired_size:
        #         observation = np.pad(observation, (0, desired_size - len(observation)), mode='constant')
        #         # print("len(observation) < desired_size: ", observation)
        #     elif len(observation) > desired_size:
        #         observation = observation[:desired_size]
        #         # print("len(observation) > desired_size: ", observation)
        #     # for section_id, section in self.rtInfra.getSections().items():
        #     #     self.observations[section_id] = observation
        #     #     print("self.observations[section_id] = observation: ", self.observations[section_id])
        #     return observation
        # except IndexError as e:
        #     print(f"IndexError encountered: {e}")
        #     return np.zeros(self.observation_space().shape, dtype=np.float32)
    def compute_observation(self):
        self.queue = []
        self.co2_emissions = []
        self.queue_density = []
        self.co2_density = []
        # Phase ID (assuming green_phase is an integer and num_green_phases is the total number of phases)
        phase_id = [1 if self.green_phase == i else 0 for i in
                    range(min(self.num_green_phases, 15))]  # One-hot encoding
        min_green = [0 if self.time_since_last_phase_change < self.min_green + self.yellow_time else 1]
        for section_id, section in self.rtInfra.getSections().items():
            section_co2_emission, _, traffic_queue, _ = section.collect_data()
            max_CO2_emission = self.max_CO2_emissions.get(section_id)
            # print(f"Section {section_id}- co2: {section_co2_emission}, max_co2: {max_CO2_emission}")
            normalized_co2 = section_co2_emission / max_CO2_emission
            self.co2_density.append(max(0, 1 - normalized_co2))
            # print(f"Section {section_id}- nomalized_co2: {self.co2_density}")

            max_queue_capacity = self.max_queue_capacities.get(section_id)
            # print(f"Section {section_id}- traffic_queue: {traffic_queue}, max_queue_capacity: {max_queue_capacity}")
            normalized_queue = traffic_queue / max_queue_capacity
            self.queue_density.append(max(0, 1 - normalized_queue))
            # print(f"Section {section_id}- nomalized_queue: {self.queue_density}")
            # print("co2_emissions:", self.co2_emissions)
        observation = phase_id + min_green + self.co2_density + self.queue_density
        # observation = phase_id + min_green + self.co2_emissions + self.queue
        # print("pre_observation: ", observation)
        if len(observation) < 16:
            observation.extend([0] * (16 - len(observation)))

        observation = np.array(observation, dtype=np.float32)
        # print("observation: ", observation)
        return observation
    def _get_num_phases(self, ts_id):
        """Return the number of phases for a given traffic signal ID."""
        return len(self.sumo.trafficlight.getRedYellowGreenState(ts_id))  # 신호 상태 문자열 길이를 통해 단계 수 반환

    def traffic_update(self):
        self.time_since_last_phase_change += 1
        if self.is_yellow and self.time_since_last_phase_change == self.yellow_time:
            # 교통 신호등 ID가 리스트가 아니라 문자열로 전달되도록 수정
            tls_id = self.ts_ids[0] if self.ts_ids else None
            if tls_id:
                self.sumo.trafficlight.setRedYellowGreenState(tls_id, self.all_phases[self.green_phase].state)
                self.is_yellow = False

    def traffic_step(self, action: Union[dict, int, None]):
        self._apply_actions(action)
        self._run_steps()

    # def _apply_actions(self, actions):
    #     """Apply traffic signal actions."""
    #     # print("actions :", actions)
    #     if self.time_to_act:
    #         self.set_next_phase(actions)

    def _apply_actions(self, actions):
        """Apply traffic signal actions."""
        if self.time_to_act:
            self.set_next_phase(actions)
            self.traffic_update()

    def time_to_act(self):
        """Returns True if the traffic signal should act in the current step."""
        return self.next_action_time == self.sumo.simulation.getTime()

    def _run_steps(self):
        """Run simulation steps until it's time to act."""
        time_to_act = False
        while not time_to_act:
            self.sumo.simulationStep()
            self.traffic_update()
            # print("%" * 50)
            # logic = traci.trafficlight.getAllProgramLogics("TLS_0")[0]
            # print(logic)
            # print("%" * 50)
            if self.check_time_to_act():
                time_to_act = True

    def check_time_to_act(self):
        """Check if it's time to act for the given traffic signal."""
        current_time = self.sumo.simulation.getTime()
        return current_time >= self.next_action_time

    def set_next_phase(self, new_phase: int):
        """Set the next traffic signal phase."""
        new_phase = int(new_phase)
        # print(f"Attempting to set new phase: {new_phase}")
        if self.green_phase == new_phase or self.time_since_last_phase_change < self.yellow_time + self.min_green:
            print(f"Currently green phase: {self.green_phase}")
            # print(f"time_since_last_phase_change: ", self.time_since_last_phase_change,  "self.yellow_time", self.yellow_time, "self.min_green", self.min_green)

            # print(f"Setting traffic light ID {tls_id} to state {self.all_phases[self.green_phase].state}")
            self.sumo.trafficlight.setRedYellowGreenState(self.id, self.all_phases[self.green_phase].state)
            self.next_action_time = self.sumo.simulation.getTime() + self.delta_time
        else:

            self.sumo.trafficlight.setRedYellowGreenState(
                self.id, self.all_phases[self.yellow_dict[(self.green_phase, new_phase)]].state
            )
            self.green_phase = new_phase
            self.next_action_time = self.sumo.simulation.getTime() + self.delta_time
            self.is_yellow = True
            self.time_since_last_phase_change = 0
            # print(f"Updated green phase to {self.green_phase}, next action time set to {self.next_action_time}")
        print("*" * 50)
        print("next action time: ", self.next_action_time)
        print("time since last phase change", self.time_since_last_phase_change)
        print("*" * 50)

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
        # print("green_phases: ", self.green_phases)
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

    def compute_q_values(self, observation):
        observation = np.array(observation).astype(np.float32)  # Ensure correct dtype
        observation = torch.tensor(observation).float().unsqueeze(0)  # Add batch dimension
        with torch.no_grad():
            # predict returns action and q_values (for DQN models)
            action, q_values = self.model.predict(observation, deterministic=False)
            q_values = self.model.q_net(observation).numpy().flatten()  # Use q_net to get Q-values directly
        # print("Q-values:", q_values)  # Print Q-values for debugging
        # print("action: ", action)
        return q_values
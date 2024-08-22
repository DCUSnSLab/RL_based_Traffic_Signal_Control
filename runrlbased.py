from RunSimulation import RunSimulation
from stable_baselines3 import DQN
from typing import Union, List
import numpy as np
import traci

class RunRLBased(RunSimulation):
    def __init__(self, config, name):
        super().__init__(config, name)
        self.sumo = traci
        self.model_state = False
        self.is_yellow = False
        self.green_phase = 0
        self.delta_time = 1
        self.begin_time = 0
        self.next_action_time = 0
        self.green_phases = []
        self.yellow_dict = {}
        self.all_phases = self.green_phases.copy()
        self.yellow_time = 4
        self.min_green = 5
        self.max_green = 60
        self.time_since_last_phase_change = 0
        self.observations = {}  # observations 초기화
        self.ts_ids = list(traci.trafficlight.getIDList())

        if not self.ts_ids:
            raise ValueError("No traffic light IDs found in the SUMO network. Check your SUMO network file.")

        self.id = self.ts_ids[0] if self.ts_ids else None
        if self.id:
            self._build_phases()  # 신호등 단계 초기화
    def model_load(self):
        model_path = "New_TestWay/RL_Based_ep30"
        self.model = DQN.load(model_path)
        print("Model loaded")
        self.model_state = True

    def _signalControl(self):
        """Control traffic signal based on model."""
        if not self.model_state:
            self.model_load()
        observations = self._compute_observations()
        for ts_id, observation in observations.items():
            action, _ = self.model.predict(observation, deterministic=True)
            self.traffic_step(action)
            # print("action:", action)
        self._run_steps()

    def _compute_observations(self):
        """현재 관측값을 계산하고 반환합니다."""
        self.observations = {}
        for ts_id in self.ts_ids:
            if not self.sumo.trafficlight.getIDList():
                # print("if not self.sumo.trafficlight.getIDList()")
                continue
            # print("ts_id: ", ts_id)
            # 신호등의 현재 상태를 가져옵니다
            num_phases = self._get_num_phases(ts_id)
            # print("num_phases: ", num_phases)
            phase_id = [1 if self.sumo.trafficlight.getPhase(ts_id) == i else 0 for i in range(num_phases)]
            # print("phase_id: ", phase_id)
            min_green = [0 if self.time_since_last_phase_change < self.min_green + self.yellow_time else 1]
            # print("min_green: ", min_green)
            # 섹션 데이터 수집
            queue = []
            density = []
            for section_id, section in self.rtInfra.getSections().items():
                try:
                    section_co2_emission, section_volume, traffic_queue = section.collect_data()
                    # 교통 대기열 정보를 추가합니다
                    density.append(section_volume)
                    queue.append(traffic_queue)
                except IndexError as e:
                    print(f"Error collecting data from section {section_id}: {e}")
                    # 빈 대기열을 추가하거나 기본값을 사용할 수 있습니다
                    queue.append(0)  # 기본값으로 0을 사용
            # print("density: ", density)
            # print("queue: ", queue)
            # 관측값 배열을 생성합니다
            # 관측값의 길이를 확인하고 부족한 부분을 0으로 채웁니다
            # phase_id의 길이와 min_green의 길이를 합산한 후 queue를 추가하여 길이를 맞춥니다
            required_length = 35
            current_length = len(phase_id) + len(min_green) + len(queue) + len(density)
            # print("current_length: ", current_length)
            if current_length < required_length:
                # print("current_length < required_length")
                queue.extend([0] * (required_length - current_length))  # 부족한 부분을 0으로 채움
            # print("phase_id: ", phase_id)
            # print("min_green: ", min_green)
            # print("queue: ", queue)
            # print("density: ", density)
            observation = np.array(phase_id + min_green + queue + density, dtype=np.float32)
            # print("observation = np.array: ", observation)
            # 관측값 길이 체크
            if observation.shape[0] != required_length:
                print(f"Warning: Observation length is {observation.shape[0]}, expected {required_length}.")
            self.observations[ts_id] = observation
            # print("self.observations[ts_id]: ", self.observations[ts_id])
        return {ts_id: obs.copy() for ts_id, obs in self.observations.items()}

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

    def _apply_actions(self, actions):
        """Apply traffic signal actions."""
        # print("actions :", actions)
        self.set_next_phase(actions)

    def _run_steps(self):
        """Run simulation steps until it's time to act."""
        time_to_act = False
        while not time_to_act:
            self.sumo.simulationStep()
            for ts_id in self.sumo.trafficlight.getIDList():

                self.traffic_update()
                if self._check_time_to_act(ts_id):
                    time_to_act = True

    def _check_time_to_act(self, ts_id):
        """Check if it's time to act for the given traffic signal."""
        current_time = self.sumo.simulation.getTime()
        return current_time >= self.next_action_time

    def traffic_signal_update(self):
        """Update traffic signal status."""
        self.time_since_last_phase_change += 1
        if self.is_yellow and self.time_since_last_phase_change == self.yellow_time:
            self.sumo.trafficlight.setRedYellowGreenState(self.ts_ids, self.all_phases[self.green_phase].state)
            self.is_yellow = False

    def set_next_phase(self, new_phase: int):
        """Set the next traffic signal phase."""
        new_phase = int(new_phase)
        # print(f"Attempting to set new phase: {new_phase}")
        if self.green_phase == new_phase or self.time_since_last_phase_change < self.yellow_time + self.min_green:
            # print(f"Currently green phase: {self.green_phase}")
            # print(f"time_since_last_phase_change: ", self.time_since_last_phase_change,  "self.yellow_time", self.yellow_time, "self.min_green", self.min_green)
            if self.green_phase >= len(self.all_phases):
                # print(f"Error: Current green_phase {self.green_phase} is out of range.")
                return
            tls_id = self.ts_ids[0] if self.ts_ids else None
            if tls_id is None:
                return
            print(f"Setting traffic light ID {tls_id} to state {self.all_phases[self.green_phase].state}")
            self.sumo.trafficlight.setRedYellowGreenState(tls_id, self.all_phases[self.green_phase].state)
            self.next_action_time = self.sumo.simulation.getTime() + self.delta_time

        else:
            yellow_index = self.yellow_dict.get((self.green_phase, new_phase), None)
            if yellow_index is None or yellow_index >= len(self.all_phases):
                return
            tls_id = self.ts_ids[0] if self.ts_ids else None
            if tls_id is None:
                return
            self.sumo.trafficlight.setRedYellowGreenState(
                tls_id, self.all_phases[yellow_index].state
            )
            self.green_phase = new_phase
            self.next_action_time = self.sumo.simulation.getTime() + self.delta_time
            self.is_yellow = True
            self.time_since_last_phase_change = 0
            # print(f"Updated green phase to {self.green_phase}, next action time set to {self.next_action_time}")

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
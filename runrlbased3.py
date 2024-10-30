import traci
from stable_baselines3 import DQN
from stable_baselines3.common.callbacks import BaseCallback

from Infra import Config_SUMO, Infra, TOTAL_RESULT, SSection
from RunSimulation import RunSimulation
from sumo_rl import SumoEnvironment
import numpy as np
from gymnasium import spaces
from sumo_rl import ObservationFunction, TrafficSignal

class CustomSumoEnvironment(SumoEnvironment):
    def __init__(self, simInfra, **kwargs):
        super().__init__(**kwargs)
        self._cust_step = 0
        self._cust_infra:Infra = simInfra

    def _compute_reward(self):
        total_co2_emission = 0
        for veh_id in traci.vehicle.getIDList():
            total_co2_emission += traci.vehicle.getCO2Emission(veh_id)

        reward = -total_co2_emission
        return reward

    def getCustInfra(self):
        return self._cust_infra

    def _sumo_step(self):
        self.sumo.simulationStep()
        self._cust_infra.update()
        self._cust_step += 1


class CO2ObservationFunction(ObservationFunction):
    """CO2-based observation function for traffic signals."""

    def __init__(self, ts: TrafficSignal):
        """Initialize CO2 observation function."""
        super().__init__(ts)

    def __call__(self) -> np.ndarray:
        self._custInfra: Infra = self.ts.env.getCustInfra()

        total_co2_emission = 0
        co2_emissions = []
        # for veh_id in traci.vehicle.getIDList():
        #     total_co2_emission += traci.vehicle.getCO2Emission(veh_id)
        total_co2_emission = self._custInfra.getTotalCO2mg()
        """Return the CO2-based observation."""
        phase_id = [1 if self.ts.green_phase == i else 0 for i in range(self.ts.num_green_phases)]  # one-hot encoding
        min_green = [0 if self.ts.time_since_last_phase_change < self.ts.min_green + self.ts.yellow_time else 1]
        co2_emissions.append(total_co2_emission)
        # co2_emissions = self.ts.get_lanes_co2_emission()
        observation = np.array(phase_id + min_green + co2_emissions, dtype=np.float32)
        print("observation: ", observation)
        return observation

    def observation_space(self) -> spaces.Box:
        """Return the observation space."""
        return spaces.Box(
            low=np.zeros(self.ts.num_green_phases + 1 + 1, dtype=np.float32),
            high=np.ones(self.ts.num_green_phases + 1 + 1, dtype=np.float32),
        )

# 콜백 클래스를 정의하여 학습 결과를 매번 출력하도록 설정
class EveryStepCallback(BaseCallback):
    def __init__(self, verbose=0):
        super(EveryStepCallback, self).__init__(verbose)

    def _on_step(self) -> bool:
        # if self.verbose > 0:
        #     print(f"Step: {self.num_timesteps}, Reward: {self.locals['rewards'][-1]}")
        return True

class RunRLBased3(RunSimulation):
    def __init__(self, config, name):
        super().__init__(config, 'RL_DQL', isExternalSignal=True)
        self.model = DQN.load("dqn_legacy_episode_100.zip")
        self.prevAction = -1
        self.env = CustomSumoEnvironment(
            net_file=self.config.scenario_file_rl,
            single_agent=True,
            route_file=self.config.route_file_rl,
            use_gui=True,
            yellow_time=4,
            min_green=5,
            max_green=120,
            sumo_seed=100,
            #observation_class=CO2ObservationFunction,
            simInfra=self.getInfra()
        )
    def preinit(self):
        pass

    def setSectionSignal(self, action):
        #E(2) W(3) S(0) N(1)
        #S N E W
        bCorrection = [2, 3, 0 ,1]
        program = traci.trafficlight.getAllProgramLogics('TLS_0')[0]
        sections = self.getInfra().getSections()
        if self.prevAction == action:
            current_dur = sections[str(bCorrection[action])].getCurrentGreenTime() + self.env.delta_time
        else:
            current_dur = self.env.delta_time

        sections[str(bCorrection[action])].setGreenTime(current_dur, None)
        self.prevAction = action

        # for i, phase in enumerate(program.phases):
        #     if i > 3:
        #         break
        #     print(f"Phase {i}: Duration = {phase.duration} seconds, State = {phase.state}, {action}")

    def run_simulation(self):
        obs, _ = self.env.reset()
        done = False
        total_reward = 0
        step = 0
        maxstep = 11700 / self.env.delta_time
        self.isStop = False

        while self.isStop is not True and step <= maxstep:
            action, _states = self.model.predict(obs, state=None, deterministic=False)
            obs, reward, done, truncated, info = self.env.step(action)
            total_reward += reward
            step += 1
            self.setSectionSignal(action)

        self.isStop = True
        traci.close()
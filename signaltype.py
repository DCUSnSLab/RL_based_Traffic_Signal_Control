from enum import Enum

from Infra import Config_SUMO
from RunSimulation import RunSimulation
from run_centralized_rl_based import RunCentralizedDQNControl

class SignalMode(Enum):
    Static = (lambda: RunSimulation(config=Config_SUMO(), name="Static Control"), "Static Control")
    Centralized_DQN = (lambda: RunCentralizedDQNControl(config=Config_SUMO(), name="Centralized DQN"), "Centralized DQN")

    @classmethod
    def from_string(cls, string_value):
        for mode in cls:
            if mode.value[1] == string_value:
                return mode
        raise ValueError(f"{string_value} is not a valid SignalMode value")
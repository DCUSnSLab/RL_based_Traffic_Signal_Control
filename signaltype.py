from enum import Enum

from Infra import Config_SUMO
from runactuated import RunActuated
from RunSimulation import RunSimulation
from runactuatedocc import RunActuatedOCC
from rundilemazone import RunDilemaZone
from runrlbased import RunRLBased


class SignalMode(Enum):
    Static = (lambda: RunSimulation(config=Config_SUMO(), name="Static Control"), "Static Control")
    Actuated = (lambda: RunActuated(config=Config_SUMO(), name="Actuated Control"), "Actuated Control")
    ActuatedOCC = (lambda: RunActuatedOCC(config=Config_SUMO(), name="Actuated Control OCC"), "Actuated Control OCC")
    RLBased = (lambda: RunRLBased(config=Config_SUMO(), name="Reinforement Learning based Control"), "Reinforement Learning based Control")
    DilemaZone = (lambda: RunDilemaZone(config=Config_SUMO(), name="DilemaZone Control"), "DilemaZone Control")

    @classmethod
    def from_string(cls, string_value):
        for mode in cls:
            if mode.value[1] == string_value:
                return mode
        raise ValueError(f"{string_value} is not a valid SignalMode value")
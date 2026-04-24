from enum import Enum

from controllers.runactuated import RunActuated
from controllers.runactuatedBocc import RunActuatedBOCC
from controllers.runactuatedocc import RunActuatedOCC
from controllers.rundilemazone import RunDilemaZone
from controllers.runrlbased import RunRLBased
from controllers.runrlbased2 import RunRLBased2
from controllers.runrlbased3 import RunRLBased3
from controllers.runrlbased4 import RunRLBased4
from controllers.runrlbased5 import RunRLBased5
from core.Infra import Config_SUMO
from core.RunSimulation import RunSimulation


class SignalMode(Enum):
    Static = (lambda: RunSimulation(config=Config_SUMO(), name="Static Control"), "Static Control")
    Actuated = (lambda: RunActuated(config=Config_SUMO(), name="Actuated Control"), "Actuated Control")
    ActuatedOCC = (lambda: RunActuatedOCC(config=Config_SUMO(), name="Actuated Control OCC"), "Actuated Control OCC")
    ActuatedBOCC = (lambda: RunActuatedBOCC(config=Config_SUMO(), name="Actuated Control OCC"), "Actuated Control Bound OCC")
    RLBased = (lambda: RunRLBased(config=Config_SUMO(), name="Reinforement Learning based Control"), "Reinforement Learning based Control")
    RLBased2 = (lambda: RunRLBased2(config=Config_SUMO(), name="Reinforement Learning based Control"),"Reinforement Learning based Control 2")
    RLBased3 = (lambda: RunRLBased3(config=Config_SUMO(), name="Reinforement Learning based Control"),"Reinforement Learning based Control 3")
    RLBased4 = (lambda: RunRLBased4(config=Config_SUMO(), name="Reinforement Learning based Control"), "Reinforement Learning based Control 4")
    RLBased5 = (lambda: RunRLBased5(config=Config_SUMO(), name="Reinforement Learning based Control"), "Reinforement Learning based Control 5")
    DilemaZone = (lambda: RunDilemaZone(config=Config_SUMO(), name="DilemaZone Control"), "DilemaZone Control")

    @classmethod
    def from_string(cls, string_value):
        for mode in cls:
            if mode.value[1] == string_value:
                return mode
        raise ValueError(f"{string_value} is not a valid SignalMode value")

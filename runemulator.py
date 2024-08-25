import pickle
from typing import List

from Infra import Infra
from inframanager import InfraManager


class RunEmulator(InfraManager):
    def __init__(self, filenames: List[str]):
        super().__init__(None, None, filenames=filenames)

    def preinit(self):
        pass
        # self.filenames: List[str] = filenames
        # self.filenames = list()
        # self.filenames.append("Actuated Control OCC_20240824040910.data")
        # self.filenames.append("Static Control_20240824040548.data")

    def _make_Infra(self) -> List[Infra]:
        infras = list()
        if self.filenames is not None and len(self.filenames) > 0:
            for fn in self.filenames:
                infras.append(self.loadData(fn))

        return infras

    def loadData(self, fileName):
        with open(fileName, "rb") as f:
            loadedInfra = pickle.load(f)

        print("Loaded Infra:", loadedInfra.sigType, loadedInfra.getSavedTime())

        return loadedInfra
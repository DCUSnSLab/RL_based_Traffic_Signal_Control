from abc import abstractmethod
import numpy as np
from gymnasium import spaces
from typing import List
from traffic_signal import TrafficSignal, Section, Config_SUMO, Station, Detector
class ObservationFunction:
    """Abstract base class for observation functions."""

    def __init__(self, ts: TrafficSignal):
        """Initialize observation function."""
        self.ts = ts
        self.sections={}
        self.section_objects = {section_id: Section(section_id, stations) for section_id, stations in self.sections.items()}
        self.max_queue_capacities = {
            0: 107,  # 섹션 0의 최대 대기 차량 수
            1: 88,  # 섹션 1의 최대 대기 차량 수
            2: 126,  # 섹션 2의 최대 대기 차량 수
            3: 119,  # 섹션 3의 최대 대기 차량 수
        }
    @abstractmethod
    def __call__(self):
        """Subclasses must override this method."""
        pass

    @abstractmethod
    def observation_space(self):
        """Subclasses must override this method."""
        pass
class DefaultObservationFunction(ObservationFunction):
    """Default observation function for traffic signals."""

    def __init__(self, ts: TrafficSignal):
        """Initialize default observation function."""
        super().__init__(ts)

    def __call__(self) -> np.ndarray:
        """Compute the observation for a given section."""
        self.queue = []
        try:
            # Phase ID (assuming green_phase is an integer and num_green_phases is the total number of phases)
            phase_id = [1 if self.ts.green_phase == i else 0 for i in
                        range(min(self.ts.num_green_phases, 15))]  # One-hot encoding
            min_green = [0 if self.ts.time_since_last_phase_change < self.ts.min_green + self.ts.yellow_time else 1]

            # Density calculation (assumes get_Section_density returns a list of densities)
            density = self.get_Section_density()
            if density is None:
                density = [0] * 4  # Replace with a list of zeros of the expected length

            # CO2 Emission calculation
            co2_emissions = []
            for section_id, section in self.section_objects.items():
                section_co2_emission, _, _, _ = section.collect_data()
                co2_emissions.append(section_co2_emission)
            if len(co2_emissions) != 4:
                co2_emissions = [0] * 4  # Ensure the list has the correct length

            # Queue calculation (fetching the latest value from deque)
            for section_id, section in self.section_objects.items():
                _, _, traffic_queue, _ = section.collect_data()
                self.queue = traffic_queue
            flattened_queue = self.queue if isinstance(self.queue, list) else list(self.queue)

            # Combine all parts into one list
            observation = phase_id + min_green + density + co2_emissions + flattened_queue

            # Ensure the observation has exactly 16 elements
            if len(observation) < 16:
                observation.extend([0] * (16 - len(observation)))

            # Convert the observation to a numpy array
            observation = np.array(observation, dtype=np.float32)
            return observation
        except IndexError as e:
            print(f"IndexError encountered: {e}")
            return np.zeros(self.observation_space().shape, dtype=np.float32)

    def observation_space(self) -> spaces.Box:
        """Return the observation space."""
        return spaces.Box(
            low=np.zeros(16, dtype=np.float32),
            high=np.ones(16, dtype=np.float32),
        )

    def get_Section_density(self) -> List[float]:
        """Returns the density [0,1] of the vehicles in the incoming lanes of the sections."""
        densities = []
        for section_id, section in self.section_objects.items():
            _, _, traffic_queue, _ = section.collect_data()
            max_queue_capacity = self.max_queue_capacities.get(section_id, 1)
            densities.append(min(1, traffic_queue / max_queue_capacity))
        return densities
#
# class DefaultObservationFunction(ObservationFunction):
#     """Default observation function for traffic signals."""
#
#     def __init__(self, ts: TrafficSignal):
#         """Initialize default observation function."""
#         super().__init__(ts)
#
#     def __call__(self) -> np.ndarray:
#         """Compute the observation for a given section."""
#         self.queue = []
#         try:
#             # Phase ID (assuming green_phase is an integer and num_green_phases is the total number of phases)
#             phase_id = [1 if self.ts.green_phase == i else 0 for i in
#                         range(min(self.ts.num_green_phases, 15))]  # One-hot encoding
#             # print("phase_id: ", phase_id)
#             min_green = [0 if self.ts.time_since_last_phase_change < self.ts.min_green + self.ts.yellow_time else 1]
#             # print("min_green: ", min_green)
#
#             # Density calculation (assumes get_Section_density returns a list of densities)
#             density = self.get_Section_density()
#             if density is None:
#                 density = [0] * 4  # Replace with a list of zeros of the expected length
#             # print("density:", density)
#
#             # Queue calculation (fetching the latest value from deque)
#             for section_id, section in self.section_objects.items():
#                 section_co2_emission, section_volume, traffic_queue, section_vehicles = section.collect_data()
#                 self.queue = traffic_queue
#                 # print("self.queue: ", self.queue)
#             # Assuming `self.queue` is a list, we need to flatten it if necessary.
#             flattened_queue = self.queue if isinstance(self.queue, list) else list(self.queue)
#
#             # Create the observation array by flattening `self.queue`
#             observation = np.array(phase_id + min_green + density + flattened_queue, dtype=np.float32)
#
#             # Create the observation array
#             # observation = np.array(phase_id + min_green + density + [self.queue], dtype=np.float32)
#             # print("observation = np.array(phase_id + min_green + density + flattened_queue, dtype=np.float32): ", observation)
#             flattened_queue = self.queue if isinstance(self.queue, list) else list(self.queue)
#
#             # Combine all parts into one list
#             observation = phase_id + min_green + density + flattened_queue
#             # print("observation = phase_id + min_green + density + flattened_queue: ", observation)
#
#             # Ensure the observation has exactly 16 elements
#             # If it has fewer than 16 elements, pad with zeros
#             if len(observation) < 16:
#                 observation.extend([0] * (16 - len(observation)))
#                 # print("len(observation) < 16: ", observation)
#             # Convert the observation to a numpy array
#             observation = np.array(observation, dtype=np.float32)
#             # print("np.array(observation, dtype=np.float32): ", observation)
#             return observation
#         except IndexError as e:
#             print(f"IndexError encountered: {e}")
#             return np.zeros(self.observation_space().shape, dtype=np.float32)
#
#     def observation_space(self) -> spaces.Box:
#         """Return the observation space."""
#         return spaces.Box(
#             low=np.zeros(16, dtype=np.float32),
#             high=np.ones(16, dtype=np.float32),
#         )
#     def get_Section_density(self) -> List[float]:
#         """Returns the density [0,1] of the vehicles in the incoming lanes of the sections."""
#         densities = []
#         # print("%"*25)
#         for section_id, section in self.section_objects.items():
#             section_co2_emission, section_volume, traffic_queue, section_vehicles = section.collect_data()
#
#             # 데이터 출력
#             # print(f"collect_data : {section_co2_emission}, {section_volume}, {traffic_queue}, {section_vehicles}")
#             # print(f"get_Section_density_traffic_queue for section {section_id}: {traffic_queue}")
#
#             # 각 섹션의 최대 대기 차량 수를 가져옵니다
#             max_queue_capacity = self.max_queue_capacities.get(section_id)  # 기본값 50 설정
#             # print("max_queue_capacity: ", max_queue_capacity)
#             if max_queue_capacity > 0:
#                 # 밀도 계산
#                 densities = min(1, traffic_queue / max_queue_capacity)
#
#             else:
#                 # capacity가 0인 경우 밀도를 0으로 설정
#                 densities = 0
#             # print("densities: ", densities)
#         return densities

    # """Return the default observation."""
    # # Create a fixed-size observation vector with 16 elements
    # # Ensure to gather exactly 16 features; adapt the features accordingly
    # phase_id = [1 if self.ts.green_phase == i else 0 for i in range(min(self.ts.num_green_phases, 15))]  # One-hot encoding
    # print("phase_id: ", phase_id)
    # min_green = [0 if self.ts.time_since_last_phase_change < self.ts.min_green + self.ts.yellow_time else 1]
    # print("min_green: ", min_green)
    # density = self.ts.get_lanes_density()[:min(len(self.ts.lanes), 5)]  # Truncate or pad if necessary
    # print("density: ", density)
    # queue = self.ts.get_lanes_queue()[:min(len(self.ts.lanes), 5)]    # Truncate or pad if necessary
    # print("queue: ", queue)
    #
    # # Combine features into the observation array
    # observation = np.array(phase_id + min_green + density + queue, dtype=np.float32)
    # print("observation: ", observation)
    # # Ensure observation array has exactly 16 elements
    # if len(observation) < 16:
    #     observation = np.pad(observation, (0, 16 - len(observation)), mode='constant')
    #     print("len(observation) < 16: ", observation)
    # elif len(observation) > 16:
    #     observation = observation[:16]
    #     print("len(observation) > 16: ", observation)
    # return observation

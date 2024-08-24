import traci
from RunSimulation import RunSimulation


class RunActuatedOCC(RunSimulation):
    def __init__(self, config, name):
        super().__init__(config, name)
        self.cycle_time = 200
        self.total_yellow_time = 20

    def _signalControl(self):
        MinGreenTime = 0

        current_phase_index = traci.trafficlight.getPhase("TLS_0")
        num_phases = len(self.logic.phases)
        next_phase_index = (current_phase_index + 1) % num_phases
        current_phase = self.logic.phases[current_phase_index]

        current_simulation_time = traci.simulation.getTime()
        current_phase_duration = traci.trafficlight.getPhaseDuration("TLS_0")
        next_switch_time = traci.trafficlight.getNextSwitch("TLS_0")
        elapsed_time = current_simulation_time - (next_switch_time - current_phase_duration)

        remaining_time = next_switch_time - current_simulation_time

        if current_phase_index == num_phases-1 and remaining_time == 0:
            self.traffic_signal_control(self.rtInfra.getSections(), self.cycle_time, self.total_yellow_time)
            # green_times, surplus_rates, waiting_times = traffic_signal_control(self.section_objects, self.cycle_time, self.total_yellow_time)
            # print(f"Simulation step {step}: Green times: {green_times}, Surplus rates: {surplus_rates}, Waiting times: {waiting_times}")

        tls = self.Check_TrafficLight_State()

    def traffic_signal_control(self, sections, cycle_time, total_yellow_time):
        total_green_time = cycle_time - total_yellow_time

        total_vehicle_count = sum([section.traffic_queue for section in sections.values()])

        # 각 바운드에 대한 계산
        green_times = {}
        surplus_rates = {}
        waiting_times = {}
        vehicle_by_bound={"0": 107, "1": 88, "2": 126, "3": 119}

        total_percentage = sum([section.traffic_queue / vehicle_by_bound[section_id] for section_id, section in sections.items()])

        for section_id, section in sections.items():
            vehicle_count = section.traffic_queue
            occupancy_rate = section.traffic_queue / vehicle_by_bound[section_id]

            # 가중치 기반으로 신호 시간 계산
            # green_time = self.calculate_green_time_by_percentage(occupancy_rate, total_percentage, total_green_time)
            # green_times[section_id] = round(green_time)
            green_time = round(self.calculate_green_time_by_percentage(occupancy_rate, total_percentage, total_green_time))
            section.setGreenTime(green_time, self.logic)

            # 계산된 green_time을 사용하여 surplus rate 및 waiting time 계산
            surplus_rate = self.calculate_surplus_rate(vehicle_count, section.getCurrentGreenTime() * len(section.stations) / total_green_time)
            waiting_time = self.calculate_waiting_time(surplus_rate, total_green_time)

            surplus_rates[section_id] = surplus_rate
            waiting_times[section_id] = waiting_time

        # 새로운 신호 설정 적용
        current_step = traci.simulation.getTime()


    def calculate_green_time_by_percentage(self, occupancy_rate, total_percentage, total_green_time):
        return(occupancy_rate/total_percentage)*total_green_time

    def calculate_surplus_rate(self, vehicle_count, service_rate):
        return vehicle_count - service_rate

    def calculate_waiting_time(self, surplus_rate, signal_time):
        return surplus_rate * signal_time
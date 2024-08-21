import traci
from RunSimulation import RunSimulation


class RunActuated(RunSimulation):
    def __init__(self, config, name):
        super().__init__(config, name)
        self.cycle_time = 200
        self.total_yellow_time = 20

    def _signalControl(self):
        MinGreenTime = 0

        current_phase_index = traci.trafficlight.getPhase("TLS_0")
        logic = traci.trafficlight.getAllProgramLogics("TLS_0")[0]
        num_phases = len(logic.phases)
        next_phase_index = (current_phase_index + 1) % num_phases
        current_phase = logic.phases[current_phase_index]

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

        if tls == "rrrrrrrrrrrgggg":
            bound = "2"
            MinGreenTime = current_phase.minDur
        elif tls == "rrrrggggrrrrrrr":
            bound = "3"
            MinGreenTime = current_phase.minDur
        elif tls == "ggggrrrrrrrrrrr":
            bound = "0"
            MinGreenTime = current_phase.minDur
        elif tls == "rrrrrrrrgggrrrr":
            bound = "1"
            MinGreenTime = current_phase.minDur
        else:
            bound = "yellow"
            extended_time = 0

        MaxGreenTime = MinGreenTime + 10

    def traffic_signal_control(self, sections, cycle_time, total_yellow_time):
        total_green_time = cycle_time - total_yellow_time

        total_vehicle_count = sum([section.traffic_queue for section in sections.values()])

        # 각 바운드에 대한 계산
        green_times = {}
        surplus_rates = {}
        waiting_times = {}
        capacity_percentage = {"0": 25, "1": 20, "2": 28, "3": 27}
        vehicle_by_bound={"0": 107, "1": 88, "2": 126, "3": 119}

        # 바운드의 가중치 계산
        total_weight = sum(
            [section.traffic_queue / capacity_percentage[section_id] for section_id, section in sections.items()])

        total_percentage = sum([section.traffic_queue / vehicle_by_bound[section_id] for section_id, section in sections.items()])

        for section_id, section in sections.items():
            vehicle_count = section.traffic_queue
            capacity_percent = capacity_percentage[section_id]

            occupancy_rate = section.traffic_queue / vehicle_by_bound[section_id]

            # 가중치 기반으로 신호 시간 계산
            # green_time = self.calculate_green_time(vehicle_count, capacity_percent, total_weight, total_green_time)
            green_time = self.calculate_green_time_by_percentage(occupancy_rate, total_percentage, total_green_time)
            green_times[section_id] = round(green_time)

            # 계산된 green_time을 사용하여 surplus rate 및 waiting time 계산
            surplus_rate = self.calculate_surplus_rate(vehicle_count, green_time * len(section.stations) / total_green_time)
            waiting_time = self.calculate_waiting_time(surplus_rate, total_green_time)

            surplus_rates[section_id] = surplus_rate
            waiting_times[section_id] = waiting_time

        # 교차로 신호 조정
        logic = traci.trafficlight.getAllProgramLogics("TLS_0")[0]

        # 각 바운드에 신호 시간을 할당
        # Eb phase
        logic.phases[0].duration = green_times["2"]
        # Wb phase
        logic.phases[2].duration = green_times["3"]
        # Sb phase
        logic.phases[4].duration = green_times["0"]
        # Nb phase
        logic.phases[6].duration = green_times["1"]

        # 새로운 신호 설정 적용
        traci.trafficlight.setProgramLogic("TLS_0", logic)
        current_step = traci.simulation.getTime()
        print(current_step, " - set new phase")
        print("0 : Sb, 1 : Nb, 2 : Eb, 3 : Wb]")
        print(f"Green times: {green_times}, Surplus rates: {surplus_rates}, Waiting times: {waiting_times}")

    def calculate_green_time(self, queue_length, capacity_percentage, total_weight, total_green_time):
        # 가중치 기반 신호 시간 계산
        weight = queue_length / capacity_percentage
        return (weight / total_weight) * total_green_time

    def calculate_green_time_by_percentage(self, occupancy_rate, total_percentage, total_green_time):
        return(occupancy_rate/total_percentage)*total_green_time

    def calculate_surplus_rate(self, vehicle_count, service_rate):
        return vehicle_count - service_rate

    def calculate_waiting_time(self, surplus_rate, signal_time):
        return surplus_rate * signal_time
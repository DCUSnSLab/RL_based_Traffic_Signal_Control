"""
교차로 신호 제어 알고리즘
"""
import traci


def calculate_green_time(queue_length, capacity_percentage, total_weight, total_green_time):
    # 가중치 기반 신호 시간 계산
    weight = queue_length / capacity_percentage
    return (weight / total_weight) * total_green_time


def calculate_surplus_rate(vehicle_count, service_rate):
    return vehicle_count - service_rate


def calculate_waiting_time(surplus_rate, signal_time):
    return surplus_rate * signal_time


def traffic_signal_control(sections, cycle_time, total_yellow_time):
    total_green_time = cycle_time - total_yellow_time

    total_vehicle_count = sum([section.traffic_queue for section in sections.values()])

    # 각 바운드에 대한 계산
    green_times = {}
    surplus_rates = {}
    waiting_times = {}
    capacity_percentage = {"0": 25, "1": 20, "2": 28, "3": 27}

    # 바운드의 가중치 계산
    total_weight = sum([section.traffic_queue / capacity_percentage[section_id] for section_id, section in sections.items()])

    for section_id, section in sections.items():
        vehicle_count = section.traffic_queue
        capacity_percent = capacity_percentage[section_id]

        # 가중치 기반으로 신호 시간 계산
        green_time = calculate_green_time(vehicle_count, capacity_percent, total_weight, total_green_time)
        green_times[section_id] = round(green_time)

        # 계산된 green_time을 사용하여 surplus rate 및 waiting time 계산
        surplus_rate = calculate_surplus_rate(vehicle_count, green_time * len(section.stations) / total_green_time)
        waiting_time = calculate_waiting_time(surplus_rate, total_green_time)

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
    print("set new phase")
    print("0 : Sb, 1 : Nb, 2 : Eb, 3 : Wb]")
    print(f"Green times: {green_times}, Surplus rates: {surplus_rates}, Waiting times: {waiting_times}")


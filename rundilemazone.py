import math
import traci
from RunSimulation import RunSimulation


class RunDilemaZone(RunSimulation):
    def __init__(self, config, name):
        super().__init__(config, name)

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

        for section_id, section in self.section_objects.items():
            if bound == "yellow":
                pass
            else:
                check_control = section.check_DilemmaZone(elapsed_time, bound, MinGreenTime, extended_time)
                if check_control == "pass":
                    print("*" * 50)
                    print("section id :", section_id)
                    print("increase 1s")
                    print("extended count", extended_time)
                    new_duration = remaining_time+1
                    traci.trafficlight.setPhaseDuration("TLS_0", new_duration)
                    print("*" * 50)
                    extended_time += 1
                elif check_control == "yellow":
                    traci.trafficlight.setPhase("TLS_0", next_phase_index)

    def check_DilemmaZone(self, time, traffic_light_bound, MinGreenTime, MaxGreenTime):
        if traffic_light_bound == self.id:
            DilemmaZone_results = []
            for vehicle in self.section_vehicles:
                vehicle_position = traci.vehicle.getPosition(vehicle)
                vehicle_x, vehicle_y = vehicle_position
                for i in range(0, len(self.stop_lane),2):
                    stop_lane_x, stop_lane_y = self.stop_lane[i:i+2]
                    distance = math.sqrt((stop_lane_x - vehicle_x) ** 2 + (stop_lane_y - vehicle_y) ** 2)
                    if distance <= 120:
                        vehicle_speed = traci.vehicle.getSpeed(vehicle)
                        vehicle_type = traci.vehicle.getTypeID(vehicle)
                        check_value = self.DilemmaZoneControlSignal(time, vehicle_speed, distance, vehicle_type, MinGreenTime, MaxGreenTime)
                        DilemmaZone_results.append(check_value)
                    else:
                        pass
            if "pass" in DilemmaZone_results:
                return "pass"
            elif "pass" not in DilemmaZone_results and "yellow" in DilemmaZone_results:
                return "yellow"
            else:
                return "none"
        else:
            check_value = "none"
            return check_value

    def StopLane_position(self):
        stop_lane = ()
        last_station = self.stations[-1]
        for stop_detector in last_station.dets:
            lane_id = traci.inductionloop.getLaneID(stop_detector.id)
            lane_shape = traci.lane.getShape(lane_id)
            stop_lane_position = lane_shape[-1]
            stop_lane += stop_lane_position
        return stop_lane

    def DilemmaZoneControlSignal(self, time, s, d, car_type, MinGreenTime, MaxGreenTime):
        check = "none"
        s = s * 3.6
        if time >= MinGreenTime:
            # if time < MaxGreenTime:
            if MaxGreenTime <= 5:
                if car_type == "passenger":
                    T1 = s / 14
                    D1 = s * T1
                    if D1 < d:
                        check = "yellow"
                        return check
                    else:
                        # signal extension
                        print(s, d, car_type, D1)
                        check = "pass"
                        return check
                else:
                    T2 = s / 9
                    D2 = s * T2
                    if D2 < d:
                        check = "yellow"
                        return check
                    else:
                        # signal extension
                        print(s, d, car_type, D2)
                        check = "pass"
                        return check
            else:
                check = "yellow"
                return check
        else:
            return check


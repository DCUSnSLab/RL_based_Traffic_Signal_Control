import math
import traci
from RunSimulation import RunSimulation

class RunDilemaZone(RunSimulation):
    def __init__(self, config, name):
        super().__init__(config, name)
        self.extended_time = 0
        self.bound = "0"
        self.previous_tls_state = None

    def _signalControl(self):
        MinGreenTime = 0

        simulation_time = traci.simulation.getTime()
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

        # Identify which bound is currently green
        if tls == "rrrrrrrrrrrgggg":
            self.bound = "2"
            MinGreenTime = current_phase.minDur
        elif tls == "rrrrggggrrrrrrr":
            self.bound = "3"
            MinGreenTime = current_phase.minDur
        elif tls == "ggggrrrrrrrrrrr":
            self.bound = "0"
            MinGreenTime = current_phase.minDur
        elif tls == "rrrrrrrrgggrrrr":
            self.bound = "1"
            MinGreenTime = current_phase.minDur
        else:
            self.bound = "yellow"
            self.extended_time = 0

        MaxGreenTime = MinGreenTime + 10

        for section_id, section in self.getInfra().getSections().items():
            green_time = traci.trafficlight.getPhaseDuration("TLS_0")
            if self.bound == "yellow":
                pass
            else:
                if tls != self.previous_tls_state and section_id == self.bound:
                    section.setGreenTime(MinGreenTime, self.logic)
                check_control = self.check_DilemmaZone(section, elapsed_time, self.bound, MinGreenTime, self.extended_time)
                if check_control == "pass":
                    print("*" * 50)
                    print("step:", simulation_time)
                    print("Section ID:", section_id)
                    print("Geen ime:", MinGreenTime)
                    print("Increasing green time by 1 second.")
                    print("Extended count:", self.extended_time)
                    green_time += 1
                    remaining_time +=1
                    section.setGreenTime(green_time, self.logic)
                    traci.trafficlight.setPhaseDuration("TLS_0", remaining_time)
                    change_time = traci.trafficlight.getPhaseDuration("TLS_0")
                    print("New Green Time:", change_time)
                    print("*" * 50)
                    self.extended_time += 1
                elif check_control == "yellow":
                    # reset_time = green_time - self.extended_time
                    # section.setGreenTime(reset_time, self.logic)
                    traci.trafficlight.setPhase("TLS_0", next_phase_index)

        self.previous_tls_state = tls

    def check_DilemmaZone(self, section, time, traffic_light_bound, MinGreenTime, MaxGreenTime):
        # Use the section's id and stations
        if traffic_light_bound == str(section.id):
            dilemma_zone_results = []
            # Get stop lane positions from the last station's stop detectors
            stop_lane = self.get_stop_lane_positions(section.stations)
            for vehicle in section.section_vehicles:  # Access section_vehicles directly from the section
                vehicle_position = traci.vehicle.getPosition(vehicle)
                vehicle_x, vehicle_y = vehicle_position
                for i in range(0, len(stop_lane), 2):
                    stop_lane_x, stop_lane_y = stop_lane[i:i+2]
                    distance = math.sqrt((stop_lane_x - vehicle_x) ** 2 + (stop_lane_y - vehicle_y) ** 2)
                    if distance <= 120:
                        vehicle_speed = traci.vehicle.getSpeed(vehicle)
                        vehicle_type = traci.vehicle.getTypeID(vehicle)
                        check_value = self.DilemmaZoneControlSignal(section, time, vehicle_speed, distance, vehicle_type, MinGreenTime, MaxGreenTime)
                        dilemma_zone_results.append(check_value)
            if "pass" in dilemma_zone_results:
                return "pass"
            elif "yellow" in dilemma_zone_results:
                return "yellow"
            else:
                return "none"
        return "none"

    def get_stop_lane_positions(self, stations):
        stop_lane = ()
        last_station = stations[-1]  # Use the last station to get stop lane positions
        for stop_detector in last_station.dets:
            lane_id = traci.inductionloop.getLaneID(stop_detector.id)
            lane_shape = traci.lane.getShape(lane_id)
            stop_lane_position = lane_shape[-1]  # Get the stop line position
            stop_lane += stop_lane_position
        return stop_lane

    def DilemmaZoneControlSignal(self, section, time, s, d, car_type, MinGreenTime, MaxGreenTime):
        check = "none"
        limit_max = 10
        s = s * 3.6  # Convert speed to km/h
        if time >= MinGreenTime:
            if MaxGreenTime < limit_max:
                if car_type == "passenger":
                    T1 = s / 14  # Time to cross the stop line for a passenger vehicle
                    D1 = s * T1  # Distance required to stop
                    if D1 < d:
                        check = "yellow"
                    else:
                        check = "pass"  # Allow the vehicle to pass by extending green time
                else:
                    T2 = s / 9  # Time to cross the stop line for a non-passenger vehicle
                    D2 = s * T2  # Distance required to stop
                    if D2 < d:
                        check = "yellow"
                    else:
                        check = "pass"  # Allow the vehicle to pass by extending green time
        return check
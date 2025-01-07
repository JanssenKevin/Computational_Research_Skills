import numpy as np
import pandas as pd

# Constants
START_OF_DAY = 8.0
END_OF_DAY = 17.0
HOURS_PER_DAY = END_OF_DAY - START_OF_DAY
MINUTES_PER_DAY = int(HOURS_PER_DAY * 60)

TIMESLOT_T1 = 30.0
TIMESLOT_T2 = 60.0

def generate_calls_for_all_days(num_days, random_seed=None):
    if random_seed is not None:
        np.random.seed(random_seed)
    calls_by_day = {}
    # Statistics used to generate both types of patients
    type1_lambda = np.random.uniform(14.87, 18.05)  # Poisson parameter (mean number of patients)
    lambda1_arrival = type1_lambda/540   # Interarrival from the Poisson.
    mu1 = np.random.uniform(0.423, 0.4425)
    sigma1 = np.random.uniform(0.0911, 0.1046)

    mu2 = 0.86659
    sigma2= 0.3104807
    shape = 12.5849
    scale = 1/18.802

    for day in range(1, num_days + 1):
        calls = []
        arrival_time=0
        # **Type 1 Patients**
        while arrival_time<540:
            interarrival_time = np.random.exponential(1/lambda1_arrival)
            arrival_time+=interarrival_time
            if arrival_time>540:
                break
            duration = max(0.0, np.random.normal(mu1, sigma1)) * 60.0
            calls.append({
                "day_called": day,
                "patient_type": "Type 1",
                "arrival_time": arrival_time,
                "actual_duration": duration
            })
        
        # **Type 2 Patients**
        arrival_time=0
        while arrival_time < 540:
            interarrival_time = np.random.normal(mu2, sigma2)*60.0
            arrival_time+=interarrival_time
            if arrival_time>540:
                break
            duration = max(0.0, np.random.gamma(shape, scale)) * 60.0
            calls.append({
                "day_called": day,
                "patient_type": "Type 2",
                "arrival_time": arrival_time,
                "actual_duration": duration
            })
        calls_by_day[day] = calls

    return calls_by_day



# Old System Scheduling
def schedule_old_system_day(t1_patients, t2_patients, day):
    t1_patients.sort(key=lambda x:(x["day_called"], x["arrival_time"]))
    t2_patients.sort(key=lambda x:(x["day_called"], x["arrival_time"]))

    deferred_t1, deferred_t2 = [], []
    machine1, machine2 = 0.0, 0.0
    busy1, busy2 = 0.0, 0.0
    waiting_times = []
    usage_timesM1, usage_timesM2 = [], []
    slot_timesM1, slot_timesM2 = [], []
    idle_timeM1, idle_timeM2 = 0, 0
    overdraft_timeM1, overdraft_timeM2 = 0,0
    cumulative_delayM1, cumulative_delayM2 = 0, 0

    # Assigns type 1 patients to machine 1 or defers them to next day, if a slot would not fit in normal working hours.
    for p in t1_patients:
        slot = TIMESLOT_T1
        used_time = max(p["actual_duration"], slot)
        start_time = machine1
        if machine1 > MINUTES_PER_DAY-slot:
            deferred_t1.append(p)
            continue
        elif machine1 <= MINUTES_PER_DAY-slot:
            usage_timesM1.append(p["actual_duration"])
            slot_timesM1.append(slot)
            waiting_time = max(0.0,(day * MINUTES_PER_DAY + start_time + MINUTES_PER_DAY) - (p["day_called"] * MINUTES_PER_DAY + p["arrival_time"]))
            waiting_times.append(waiting_time)
            
        finish = start_time + used_time
        busy1 += p["actual_duration"]
        machine1 = finish
    
    # Assigns type 2 patients to machine 2 or defers them to next day, if a slot would not fit in normal working hours.
    for p in t2_patients:
        slot = TIMESLOT_T2
        used_time = max(p["actual_duration"], slot)
        start_time = machine2
        if machine2 > MINUTES_PER_DAY- slot:
            deferred_t2.append(p)
            continue
        elif machine2 <= MINUTES_PER_DAY - slot:
            usage_timesM2.append(p["actual_duration"])
            slot_timesM2.append(slot)
            waiting_time = max(0.0,(day * MINUTES_PER_DAY + start_time+MINUTES_PER_DAY) - (p["day_called"] * MINUTES_PER_DAY + p["arrival_time"]))
            waiting_times.append(waiting_time) 

        finish = start_time + used_time
        busy2 += p["actual_duration"]
        machine2 = finish
        
    finishing_time = max(machine1, machine2)

    # Calculate the idle and overdraft times(delay) for M1.
    for slot_time1, usage_time1 in zip(slot_timesM1, usage_timesM1):
        # Adjusts the patients time if there was delay in the system.
        adjusted_usage_time1 = usage_time1 + cumulative_delayM1

        if adjusted_usage_time1 < slot_time1:
        # Idle time(between 2 planned scans) occurs
            idle_timeM1 += slot_time1 - adjusted_usage_time1
            cumulative_delayM1 = 0  # Reset cumulative_delay as we have idle time between two scans
        else:
        # Overdraft(delay) time occurs
            overdraft_timeM1 += adjusted_usage_time1 - slot_time1
            cumulative_delayM1 = adjusted_usage_time1 - slot_time1  # Update cumulative delay
    
    # Calculate the idle and overdraft times(delay) for M2.
    for slot_time2, usage_time2 in zip(slot_timesM2, usage_timesM2):
        adjusted_usage_time2 = usage_time2 + cumulative_delayM2

        if adjusted_usage_time2 < slot_time2:
        # Idle time occurs
            idle_timeM2 += slot_time2 - adjusted_usage_time2
            cumulative_delayM2 = 0  # Reset cumulative_delay
        else:
        # Overdraft time occurs
            overdraft_timeM2 += adjusted_usage_time2 - slot_time2
            cumulative_delayM2 = adjusted_usage_time2 - slot_time2  # Update cumulative delay
    
    total_idleScan = idle_timeM1 + idle_timeM2
    total_busy = busy1 + busy2
    Lateness_time = overdraft_timeM1 + overdraft_timeM2

    return finishing_time, total_busy, deferred_t1, deferred_t2, waiting_times, Lateness_time, total_idleScan

# New System Scheduling
def schedule_new_system_day(patients, day):
    patients.sort(key=lambda x:(x["day_called"], x["arrival_time"]))

    deferred, machineA, machineB = [], 0.0, 0.0
    busyA, busyB = 0.0, 0.0
    waiting_times = []
    usage_timesMA, usage_timesMB = [], []
    slot_timesMA, slot_timesMB = [], []
    idle_timeMA, idle_timeMB = 0, 0
    overdraft_timeMA, overdraft_timeMB = 0,0
    cumulative_delayMA, cumulative_delayMB = 0, 0
    LastAdditionHelper = 1

    # Assigns patients to the earliest finished machine yet (or defers them, depending on if a slot would not fit in normal working hours), 
    # with the tiebreak being the opposite machine to the previous scheduled patient.
    for p in patients:
        slot = TIMESLOT_T1 if p["patient_type"] == "Type 1" else TIMESLOT_T2
        used_time = max(p["actual_duration"], slot)

        if machineA < machineB or (machineA==machineB and LastAdditionHelper==2):
            start_time = machineA
            if machineA > MINUTES_PER_DAY-slot:
                deferred.append(p)
                
                continue
            elif machineA <= MINUTES_PER_DAY-slot:
                usage_timesMA.append(p["actual_duration"])
                slot_timesMA.append(slot)
                waiting_time = (day * MINUTES_PER_DAY + start_time+ MINUTES_PER_DAY) - (p["day_called"] * MINUTES_PER_DAY + p["arrival_time"])
                waiting_times.append(waiting_time)
                LastAdditionHelper=1

            finish = start_time + used_time
            busyA += p["actual_duration"]
            machineA = finish

        elif machineB < machineA or (machineA==machineB and LastAdditionHelper==1):
            start_time = machineB
            if machineB > MINUTES_PER_DAY-slot:
                deferred.append(p)
                continue
            elif machineB <= MINUTES_PER_DAY-slot:
                usage_timesMB.append(p["actual_duration"])
                slot_timesMB.append(slot)
                waiting_time = (day * MINUTES_PER_DAY + start_time+ MINUTES_PER_DAY) - (p["day_called"] * MINUTES_PER_DAY + p["arrival_time"])
                waiting_times.append(waiting_time)
                LastAdditionHelper=2
            
            finish = start_time + used_time
            busyB += p["actual_duration"]
            machineB = finish

    finishing_time = max(machineA, machineB)
    
    # Calculating the idle time and overdraft(delay) on both machines.
    for slot_time, usage_time in zip(slot_timesMA, usage_timesMA):
        adjusted_usage_time = usage_time + cumulative_delayMA

        if adjusted_usage_time < slot_time:
            idle_timeMA += slot_time - adjusted_usage_time
            cumulative_delayMA = 0
        else:
            overdraft_timeMA += adjusted_usage_time - slot_time
            cumulative_delayMA = adjusted_usage_time - slot_time
    
    for slot_time, usage_time in zip(slot_timesMB, usage_timesMB):
        adjusted_usage_time = usage_time + cumulative_delayMB

        if adjusted_usage_time < slot_time:
            idle_timeMB += slot_time - adjusted_usage_time
            cumulative_delayMB = 0
        else:
            overdraft_timeMB += adjusted_usage_time - slot_time
            cumulative_delayMB = adjusted_usage_time - slot_time

    total_idleScan = idle_timeMA + idle_timeMB
    total_busy = busyA + busyB
    Lateness_time = overdraft_timeMA + overdraft_timeMB

    return finishing_time, total_busy, deferred, waiting_times, Lateness_time, total_idleScan


def run_old_system_sim(calls_by_day):
    deferred_t1, deferred_t2 = [], []
    daily_info, total_waiting, total_patients = [], 0.0, 0
    max_wait = 0.0
    max_Late = 0

    # Runs the old_schedule for the generation days.
    for day in range(1, len(calls_by_day) + 1):
        t1_patients = deferred_t1 + [p for p in calls_by_day[day] if p["patient_type"] == "Type 1"]
        t2_patients = deferred_t2 + [p for p in calls_by_day[day] if p["patient_type"] == "Type 2"]
        finishing, busy, deferred_t1, deferred_t2, waits, Late, idleScan = schedule_old_system_day(
            t1_patients, t2_patients, day
        )

        overtime = max(0.0, finishing - MINUTES_PER_DAY)
        total_waiting += sum(waits)
        total_patients += len(waits)
        if max_wait < max(waits):
            max_wait = max(waits)
        if max_Late <= Late:
            max_Late = Late

        daily_info.append({
            "day": day,
            "finishing_time": finishing,
            "idle_time": idleScan,
            "busy_time": busy,
            "overtime": overtime,
            "Late": Late
        })
    
    # Running the days without generation, until the system has no patients stuck.
    day = len(calls_by_day)+1
    while deferred_t1 or deferred_t2:
        t1_patients = deferred_t1 
        t2_patients = deferred_t2 
        finishing, busy, deferred_t1, deferred_t2, waits, Late, idleScan = schedule_old_system_day(
        t1_patients, t2_patients, day
        )
        overtime = max(0.0, finishing - MINUTES_PER_DAY)
        total_waiting += sum(waits)
        total_patients += len(waits)
        if max_wait < max(waits):
            max_wait = max(waits)
        if max_Late <= Late:
            max_Late = Late
        daily_info.append({
            "day": day,
            "finishing_time": finishing,
            "idle_time": idleScan,
            "busy_time": busy,
            "overtime": overtime,
            "Late": Late
        })
        day+= 1
    avg_wait = total_waiting / total_patients if total_patients > 0 else 0.0
    df_old = pd.DataFrame(daily_info)
    return df_old, avg_wait, max_wait, max_Late

def run_new_system_sim(calls_by_day):
    deferred_patients = []
    daily_info = []
    total_waiting, total_patients = 0.0, 0
    max_wait = 0.0
    max_Late = 0

    # Runs the new_schedule for the generation days.
    for day in range(1, len(calls_by_day) + 1):
        todays_patients = deferred_patients + calls_by_day[day]
        finishing, busy, deferred_patients, waits, Late, idleScan = schedule_new_system_day(
            todays_patients, day
        )

        overtime = max(0.0, finishing - MINUTES_PER_DAY)
        total_waiting += sum(waits)
        total_patients += len(waits)
        if max_wait < max(waits):
            max_wait = max(waits)
        if max_Late <= Late:
            max_Late = Late

        daily_info.append({
            "day": day,
            "finishing_time": finishing,
            "idle_time": idleScan,
            "busy_time": busy,
            "overtime": overtime,
            "Late": Late
        })
    
    # Runs the system until all patients have been helped, no backlog left. (no generation of new patients)
    day = len(calls_by_day)+1
    while deferred_patients:
        todays_patients = deferred_patients
        finishing, busy, deferred_patients, waits, Late, idleScan = schedule_new_system_day(
            todays_patients, day
        )
        overtime = max(0.0, finishing - MINUTES_PER_DAY)
        total_waiting += sum(waits)
        total_patients += len(waits)
        if max_wait < max(waits):
            max_wait = max(waits)
        if max_Late <= Late:
            max_Late = Late
        daily_info.append({
            "day": day,
            "finishing_time": finishing,
            "idle_time": idleScan,
            "busy_time": busy,
            "overtime": overtime,
            "Late": Late
        })
        day+= 1
    avg_wait = total_waiting / total_patients if total_patients > 0 else 0.0
    df_new = pd.DataFrame(daily_info)
    return df_new, avg_wait, max_wait, max_Late

if __name__ == "__main__":
# Initialize lists to store results for easier aggregation.
    results_old = []
    results_new = []

    for i in range(1, 1001):
        num_days = 30
        random_seed = i
        calls_all = generate_calls_for_all_days(num_days, random_seed)
    
    # Old System
        df_old, avg_waiting_old, max_waiting_old, max_Late_old = run_old_system_sim(calls_all)
        df_old['utilization'] = (df_old['busy_time'] / (2 * MINUTES_PER_DAY)) * 100
    
    # Collect statistics for old system
        results_old.append({
            "version": i,
            "avg_finishing_time": df_old['finishing_time'].mean(),
            "avg_overtime": df_old['overtime'].mean(),
            "avg_idle": df_old['idle_time'].mean(),
            "avg_busy": df_old['busy_time'].mean(),
            "avg_utilization": df_old['utilization'].mean(),
            "avg_waiting_time": avg_waiting_old,
            "max_waiting_time": max_waiting_old,
            "max_lateness_day": max_Late_old
        })
    
    # New System
        df_new, avg_waiting_new, max_waiting_new, max_Late_new = run_new_system_sim(calls_all)
        df_new['utilization'] = (df_new['busy_time'] / (2 * MINUTES_PER_DAY)) * 100
    
    # Collect statistics for new system
        results_new.append({
            "version": i,
            "avg_finishing_time": df_new['finishing_time'].mean(),
            "avg_overtime": df_new['overtime'].mean(),
            "avg_idle": df_new['idle_time'].mean(),
            "avg_busy": df_new['busy_time'].mean(),
            "avg_utilization": df_new['utilization'].mean(),
            "avg_waiting_time": avg_waiting_new,
            "max_waiting_time": max_waiting_new,
            "max_lateness_day": max_Late_new
        })

# Convert results to dataframe.
    df_results_old = pd.DataFrame(results_old)
    df_results_new = pd.DataFrame(results_new)

# Save to CSV for records 
    df_results_old.to_csv("aggregated_old_system_results.csv", index=False)
    df_results_new.to_csv("aggregated_new_system_results.csv", index=False)

# Compute overall statistics for Old System
    print("\n==== AGGREGATED RESULTS - OLD SYSTEM ====")
    print(f"Average finishing time = {df_results_old['avg_finishing_time'].mean():.2f} min")
    print(f"Average overtime       = {df_results_old['avg_overtime'].mean():.2f} min")
    print(f"Average idle           = {df_results_old['avg_idle'].mean():.2f} min")
    print(f"Average busy           = {df_results_old['avg_busy'].mean():.2f} min")
    print(f"Average utilization    = {df_results_old['avg_utilization'].mean():.2f}%")
    print(f"Average waiting time   = {df_results_old['avg_waiting_time'].mean():.2f} min")
    print(f"Maximum waiting time   = {df_results_old['max_waiting_time'].max():.2f} min")
    print(f"Maximum Lateness Day   = {df_results_old['max_lateness_day'].max():.2f} total min")

# Compute overall statistics for New System
    print("\n==== AGGREGATED RESULTS - NEW SYSTEM ====")
    print(f"Average finishing time = {df_results_new['avg_finishing_time'].mean():.2f} min")
    print(f"Average overtime       = {df_results_new['avg_overtime'].mean():.2f} min")
    print(f"Average idle           = {df_results_new['avg_idle'].mean():.2f} min")
    print(f"Average busy           = {df_results_new['avg_busy'].mean():.2f} min")
    print(f"Average utilization    = {df_results_new['avg_utilization'].mean():.2f}%")
    print(f"Average waiting time   = {df_results_new['avg_waiting_time'].mean():.2f} min")
    print(f"Maximum waiting time   = {df_results_new['max_waiting_time'].max():.2f} min")
    print(f"Maximum Lateness Day   = {df_results_new['max_lateness_day'].max():.2f} total min")

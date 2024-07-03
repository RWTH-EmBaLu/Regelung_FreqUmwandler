#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regelung für Frequenzumwandlung mit Geschwindigkeit von Testo400
"""

import time
import tkinter as tk
from collections import deque
import requests
import json
import math
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import smbus #------------------------------

# PID controller parameters
Kp = 1.3
Ki = 1.3
Kd = 0.001
#setpoint = 10.0  # Desired speed - get from entry
speed_measurements = deque(maxlen=5) #Mittlung über 5 Messungen


DEVICE_BUS = 1
DAC_ADDR = 0x58 #Adresse von I2HAA i2c-analog converter
CH_A1 = 0x00 #Analoger Ausgabe Channel A1
bus = smbus.SMBus(DEVICE_BUS) #------------------------------


times = []
current_speeds = []
mean_speeds = []
setpoints = []
start_time = time.time()

 #Umrechnungsfaktor Spannung - Umdrehung
faktor_r1 = 304.19
faktor_r2 = 13.85


# PID Controller Class
class PID:
    def __init__(self, Kp, Ki, Kd, setpoint):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.setpoint = setpoint
        self.integral = 0
        self.previous_error = 0

    def update(self, measured_value):
        # Calculate error
        error = self.setpoint - measured_value

        # Proportional term
        P = self.Kp * error

        # Integral term
        self.integral += error
        I = self.Ki * self.integral

        # Derivative term
        derivative = error - self.previous_error
        D = self.Kd * derivative

        # Update previous error
        self.previous_error = error

        # Calculate output
        output = P + I + D
        output = 0 if (output < 0) else output
        
        return output
    
def start():
    global condition
    condition = True
    # Create PID controller instance
    setpoint = float(setpoint_entry.get())
    global pid 
    pid = PID(Kp, Ki, Kd, setpoint)
    print(f"PID created {Kp:.2f}, {Ki:.2f}, {Kd:.2f},  {setpoint:.2f}")
    startpoint = float(startpoint_entry.get())
    set_device(startpoint)
    voltage_output_label.config(text=f"Spannung [V]: {startpoint:.2f}")
    update_gui()

def stop():
    global condition
    condition = False


def goodbye():
    # Do stuff before closing
    print("goodbye")
    set_device(0)# ------------------------------
    set_device(0)
    root.quit()
    root.destroy()


# Function to get current speed from the sensor
def get_speed():
    api_url = "http://192.168.1.4:54000/api/data/live"
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.get(api_url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            data = data.get("21061486")
            velocity=data.get("Velocity").strip("m/s")
            velocity = velocity.replace(",",".")
            return float(velocity)
        else:
            print("Error:", response.status_code)
    except Exception as e:
        print("Exception:", e)
    return 0

# Function to set device output
def set_device(output):
    voltage = output if (output< 9.5) else 9.5
   
    LBy,HBy = (int(voltage*100)).to_bytes(2, byteorder='little')
    bus.write_i2c_block_data(DAC_ADDR, CH_A1, [LBy, HBy])
    return voltage
    pass

# Function to calculate the mean of the last n measurements
def calculate_mean(values):
    return sum(values) / len(values)

# Function to update the plot
def update_plot(current_speed, mean_speed, setpoint):
    times.append(time.time() - start_time)
    current_speeds.append(current_speed)
    mean_speeds.append(mean_speed)
    setpoints.append(setpoint)

    ax.clear()
    ax.plot(times, current_speeds, label='Aktuelle Geschwindigkeit')
    ax.plot(times, mean_speeds, label='Mittlere Geschwindigkeit')
    ax.plot(times, setpoints, label='Sollgeschwindigkeit')
    ax.legend(loc='upper left')
    ax.set_xlabel('Zeit [s]')
    ax.set_ylabel('Geschwindigkeit [m/s]')
    canvas.draw()
    root.update_idletasks()
    root.update()

# Function to update the GUI
def update_gui():
    if condition:
        global speed_measurements
        global pid  

        for i in range(0,10):
            if condition:
                # Read the current speed
                #current_speed = i+1 #------------------------------Test Beispiel
                current_speed = get_speed() #------------------------------
                print("aktuelle Geschwindigkeit: ",current_speed)
                current_speed_label.config(text=f"Gemessene Geschwindigkeit (Rohr) [m/s]: {current_speed:.2f}")

                #Calculate speed in chamber
                cham_speed = round((current_speed*math.pi*math.pow(0.355/2,2))/(0.8*0.8),4)
                cham_speed_label.config(text=f"Geschwindigkeit (Kammer) [m/s]: {cham_speed:.2f}")

                speed_measurements.append(cham_speed)

                mean_speed = calculate_mean(speed_measurements)
                print("mittlere Geschwindigkeit: ",mean_speed)
                mean_speed_label.config(text=f"Mittlere Geschwindigkeit (Kammer) [m/s]: {mean_speed:.2f}")

                update_plot(cham_speed, mean_speed, pid.setpoint)
                time.sleep(1)
        

        # Compute the control output
        control_output = pid.update(mean_speed)
        print("Control ouptput: ",control_output)
        control_output_label.config(text=f"Steuersignal [V]: {control_output:.2f}")
    
        # Apply the control output to the device
        #voltage = control_output #------------------------------
        voltage = set_device(control_output) #------------------------------
        print("Spannung: ", voltage)
        voltage_output_label.config(text=f"Spannung [V]: {voltage:.2f}")
        
        rotation = float(voltage*faktor_r1-faktor_r2)
        rotation_output_label.config(text=f"Drehzahl [1/min]: {rotation:.0f}")

        # Schedule the next update
        root.after(1000, update_gui)  # Update every 100 ms
        

# Create the GUI
root = tk.Tk()
root.title("PID Controller GUI")
root.geometry("1100x500+1100+500") 
root.protocol("WM_DELETE_WINDOW", goodbye)

title = tk.Label(root, text="Regelung Frequenzumwandler", font=("Font", 15))
title.place(x=1, y=1)

current_speed_label = tk.Label(root, text="Gemessene Geschwindigkeit (Rohr) [m/s]: 0.00",font=("Font",12))
current_speed_label.place(x=1, y=30)

cham_speed_label = tk.Label(root, text="Geschwindigkeit (Kammer) [m/s]: 0.00",font=("Font",12))
cham_speed_label.place(x=1, y=60)

mean_speed_label = tk.Label(root, text="Mittlere Geschwindigkeit (Kammer) [m/s]: 0.00",font=("Font",12))
mean_speed_label.place(x=1, y=90)

control_output_label = tk.Label(root, text="Steuersignal [V]: 0.00",font=("Font",12))
control_output_label.place(x=1, y=120)

voltage_output_label = tk.Label(root, text="Spannung [V]: 0.00",font=("Font",12))
voltage_output_label.place(x=1, y=150)


rotation_output_label = tk.Label(root, text="Drehzahl [1/min]: 0.00",font=("Font",12))
rotation_output_label.place(x=1, y=180)



setpoint_label = tk.Label(root, text="Soll Geschwindigkeit (Kammer) [m/s]:", font=("Font", 12))
setpoint_label.place(x=1, y=210)
setpoint_entry = tk.Entry(root, width = 5)
setpoint_entry.insert(0,"1.5")
setpoint_entry.place(x=310, y=210)


startpoint_label = tk.Label(root, text="Start Spannung [V]:", font=("Font", 12))
startpoint_label.place(x=1, y=240)
startpoint_entry = tk.Entry(root, width = 5)
startpoint_entry.insert(0,"0")
startpoint_entry.place(x=310, y=240)



# Create the plot
fig, ax = plt.subplots()
canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().place(x=380, y=20, width=650, height=450)


start_button = tk.Button(root, text="Start", command=start, width=10)
start_button.place(x=2, y=280)
stop_button = tk.Button(root, text="Stop", command=stop, width=10)
stop_button.place(x=100, y=280)

close_button = tk.Button(root, command=goodbye, text="schließen", width=10)
close_button.place(x=200, y=280)



# Start the Tkinter main loop
root.mainloop()

import sys
import os
import json
import subprocess
import psutil
import atexit
import zmq
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QGridLayout, QTabWidget, QMessageBox, QHBoxLayout
)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtCore import QCoreApplication 

# Conversion factor from Pa to Torr
PA_TO_TORR = 0.00750062

# Dictionary to map pin names to gauge designations
pin_gauge_dict = {
    "A0": "A",
    "A1": "B",
    "A2": "C",
    "A3": "E"
}

# Filament current settings dictionary
FilamentCurrent = {"A": 1, "B": 1, "C": 0.1, "E": 1}

def format_scientific(value):
    """Format number in scientific notation with 1 decimal place."""
    return f"{value:.1e}"

def voltage_to_pressure(voltage: float, filament_current):
    """Convert voltage to pressure."""
    pressure_exp_dict = {0.1: 10, 1: 11, 10: 12}
    actual_voltage = voltage * 2
    if actual_voltage >= 10:
        return "Ion gauge off!"
    else:
        pressure = 10 ** (actual_voltage - pressure_exp_dict[filament_current])
        return format_scientific(pressure)

# ZMQ Clients for valve and pressure servers
class ValveZMQClient(QThread):
    valve_data_ready = pyqtSignal(dict)

    def __init__(self, server_address="tcp://localhost:5560"):
        super().__init__()
        self.server_address = server_address
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(server_address)
        self.running = True

    def send_command(self, command):
        try:
            self.socket.send_string(command)
            response = self.socket.recv_string()
            return True, response
        except Exception as e:
            return False, f"Failed to send command: {e}"

    def stop(self):
        self.running = False
        self.quit()

class PressureZMQClient(QThread):
    pressure_data_ready = pyqtSignal(dict)

    def __init__(self, server_address="tcp://localhost:5555"):
        super().__init__()
        self.server_address = server_address
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(server_address)
        self.running = True

    def run(self):
        while self.running:
            command = "READ_PRESSURES"
            self.socket.send_string(command)

            try:
                message = self.socket.recv_string()
                try:
                    data = json.loads(message)
                    self.pressure_data_ready.emit(data)
                except json.JSONDecodeError:
                    pass
            except zmq.ZMQError:
                pass

            self.msleep(5000)

    def stop(self):
        self.running = False
        self.quit()

class ServerManager:
    def __init__(self, script_path, pid_file):
        self.script_path = script_path
        self.pid_file = pid_file
        atexit.register(self.stop_server)

    def is_server_running(self):
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and self.script_path in proc.info['cmdline']:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False

    def start_server(self):
        if not self.is_server_running():
            try:
                process = subprocess.Popen(
                    ["python", self.script_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                with open(self.pid_file, "w") as pid_file:
                    pid_file.write(str(process.pid))
                return True, f"{self.script_path} started successfully."
            except Exception as e:
                return False, f"Failed to start {self.script_path}: {e}"
        else:
            return False, f"{self.script_path} is already running."

    def stop_server(self):
        if os.path.exists(self.pid_file):
            with open(self.pid_file, "r") as pid_file:
                pid = int(pid_file.read())
            if psutil.pid_exists(pid):
                os.kill(pid, 9)
                os.remove(self.pid_file)
                return True, f"{self.script_path} stopped successfully."
        return False, f"{self.script_path} was not running."

class ControlGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gate Valve Control and Pressure Monitoring")
        self.setGeometry(100, 100, 600, 400)

        # Initialize server managers and UI components
        self.valve_server_manager = ServerManager("valve_serial_command_server.py", "valve_server_pid.txt")
        self.pressure_server_manager = ServerManager("pressure_reading_server.py", "pressure_server_pid.txt")
        self.init_ui()

        # Initialize ZMQ clients
        self.valve_client = ValveZMQClient("tcp://localhost:5560")
        self.pressure_client = PressureZMQClient("tcp://localhost:5555")

        # Connect signals
        self.pressure_client.pressure_data_ready.connect(self.update_pressure_readings)

        # Start servers and data fetch
        self.start_valve_server()
        self.start_pressure_server()
        self.pressure_client.start()

        # Fetch and display the initial valve status
        self.fetch_valve_status()

    def init_ui(self):
        layout = QVBoxLayout()
        self.tabs = QTabWidget()

        # Valve Control Tab
        self.valve_tab = QWidget()
        self.valve_layout = QVBoxLayout()
        self.create_valve_controls()
        self.valve_tab.setLayout(self.valve_layout)
        self.tabs.addTab(self.valve_tab, "Valve Control")

        # Pressure Monitoring Tab
        self.pressure_tab = QWidget()
        self.pressure_layout = QVBoxLayout()

        # Add TIC Forline pressure label at the top with the same styling
        self.tic_label = QLabel("Forline: -- Torr")
        self.tic_label.setStyleSheet("font-size: 14px; font-weight: bold; color: blue; padding: 5px;")
        self.pressure_layout.addWidget(self.tic_label)

        # Add labels for all necessary Arduino pressure readings (A, B, C, E)
        self.labels = {}
        for pin, gauge in {"A0": "A", "A1": "B", "A2": "C", "A3": "E"}.items():
            label = QLabel(f"{gauge}: -- Torr")
            label.setStyleSheet("font-size: 14px; font-weight: bold; color: blue; padding: 5px;")
            self.pressure_layout.addWidget(label)
            self.labels[gauge] = label

        self.pressure_tab.setLayout(self.pressure_layout)
        self.tabs.addTab(self.pressure_tab, "Pressure Monitoring")

        # Server Controls Tab
        self.server_tab = QWidget()
        self.server_layout = QVBoxLayout()

        # Valve Server Status and Controls
        self.valve_status_label = QLabel("Valve Server Status: Unknown")
        self.server_layout.addWidget(self.valve_status_label)
        self.valve_server_controls = QHBoxLayout()
        self.start_valve_button = QPushButton("Start Valve Server")
        self.stop_valve_button = QPushButton("Stop Valve Server")
        self.start_valve_button.clicked.connect(self.start_valve_server)
        self.stop_valve_button.clicked.connect(self.stop_valve_server)
        self.valve_server_controls.addWidget(self.start_valve_button)
        self.valve_server_controls.addWidget(self.stop_valve_button)
        self.server_layout.addLayout(self.valve_server_controls)

        # Pressure Server Status and Controls
        self.pressure_status_label = QLabel("Pressure Server Status: Unknown")
        self.server_layout.addWidget(self.pressure_status_label)
        self.pressure_server_controls = QHBoxLayout()
        self.start_pressure_button = QPushButton("Start Pressure Server")
        self.stop_pressure_button = QPushButton("Stop Pressure Server")
        self.start_pressure_button.clicked.connect(self.start_pressure_server)
        self.stop_pressure_button.clicked.connect(self.stop_pressure_server)
        self.pressure_server_controls.addWidget(self.start_pressure_button)
        self.pressure_server_controls.addWidget(self.stop_pressure_button)
        self.server_layout.addLayout(self.pressure_server_controls)

        self.server_tab.setLayout(self.server_layout)
        self.tabs.addTab(self.server_tab, "Server Controls")

        layout.addWidget(self.tabs)
        self.setLayout(layout)

    def update_pressure_readings(self, readings):
        """Update the pressure readings display using gauge designations."""
        for pin, voltage in readings.items():
            if pin == "Forline":
                # Convert Forline pressure from Pa to Torr and format it
                forline_pressure_torr = format_scientific(voltage * PA_TO_TORR)
                self.tic_label.setText(f"Forline: {forline_pressure_torr} Torr")
            else:
                gauge = pin_gauge_dict.get(pin)
                if gauge:
                    # Get the corresponding filament current for this gauge
                    filament_current = FilamentCurrent.get(gauge, 1)
                    pressure = voltage_to_pressure(voltage, filament_current)

                    # Update the label for the gauge
                    if gauge in self.labels:
                        self.labels[gauge].setText(f"{gauge}: {pressure} Torr")

    def create_valve_controls(self):
        """Creates buttons for each valve control."""
        self.valve_buttons = {}
        grid_layout = QGridLayout()

        for i in range(1, 9):
            valve_name = f"VALVE_{i}"
            button = QPushButton(f"Open {valve_name}")
            button.setCheckable(True)
            # Use a lambda with a default argument to capture the current valve_name
            button.clicked.connect(lambda _, v=valve_name: self.toggle_valve(v))
            self.valve_buttons[valve_name] = button
            grid_layout.addWidget(button, (i - 1) // 4, (i - 1) % 4)

        self.valve_layout.addLayout(grid_layout)

    def toggle_valve(self, valve_name):
        """Send command to open/close valve and update UI."""
        current_status = "OPEN" if self.valve_buttons[valve_name].isChecked() else "CLOSE"
        success, response = self.valve_client.send_command(f"{current_status}_{valve_name}")

        if success:
            action = "Closed" if current_status == "CLOSE" else "Opened"
            self.valve_buttons[valve_name].setText(f"{action} {valve_name}")
        else:
            QMessageBox.warning(self, "Error", f"Failed to toggle {valve_name}. {response}")

    def fetch_valve_status(self):
        """Fetch the initial status of the valves and update the buttons."""
        success, response = self.valve_client.send_command("STATUS_VALVES")
        if success:
            try:
                if response.startswith("VALVE_STATUS:"):
                    # Remove the "VALVE_STATUS:" prefix and parse the valve statuses
                    response = response.replace("VALVE_STATUS:", "").strip()
                    valve_statuses = {}

                    # Split the response into individual valve updates
                    for update in response.split(","):
                        if "=" in update:
                            valve, status = update.split("=")
                            # Normalize valve name to uppercase to match button names
                            valve_statuses[valve.strip().upper()] = status.strip().upper()

                    # # Debug: Print the parsed valve statuses
                    # print("Parsed Valve Statuses:", valve_statuses)

                    # Update the valve buttons based on the parsed statuses
                    for valve_name, status in valve_statuses.items():
                        if valve_name in self.valve_buttons:
                            is_open = status == "OPEN"
                            # Set the button's state and text
                            self.valve_buttons[valve_name].setChecked(is_open)
                            self.valve_buttons[valve_name].setText(f"{'Opened' if is_open else 'Closed'} {valve_name}")

                            # Force an update on the button to reflect changes
                            self.valve_buttons[valve_name].repaint()

                    # Force a refresh of the entire application
                    QCoreApplication.processEvents()
                else:
                    QMessageBox.warning(self, "Error", "Unexpected response format from valve server.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to decode valve status response: {e}")

    def start_valve_server(self):
        """Start the valve server."""
        started, message = self.valve_server_manager.start_server()
        self.valve_status_label.setText("Valve Server Status: Running" if started else "Valve Server Status: " + message)

    def stop_valve_server(self):
        """Stop the valve server."""
        stopped, message = self.valve_server_manager.stop_server()
        self.valve_status_label.setText("Valve Server Status: Stopped" if stopped else "Valve Server Status: " + message)

    def start_pressure_server(self):
        """Start the pressure server."""
        started, message = self.pressure_server_manager.start_server()
        self.pressure_status_label.setText("Pressure Server Status: Running" if started else "Pressure Server Status: " + message)

    def stop_pressure_server(self):
        """Stop the pressure server."""
        stopped, message = self.pressure_server_manager.stop_server()
        self.pressure_status_label.setText("Pressure Server Status: Stopped" if stopped else "Pressure Server Status: " + message)

    def closeEvent(self, event):
        """Ensure clients and threads stop when GUI closes."""
        self.pressure_client.stop()
        self.valve_server_manager.stop_server()
        self.pressure_server_manager.stop_server()
        event.accept()

def main():
    app = QApplication(sys.argv)
    gui = ControlGUI()
    gui.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()



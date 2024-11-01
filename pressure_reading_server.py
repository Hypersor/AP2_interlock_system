import zmq
import json
import serial
import time
import re

# Configuration dictionary for pressure units
config = {
    'pressure_unit_dictionary': {66: "V", 59: "Pa", 81: "%"}
}

class PressureStatusJSON:
    def __init__(self, json_file="pressure_status.json"):
        self.json_file = json_file

    def read_status(self):
        """Read the pressure readings from the JSON file."""
        try:
            with open(self.json_file, "r") as json_file:
                data = json.load(json_file)
                return data
        except FileNotFoundError:
            print("JSON file not found, initializing with default values.")
            return self.default_status()
        except Exception as e:
            print(f"Error reading JSON: {e}")
            return None

    def write_status(self, pressure_readings):
        """Write the pressure readings along with a timestamp to the JSON file."""
        data = {
            "pressure": pressure_readings,
            "timestamp": time.time()  # Current timestamp
        }
        try:
            with open(self.json_file, "w") as json_file:
                json.dump(data, json_file, indent=4)
            print(f"Written to JSON: {data}")
        except Exception as e:
            print(f"Error writing to JSON: {e}")

    def default_status(self):
        """Return default pressure values."""
        return {
            "pressure": {
                "A0": 0.0,
                "A1": 0.0,
                "A2": 0.0,
                "A3": 0.0,
                "Forline": 0.0
            },
            "timestamp": time.time()
        }

class SerialPressureHandler:
    def __init__(self, serial_port, baudrate=9600, json_handler=None):
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.serial_connection = None
        self.json_handler = json_handler if json_handler else PressureStatusJSON()
        self.init_serial_connection()
    
    def init_serial_connection(self):
        """Initialize the serial connection."""
        try:
            self.serial_connection = serial.Serial(self.serial_port, self.baudrate, timeout=1)
            time.sleep(2)
            print(f"Connected to serial port {self.serial_port}")
        except Exception as e:
            print(f"Error connecting to serial port: {e}")

    def send_read_command(self):
        """Send the READ_VOLTAGES command to the Arduino and parse the response."""
        if self.serial_connection and self.serial_connection.is_open:
            try:
                self.serial_connection.write("READ_VOLTAGES\n".encode())
                time.sleep(0.1)
                response = self.serial_connection.readline().decode().strip()
                
                if response.startswith("Voltages:"):
                    voltages = re.findall(r"A\d = ([\d.]+)", response)
                    if len(voltages) == 4:
                        pressure_readings = {
                            "A0": float(voltages[0]),
                            "A1": float(voltages[1]),
                            "A2": float(voltages[2]),
                            "A3": float(voltages[3])
                        }
                        return pressure_readings
                    else:
                        print("Error: Incorrect number of voltage readings.")
                        return None
                else:
                    print(f"Unexpected response: {response}")
                    return None
            except Exception as e:
                print(f"Error reading from Arduino: {e}")
                return None
        else:
            print("Serial connection not open.")
            return None

class EdwardsTICReader:
    def __init__(self, port="COM20", baudrate=9600, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_connection = None
        self.init_serial_connection()

    def init_serial_connection(self):
        """Initialize the serial connection to the TIC controller."""
        try:
            self.serial_connection = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            time.sleep(2)
            print(f"Connected to Edwards TIC on {self.port}")
        except serial.SerialException as e:
            print(f"Error connecting to TIC controller: {e}")

    def get_pressure_reading(self):
        """Send the pressure command and parse the response."""
        if self.serial_connection and self.serial_connection.is_open:
            try:
                self.serial_connection.write(b"?V913\r")
                time.sleep(0.1)
                reply = self.serial_connection.readline().decode().strip()
                
                pressure_value = float(reply.split(" ")[1].split(";")[0])
                unit_code = int(reply.split(" ")[1].split(";")[1])
                pressure_unit = config['pressure_unit_dictionary'].get(unit_code, "Unknown unit")
                
                return pressure_value, pressure_unit
            except (IndexError, ValueError) as e:
                print(f"Error parsing pressure response: {e}")
                return None, None
        else:
            print("Serial connection not open.")
            return None, None

    def close_connection(self):
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
            print("Closed serial connection to TIC controller.")

def main():
    arduino_port = 'COM9'  # Replace with actual Arduino serial port
    tic_port = 'COM20'     # TIC controller port
    pressure_json_handler = PressureStatusJSON()
    arduino_handler = SerialPressureHandler(arduino_port, json_handler=pressure_json_handler)
    tic_handler = EdwardsTICReader(tic_port)

    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:5555")

    print("ZeroMQ Pressure Server listening on port 5555...")

    try:
        while True:
            if socket.poll(timeout=1000) & zmq.POLLIN:
                message = socket.recv_string()
                print(f"Received request: {message}")

                if message == "READ_PRESSURES":
                    # Read from Arduino
                    arduino_readings = arduino_handler.send_read_command()
                    # Read from TIC
                    tic_pressure, tic_unit = tic_handler.get_pressure_reading()
                    
                    # Combine readings and write to JSON
                    if arduino_readings is not None and tic_pressure is not None:
                        pressure_readings = {**arduino_readings, "Forline": tic_pressure}
                        pressure_json_handler.write_status(pressure_readings)
                        response = json.dumps(pressure_readings)
                    else:
                        response = "Error: Failed to read pressures"
                else:
                    response = "Unknown command"

                socket.send_string(response)

    except KeyboardInterrupt:
        print("Shutting down the server...")

    finally:
        socket.close()
        context.term()
        arduino_handler.serial_connection.close()
        tic_handler.close_connection()
        print("Server stopped.")

if __name__ == "__main__":
    main()

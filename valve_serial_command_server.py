# import zmq
# import json
# import serial
# import time
# import re

# class ValveStatusJSON:
#     def __init__(self, json_file="valve_status.json"):
#         self.json_file = json_file

#     def read_status(self):
#         """Read the valve status and timestamp from the JSON file."""
#         try:
#             with open(self.json_file, "r") as json_file:
#                 data = json.load(json_file)
#                 return data
#         except FileNotFoundError:
#             print("JSON file not found, initializing with default values.")
#             return self.default_status()
#         except Exception as e:
#             print(f"Error reading JSON: {e}")
#             return None

#     def write_status(self, valve_status):
#         """Write the valve status along with a timestamp to the JSON file."""
#         data = {
#             "status": valve_status,
#             "timestamp": time.time()  # Current timestamp
#         }
#         try:
#             with open(self.json_file, "w") as json_file:
#                 json.dump(data, json_file, indent=4)
#             print(f"Written to JSON: {data}")
#         except Exception as e:
#             print(f"Error writing to JSON: {e}")

#     def default_status(self):
#         """Return a default status for the valves."""
#         default_valve_status = {
#             "VALVE_1": "CLOSED",
#             "VALVE_2": "CLOSED",
#             "VALVE_3": "CLOSED",
#             "VALVE_4": "CLOSED",
#             "VALVE_5": "CLOSED",
#             "VALVE_6": "CLOSED",
#             "VALVE_7": "CLOSED",
#             "VALVE_8": "CLOSED"
#         }
#         return {
#             "status": default_valve_status,
#             "timestamp": time.time()  # Set timestamp for initialization
#         }

# class SerialCommandHandler:
#     def __init__(self, serial_port, baudrate=9600, json_handler=None):
#         self.serial_port = serial_port
#         self.baudrate = baudrate
#         self.serial_connection = None
#         self.json_handler = json_handler if json_handler else ValveStatusJSON()
#         self.init_serial_connection()
    
#     def init_serial_connection(self):
#         """Initialize the serial connection."""
#         try:
#             self.serial_connection = serial.Serial(self.serial_port, self.baudrate, timeout=1)
#             time.sleep(2)  # Short delay to ensure the connection is ready
#             print(f"Connected to serial port {self.serial_port}")
#         except Exception as e:
#             print(f"Error connecting to serial port: {e}")

#     def send_command_to_arduino(self, command, retries=3):
#         """Send a command to the Arduino with retry mechanism."""
#         attempt = 0
#         while attempt < retries:
#             if self.serial_connection and self.serial_connection.is_open:
#                 try:
#                     self.serial_connection.write(f"{command}\n".encode())
#                     time.sleep(0.1)
#                     response = self.serial_connection.readline().decode().strip()
#                     if response:  # Check if a response is received
#                         print(f"Sent: {command}, Received: {response}")
#                         return response
#                 except Exception as e:
#                     print(f"Error sending command to Arduino (attempt {attempt + 1}): {e}")
#             else:
#                 print("Serial connection not open.")
            
#             attempt += 1
#             time.sleep(1)  # Short delay between retries
#         return None  # Return None if all attempts fail
    
#     def handle_command(self, command):
#         """Handle the incoming command: open/close valves or get status."""
#         try:
#             # Read the current valve status from the JSON file
#             valve_status = self.json_handler.read_status().get("status", {})

#             # Match OPEN_VALVE_n or CLOSE_VALVE_n commands using re.match
#             match = re.match(r'(OPEN|CLOSE)_VALVE_(\d+)', command)

#             if match:
#                 action, valve_number = match.groups()
#                 valve_key = f"VALVE_{valve_number}"

#                 if action == "OPEN":
#                     # Send the OPEN command to Arduino
#                     response = self.send_command_to_arduino(f"OPEN_VALVE_{valve_number}")

#                     # Ignore CMD_RECEIVED response
#                     if "CMD_RECEIVED" in response:
#                         response = self.send_command_to_arduino(f"OPEN_VALVE_{valve_number}")

#                     # Process the actual response from Arduino (success or failure)
#                     if "SUCCESS" in response:
#                         valve_status[valve_key] = "OPEN"
#                     elif "VALVE_ALREADY_OPEN" in response:
#                         return f"Valve {valve_number} is already open."
#                     else:
#                         return f"Error: {response}"

#                 elif action == "CLOSE":
#                     # Send the CLOSE command to Arduino
#                     response = self.send_command_to_arduino(f"CLOSE_VALVE_{valve_number}")

#                     # Ignore CMD_RECEIVED response
#                     if "CMD_RECEIVED" in response:
#                         response = self.send_command_to_arduino(f"CLOSE_VALVE_{valve_number}")

#                     # Process the actual response from Arduino (success or failure)
#                     if "SUCCESS" in response:
#                         valve_status[valve_key] = "CLOSED"
#                     elif "VALVE_ALREADY_CLOSED" in response:
#                         return f"Valve {valve_number} is already closed."
#                     else:
#                         return f"Error: {response}"

#                 # Update the JSON file with the new valve status
#                 self.json_handler.write_status(valve_status)
#                 return f"Command {action} executed for Valve {valve_number}"

#             # Use re.match for STATUS_VALVES command
#             elif re.match(r'STATUS_VALVES', command):
#                 # Send the STATUS_VALVES command to Arduino
#                 response = self.send_command_to_arduino("STATUS_VALVES")

#                 # First response line should be CMD_RECEIVED=STATUS_VALVES
#                 if "CMD_RECEIVED=STATUS_VALVES" in response:
#                     # Wait for the next line which contains the actual valve status
#                     response = self.send_command_to_arduino("")

#                 # Parse the valve statuses from the Arduino response
#                 if "VALVE_STATUS:" in response:
#                     # Remove the "VALVE_STATUS:" prefix
#                     response = response.replace("VALVE_STATUS:", "").strip()

#                     # Split the response into individual valve updates
#                     valve_updates = response.split(", ")
#                     for update in valve_updates:
#                         if "=" in update:
#                             try:
#                                 valve, status = update.split("=")
#                                 valve_status[valve.strip()] = status.strip()
#                             except ValueError:
#                                 return f"Error: Invalid valve status format: {update}"

#                     # Write the updated statuses back to the JSON file
#                     self.json_handler.write_status(valve_status)
#                     return f"VALVE_STATUS: {response}"
#                 else:
#                     return "Error: Failed to retrieve valve statuses"

#             else:
#                 return "Unknown command"

#         except Exception as e:
#             return f"Error: {e}"

# def main():
#     serial_port = 'COM10'  # Replace with your actual serial port on Windows
#     valve_json_handler = ValveStatusJSON()  # Instantiate the ValveStatusJSON class
#     handler = SerialCommandHandler(serial_port, json_handler=valve_json_handler)

#     context = zmq.Context()
#     socket = context.socket(zmq.REP)  # REP socket for synchronous communication
#     socket.bind("tcp://*:5560")  # Bind to TCP port 5555

#     poller = zmq.Poller()
#     poller.register(socket, zmq.POLLIN)  # Register the socket for incoming messages

#     print("ZeroMQ Server listening on port 5555...")

#     try:
#         while True:
#             events = dict(poller.poll(timeout=1000))  # Timeout set to 1000ms (1 second)

#             if socket in events:
#                 message = socket.recv_string()
#                 print(f"Received request: {message}")

#                 # Handle the command (send it to Arduino and update JSON as needed)
#                 response = handler.handle_command(message)

#                 # Send the reply back to the client
#                 socket.send_string(response)

#     except KeyboardInterrupt:
#         print("\nShutting down the server...")

#     finally:
#         # Close the socket and context properly
#         socket.close()
#         context.term()
#         if handler.serial_connection and handler.serial_connection.is_open:
#             handler.serial_connection.close()
#         print("Server stopped.")

# if __name__ == "__main__":
#     main()

import zmq
import json
import serial
import time
import re

class ValveStatusJSON:
    def __init__(self, json_file="valve_status.json"):
        self.json_file = json_file

    def read_status(self):
        """Read the valve status and timestamp from the JSON file."""
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

    def write_status(self, valve_status):
        """Write the valve status along with a timestamp to the JSON file."""
        data = {
            "status": valve_status,
            "timestamp": time.time()  # Current timestamp
        }
        try:
            with open(self.json_file, "w") as json_file:
                json.dump(data, json_file, indent=4)
            print(f"Written to JSON: {data}")
        except Exception as e:
            print(f"Error writing to JSON: {e}")

    def default_status(self):
        """Return a default status for the valves."""
        default_valve_status = {
            "VALVE_1": "CLOSED",
            "VALVE_2": "CLOSED",
            "VALVE_3": "CLOSED",
            "VALVE_4": "CLOSED",
            "VALVE_5": "CLOSED",
            "VALVE_6": "CLOSED",
            "VALVE_7": "CLOSED",
            "VALVE_8": "CLOSED"
        }
        return {
            "status": default_valve_status,
            "timestamp": time.time()  # Set timestamp for initialization
        }

class SerialCommandHandler:
    def __init__(self, serial_port, baudrate=9600, json_handler=None):
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.serial_connection = None
        self.json_handler = json_handler if json_handler else ValveStatusJSON()
        self.init_serial_connection()

    def init_serial_connection(self):
        """Initialize the serial connection."""
        try:
            self.serial_connection = serial.Serial(self.serial_port, self.baudrate, timeout=1)
            time.sleep(2)  # Short delay to ensure the connection is ready
            print(f"Connected to serial port {self.serial_port}")
        except Exception as e:
            print(f"Error connecting to serial port: {e}")

    def send_command_to_arduino(self, command, retries=3):
        """Send a command to the Arduino with retry mechanism."""
        attempt = 0
        while attempt < retries:
            if self.serial_connection and self.serial_connection.is_open:
                try:
                    self.serial_connection.write(f"{command}\n".encode())
                    time.sleep(0.1)  # Small delay to give Arduino time to process
                    response = self.serial_connection.readline().decode().strip()
                    if response:  # Check if a response is received
                        print(f"Sent: {command}, Received: {response}")
                        return response
                except Exception as e:
                    print(f"Error sending command to Arduino (attempt {attempt + 1}): {e}")
            else:
                print("Serial connection not open.")
            
            attempt += 1
            time.sleep(1)  # Short delay between retries
        return None  # Return None if all attempts fail

    def handle_command(self, command):
        """Handle the incoming command: open/close valves or get status."""
        try:
            # Read the current valve status from the JSON file
            valve_status = self.json_handler.read_status().get("status", {})

            # Match OPEN_VALVE_n or CLOSE_VALVE_n commands using re.match
            match = re.match(r'(OPEN|CLOSE)_VALVE_(\d+)', command)

            if match:
                action, valve_number = match.groups()
                valve_key = f"VALVE_{valve_number}"

                if action == "OPEN":
                    response = self.send_command_to_arduino(f"OPEN_VALVE_{valve_number}")
                    if response and "SUCCESS" in response:
                        valve_status[valve_key] = "OPEN"
                    elif response and "VALVE_ALREADY_OPEN" in response:
                        return f"Valve {valve_number} is already open."
                    else:
                        return f"Error: {response or 'No response'}"

                elif action == "CLOSE":
                    response = self.send_command_to_arduino(f"CLOSE_VALVE_{valve_number}")
                    if response and "SUCCESS" in response:
                        valve_status[valve_key] = "CLOSED"
                    elif response and "VALVE_ALREADY_CLOSED" in response:
                        return f"Valve {valve_number} is already closed."
                    else:
                        return f"Error: {response or 'No response'}"

                self.json_handler.write_status(valve_status)
                return f"Command {action} executed for Valve {valve_number}"

            elif command == "STATUS_VALVES":
                # Send the STATUS_VALVES command to Arduino
                response = self.send_command_to_arduino("STATUS_VALVES")
                print(f"First response: {response}")  # Debugging output

                if response and "CMD_RECEIVED=STATUS_VALVES" in response:
                    # Wait for the next line which contains the actual valve status
                    time.sleep(0.1)  # Small delay before reading again
                    response = self.serial_connection.readline().decode().strip()
                    print(f"Valve status response: {response}")  # Debugging output

                if response and "VALVE_STATUS:" in response:
                    response = response.replace("VALVE_STATUS:", "").strip()
                    valve_updates = response.split(", ")
                    for update in valve_updates:
                        if "=" in update:
                            try:
                                valve, status = update.split("=")
                                valve_status[valve.strip()] = status.strip()
                            except ValueError:
                                return f"Error: Invalid valve status format: {update}"

                    self.json_handler.write_status(valve_status)
                    return f"VALVE_STATUS: {response}"
                else:
                    return "Error: Failed to retrieve valve statuses"

            else:
                return "Unknown command"

        except Exception as e:
            return f"Error: {e}"

def main():
    serial_port = 'COM10'  # Replace with your actual serial port on Windows
    valve_json_handler = ValveStatusJSON()  # Instantiate the ValveStatusJSON class
    handler = SerialCommandHandler(serial_port, json_handler=valve_json_handler)

    context = zmq.Context()
    socket = context.socket(zmq.REP)  # REP socket for synchronous communication
    socket.bind("tcp://*:5560")  # Bind to TCP port 5555

    poller = zmq.Poller()
    poller.register(socket, zmq.POLLIN)  # Register the socket for incoming messages

    print("ZeroMQ Server listening on port 5555...")

    try:
        while True:
            events = dict(poller.poll(timeout=1000))  # Timeout set to 1000ms (1 second)

            if socket in events:
                message = socket.recv_string()
                print(f"Received request: {message}")

                # Handle the command (send it to Arduino and update JSON as needed)
                response = handler.handle_command(message)

                # Send the reply back to the client
                socket.send_string(response)

    except KeyboardInterrupt:
        print("\nShutting down the server...")

    finally:
        # Close the socket and context properly
        socket.close()
        context.term()
        if handler.serial_connection and handler.serial_connection.is_open:
            handler.serial_connection.close()
        print("Server stopped.")

if __name__ == "__main__":
    main()

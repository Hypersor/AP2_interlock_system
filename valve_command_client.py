import zmq

def send_command(command):
    context = zmq.Context()

    # Create a request socket
    socket = context.socket(zmq.REQ)
    socket.connect("tcp://localhost:5560")  # Connect to the server

    print(f"Sending command: {command}")
    socket.send_string(command)

    # Get the reply from the server
    message = socket.recv_string()
    print(f"Received reply: {message}")

if __name__ == "__main__":
    command = input("Enter command to send to the serial device: ")
    send_command(command)

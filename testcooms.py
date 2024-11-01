import zmq

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:5555")


socket.send_string("READ_PRESSURES")
try:
    response = socket.recv_string(zmq.NOBLOCK)  # Or use a timeout
    print("Received:", response)
except zmq.Again:
    print("Timeout: No response from the server")
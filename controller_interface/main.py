import serial
import math
import threading
import queue
import struct
import enum
import time

import argparse

class ControllerState(enum.Enum):
    IDLE = 0
    ACTIVE = 1
    ERROR = 2

PACKET_HEADER = '<HH'
PACKET_FOOTER = '<HH'
PACKET_DELIMITER = 0xF0F0
PACKET_DELIMETER_FOOTER = 0x0F0F

HEARTBEAT_PACKET_ID = 0x00
CONTROL_PACKET_ID = 0x01

class ControllerInterface: 
    def __init__(self, port, baudrate): 
        self.port = port
        self.baudrate = baudrate
        self.state = ControllerState.IDLE
        self.packet_queue = queue.Queue()
        self.heartbeat_thread = threading.Thread(target=self.heartbeat)
        self.broadcast_thread = threading.Thread(target=self.broadcast) 
        
    def create_packet(self, packet_id: int, payload: bytes) -> bytes:
        match packet_id:
            case 0x00:
                assert len(payload) == 0, "Heartbeat packet should not have payload"
            case 0x01:
                assert len(payload) == 4 * 1, "Control packet should have exactly 4 (8-bit) control values" 
        packet = struct.pack(PACKET_HEADER, PACKET_DELIMITER, packet_id) + payload + struct.pack(PACKET_FOOTER, packet_id, PACKET_DELIMITER)
        return packet

    def heartbeat(self):
        while self.state == ControllerState.ACTIVE:
            heartbeat_packet = self.create_packet(HEARTBEAT_PACKET_ID, b'')
            self.packet_queue.put(heartbeat_packet)
            time.sleep(0.25)

    def control(self, control_values: list[int]):
        assert len(control_values) == 4, "Control packet should have exactly 4 control values"
        payload = struct.pack('<' + 'B' * len(control_values), *control_values)
        control_packet = self.create_packet(CONTROL_PACKET_ID, payload)
        self.packet_queue.put(control_packet)

    def broadcast(self):
        srl = serial.Serial(self.port, self.baudrate)
        try:
            while self.state == ControllerState.ACTIVE:
                try:
                    packet = self.packet_queue.get(block=True, timeout=1.0)
                    srl.write(packet)
                    buf = list(bytearray(srl.read(12)))
                    print(buf) 
                except queue.Empty:
                    continue
        except Exception as e:
            pass
        finally:
            srl.close()
        
    def start(self):
        # Start the controller interface
        self.state = ControllerState.ACTIVE
        self.heartbeat_thread.start()
        self.broadcast_thread.start()
        print("Controller interface started.")

    def stop(self):
        # Stop the controller interface
        self.state = ControllerState.IDLE
        self.heartbeat_thread.join()
        self.broadcast_thread.join()
        print("Controller interface stopped.")


def main(): 
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Controller Interface')
    parser.add_argument('--port', type=str, default='/dev/ttyUSB0', help='Serial port to connect to the controller')
    parser.add_argument('--baudrate', type=int, default=115200, help='Baud rate for the serial connection')
    args = parser.parse_args()
    
    # Create a serial connection to the controller
    print(f"Connecting to controller on port {args.port} with baudrate {args.baudrate}...")
    controller_interface = ControllerInterface(args.port, args.baudrate)

    # Start the controller interface
    controller_interface.start()
    print("Press Ctrl+C to stop the controller interface.")
    try:
        t = 0.0
        last_time = time.time()
        while True:
            # Example control values (replace with actual control logic)
            new_time = time.time()
            t += 0.01 * (new_time - last_time)
            control_values = [
                int((1 + 0.5 * math.sin(t)) * 127),  # yaw (purple) (0-255)
                int((1 + 0.5 * math.cos(t)) * 127),  # height (blue) (0-255)
                int((1 + 0.5 * math.sin(2*t)) * 127), # forwards (green) (0-255)
                int((1 + 0.5 * math.cos(2*t)) * 127)  # strafe (yellow) (0-255)
            ]
            controller_interface.control(control_values)
            # print(controller_interface.read(), end='')  # Read and print any incoming data from the controller
            last_time = new_time
            time.sleep(1)  # Send control values every second
    except KeyboardInterrupt:
        pass
    finally:
        print("Stopping controller interface...")
        controller_interface.stop()
    
if __name__ == "__main__":
    main()
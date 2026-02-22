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
                    buf = srl.read_all()
                    if buf:
                        print(buf.decode('ascii', errors='ignore'), end='')  # Print any incoming data from the controller
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
    import pygame

    parser = argparse.ArgumentParser(description='Controller Interface')
    parser.add_argument('--port', type=str, default='/dev/ttyUSB0')
    parser.add_argument('--baudrate', type=int, default=115200)
    args = parser.parse_args()

    print(f"Connecting to controller on port {args.port} with baudrate {args.baudrate}...")
    controller_interface = ControllerInterface(args.port, args.baudrate)
    controller_interface.start()

    # --- Pygame setup ---
    pygame.init()
    screen = pygame.display.set_mode((400, 200))
    pygame.display.set_caption("Keyboard Controller")
    clock = pygame.time.Clock()

    print("Use WASD + Arrow keys. Ctrl+C to quit.")

    # Control state (centered)
    yaw = 127
    height = 127
    forward = 127
    strafe = 127

    step = 10          # how fast values change
    return_speed = 8   # how fast they return to center

    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    raise KeyboardInterrupt

            keys = pygame.key.get_pressed()

            # --- FORWARD (W/S) ---
            if keys[pygame.K_s]:
                forward += step
            elif keys[pygame.K_w]:
                forward -= step
            else:
                forward += (127 - forward) * 0.2

            # --- HEIGHT (UP/DOWN) ---
            if keys[pygame.K_UP]:
                height += step
            elif keys[pygame.K_DOWN]:
                height -= step
            else:
                height += (127 - height) * 0.2

            # --- STRAFE (A/D) ---
            if keys[pygame.K_d]:
                strafe += step
            elif keys[pygame.K_a]:
                strafe -= step
            else:
                strafe += (127 - strafe) * 0.2

            # --- Yaw (LEFT/RIGHT) ---
            if keys[pygame.K_RIGHT]:
                yaw += step
            elif keys[pygame.K_LEFT]:
                yaw -= step
            else:
                yaw += (127 - yaw) * 0.2

            # Clamp to 0–255
            yaw = int(max(0, min(255, yaw)))
            height = int(max(0, min(255, height)))
            forward = int(max(0, min(255, forward)))
            strafe = int(max(0, min(255, strafe)))

            control_values = [forward, strafe, height, yaw]

            controller_interface.control(control_values)
            print(f"\rSent control values: {control_values}", end="")

            clock.tick(20)  # 20 Hz update rate

    except KeyboardInterrupt:
        pass
    finally:
        print("\nStopping controller interface...")
        controller_interface.stop()
        pygame.quit()

    
if __name__ == "__main__":
    main()
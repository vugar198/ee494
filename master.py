import asyncio
import cv2
import pickle
import struct
import imutils
import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout
)

# === Default Values ===
default_slave_ips = [
    "192.168.1.110",
"192.168.1.113",
    "192.168.1.112"

]
default_ports = [9997, 9999, 9998]

# Global variables to be updated from GUI
slave_ips = []
ports = []

video_sources = [
"rtsp://electro1:electro1@192.168.1.100:554/stream1",
    "rtsp://electro3:electro3@192.168.1.106:554/stream1",
"rtsp://electro2:electro2@192.168.1.102:554/stream1"


]
payload_size = struct.calcsize("Q")
frame_skip = 0
slave_buffers = []


async def send_frames(writer, cap, slave_id):
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame = imutils.resize(frame, width=640)
        if slave_buffers[slave_id].full():
            try:
                slave_buffers[slave_id].get_nowait()
            except asyncio.QueueEmpty:
                pass
        await slave_buffers[slave_id].put(frame)
        for _ in range(frame_skip):
            cap.read()
        await asyncio.sleep(0.005)


async def frame_sender(writer, slave_id):
    while True:
        frame = await slave_buffers[slave_id].get()
        try:
            data = pickle.dumps(frame)
            message = struct.pack("Q", len(data)) + data
            writer.write(message)
            await writer.drain()
        except Exception as e:
            print(f"[Slave {slave_id}] Error sending frame: {e}")


async def handle_slave_connection(slave_id):
    try:
        reader, writer = await asyncio.open_connection(slave_ips[slave_id], ports[slave_id])
        print(f"[Slave {slave_id}] Connected")

        cap = cv2.VideoCapture(video_sources[slave_id])
        send_task = asyncio.create_task(send_frames(writer, cap, slave_id))
        sender_task = asyncio.create_task(frame_sender(writer, slave_id))
        await asyncio.gather(send_task, sender_task)
        writer.close()
        await writer.wait_closed()
        cap.release()
    except Exception as e:
        print(f"[Slave {slave_id}] Connection error: {e}")


async def main_async():
    global slave_buffers
    slave_buffers = [asyncio.Queue(maxsize=1) for _ in range(3)]
    await asyncio.gather(*(handle_slave_connection(i) for i in range(3)))


def launch_async_loop():
    asyncio.run(main_async())


# GUI Setup
class InputWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Slave Configuration Input")
        self.layout = QVBoxLayout()
        self.ip_edits = []
        self.port_edits = []

        for i in range(3):
            row = QHBoxLayout()
            ip_edit = QLineEdit()
            ip_edit.setPlaceholderText(f"Slave {i+1} IP")
            ip_edit.setText(default_slave_ips[i])
            port_edit = QLineEdit()
            port_edit.setPlaceholderText(f"Port {i+1}")
            port_edit.setText(str(default_ports[i]))
            self.ip_edits.append(ip_edit)
            self.port_edits.append(port_edit)
            row.addWidget(QLabel(f"Slave {i+1}:"))
            row.addWidget(ip_edit)
            row.addWidget(port_edit)
            self.layout.addLayout(row)

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_clicked)
        self.layout.addWidget(self.start_button)
        self.setLayout(self.layout)

    def start_clicked(self):
        global slave_ips, ports
        try:
            slave_ips[:] = [ip.text().strip() for ip in self.ip_edits]
            ports[:] = [int(port.text().strip()) for port in self.port_edits]
            self.close()
            launch_async_loop()
        except Exception as e:
            print("Invalid input:", e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = InputWindow()
    window.show()
    sys.exit(app.exec())
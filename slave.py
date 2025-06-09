import asyncio
import os
from datetime import datetime
import pickle
import struct
import cv2
import numpy as np
import json
import time
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort
from counterline_V2 import detect_walkway_and_save
from uploadLog import uploadLog
import tkinter as tk
from tkinter import messagebox
#from alarm_test import set_volume, pause, resume, play_track

walkway_model = YOLO("best.pt")
human_model = YOLO("yolov8m.pt")
tracker = DeepSort(max_age=20)


incident_logs = {}
has_been_inside = {}
violation_timer = {}          # Track unsafe timer
violation_triggered = {}      # Track if violation was triggered

def get_user_inputs():
    def submit():
        try:
            ip_val = ip_entry.get()
            port_val = int(port_entry.get())
            scale_val_x = float(scaling_entry_x.get())
            scale_val_y = float(scaling_entry_y.get())
            wait_val = float(wait_entry.get())

            if not ip_val:
                raise ValueError("IP address is required")

            inputs["ip"] = ip_val
            inputs["port"] = port_val
            inputs["scaling_factor_x"] = scale_val_x
            inputs["scaling_factor_y"] = scale_val_y
            inputs["violation_wait_time"] = wait_val

            root.destroy()
        except Exception as e:
            messagebox.showerror("Input Error", str(e))

    inputs = {}

    root = tk.Tk()
    root.title("Slave Server Configuration")
    root.geometry("400x400")
    root.resizable(False, False)

    tk.Label(root, text="Enter IP Address:").pack(pady=(20, 0))
    ip_entry = tk.Entry(root, width=30)
    ip_entry.insert(0, "192.168.1.110")
    ip_entry.pack()

    tk.Label(root, text="Enter Port:").pack(pady=(10, 0))
    port_entry = tk.Entry(root, width=30)
    port_entry.insert(0, "9997")
    port_entry.pack()

    tk.Label(root, text="Enter Scaling Factor X:").pack(pady=(10, 0))
    scaling_entry_x = tk.Entry(root, width=30)
    scaling_entry_x.insert(0, "1")
    scaling_entry_x.pack()

    tk.Label(root, text="Enter Scaling Factor Y:").pack(pady=(10, 0))
    scaling_entry_y = tk.Entry(root, width=30)
    scaling_entry_y.insert(0, "1")
    scaling_entry_y.pack()

    tk.Label(root, text="Violation Wait Time (seconds):").pack(pady=(10, 0))
    wait_entry = tk.Entry(root, width=30)
    wait_entry.insert(0, "1.0")
    wait_entry.pack()

    submit_btn = tk.Button(root, text="Start Server", command=submit)
    submit_btn.pack(pady=20)

    root.mainloop()

    if not inputs:
        exit(1)

    return inputs["ip"], inputs["port"], inputs["scaling_factor_x"], inputs["scaling_factor_y"], inputs["violation_wait_time"]

def is_point_in_walkway(x, y, walkway_contours):
    for contour in walkway_contours.values():
        polygon = np.array([[pt["x"], pt["y"]] for pt in contour], dtype=np.int32)
        if cv2.pointPolygonTest(polygon, (x, y), False) >= 0:
            return True
    return False

def log_incident(person_id, time_increment):
    if person_id not in incident_logs:
        incident_logs[person_id] = {"time_spent": 0}
    incident_logs[person_id]["time_spent"] += time_increment

def initialize_walkway(frame):
    detect_walkway_and_save(frame, "walkway_contours.json", scaling_factor_x, scaling_factor_y)
    with open("walkway_contours.json", "r") as f:
        return json.load(f)

def save_violation_frame(frame, track_id, box):
    os.makedirs("violations", exist_ok=True)
    annotated_frame = frame.copy()
    (x1, y1, x2, y2) = box
    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 0, 255), 1)
    text = f"VIOLATION DETECTED (ID {track_id})"
    cv2.putText(annotated_frame, text, (x1, max(y1 - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX,
                0.4, (0, 0, 255), 1)

    # Create filename with current datetime and track ID
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_name = f"{timestamp}_ID{track_id}.jpg"
    file_path = os.path.join("violations", file_name)

    file_path_log = [fr"violations{file_name}"]
    # Save the annotated frame
    cv2.imwrite(file_path, annotated_frame)
    print(f"[INFO] Saved violation frame with annotation: {file_path}")
    #turn_on_alarm()
    uploadLog([f"C:\\Users\\dogan\\Documents\\PythonProjects\\YOLO-Project1\\Project_05_02\\violations\\{file_name}"])

def process_frame(frame, walkway_contours, fps=30):
    results = human_model.predict(source=frame, save=False, show=False, classes=[0])

    detections = []
    for result in results:
        boxes = result.boxes.xyxy.cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()
        for box, confidence in zip(boxes, confidences):
            if confidence >= 0.7:
                x1, y1, x2, y2 = map(int, box)
                detections.append(([x1, y1, x2 - x1, y2 - y1], confidence, "person"))

    tracks = tracker.update_tracks(detections, frame=frame)

    current_time = time.time()

    for track in tracks:
        if not track.is_confirmed():
            continue
        track_id = track.track_id
        x1, y1, w, h = track.to_ltwh()
        x2, y2 = int(x1 + w), int(y1 + h)
        x1, y1 = int(x1), int(y1)
        foot_x, foot_y = int((x1 + x2) / 2), y2

        is_safe = is_point_in_walkway(foot_x, foot_y, walkway_contours)

        # Update has_been_inside
        if track_id not in has_been_inside:
            has_been_inside[track_id] = False
        if is_safe:
            has_been_inside[track_id] = True

        # Only track if ever inside
        if has_been_inside[track_id]:
            if not is_safe:
                if track_id not in violation_timer:
                    violation_timer[track_id] = current_time
                    violation_triggered[track_id] = False

                elapsed_time = current_time - violation_timer[track_id]

                if elapsed_time >= violation_wait_time and not violation_triggered[track_id]:
                    # Violation detected!
                    log_incident(track_id, violation_wait_time)
                    save_violation_frame(frame, track_id, (x1, y1, x2, y2))
                    violation_triggered[track_id] = True  # Prevent double-triggering for SAME exit
            else:
                # Back to safe zone -> reset timers
                violation_timer.pop(track_id, None)
                violation_triggered.pop(track_id, None)

        # ==== Drawing labels and boxes ====
        if is_safe:
            color = (0, 255, 0)
            label = f"ID: {track_id} Safe"
        else:
            if has_been_inside.get(track_id, False):
                if violation_triggered.get(track_id, False):
                    color = (0, 0, 255)
                    #play_track(2)
                    label = f"ID: {track_id} Unsafe"
                else:
                    color = (0, 255, 255)
                    #play_track(1)
                    label = f"ID: {track_id} Exiting"
            else:
                color = (128, 128, 128)
                label = f"ID: {track_id} Ignored"

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)
        cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
        cv2.circle(frame, (foot_x, foot_y), 2, (255, 0, 255), -1)

        if not is_safe and has_been_inside.get(track_id, False):
            if not violation_triggered.get(track_id, False):
                time_remaining = violation_wait_time - (current_time - violation_timer[track_id])
                time_remaining = max(time_remaining, 0)
                countdown_text = f"Violation in {time_remaining:.1f}s"
                cv2.putText(frame, countdown_text, (x1, y1 - 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 255), 1)
            else:
                countdown_text = "Violation detected!"
                cv2.putText(frame, countdown_text, (x1, y1 - 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)

    # Draw Walkway
    for contour in walkway_contours.values():
        polygon = np.array([[pt["x"], pt["y"]] for pt in contour], dtype=np.int32)
        cv2.polylines(frame, [polygon], isClosed=True, color=(0, 255, 0), thickness=1)

    return frame

async def handle_master_connection(reader, _):
    print("[Slave] Connected to master.")
    payload_size = struct.calcsize("Q")
    walkway_initialized = False
    walkway_contours = None
    fps = 30
    buffer = b""

    try:
        while True:
            while len(buffer) < payload_size:
                buffer += await reader.read(1024)
            packed_size = buffer[:payload_size]
            buffer = buffer[payload_size:]
            msg_size = struct.unpack("Q", packed_size)[0]

            while len(buffer) < msg_size:
                buffer += await reader.read(1024)
            frame_data = buffer[:msg_size]
            buffer = buffer[msg_size:]

            frame = pickle.loads(frame_data)

            if not walkway_initialized:
                walkway_contours = initialize_walkway(frame)
                walkway_initialized = True

            processed = process_frame(frame, walkway_contours, fps)
            processed = cv2.resize(processed, (1200, 900))
            cv2.imshow("Processed Video", processed)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except Exception as e:
        print(f"[Slave] Error: {e}")
    finally:
        cv2.destroyAllWindows()

async def start_slave_server(ip, port):
    server = await asyncio.start_server(handle_master_connection, ip, port)
    print(f"[Slave] Listening on {ip}:{port}")
    async with server:
        await server.serve_forever()

if _name_ == "_main_":
    ip, port, scaling_factor_x, scaling_factor_y, violation_wait_time = get_user_inputs()
    asyncio.run(start_slave_server(ip, port))
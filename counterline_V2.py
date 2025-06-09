from ultralytics import YOLO
import cv2
import numpy as np
import json

# Load the trained YOLO model for walkway detection
walkway_model = YOLO("best.pt")  # Replace with the correct path to your best.pt file

# Function to find a frame with walkway confidence >= 0.7
def find_suitable_frame(video_path, confidence_threshold=0.7, start_frame=1, max_frames=100):
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"Error: Unable to open video {video_path}")
        return None


    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret or frame_idx >= max_frames:  # Stop after processing max_frames
            print(f"No suitable frame found after {max_frames} frames.")
            break

        frame_idx += 1
        if frame_idx < start_frame:
            continue  # Skip frames before the start_frame

        # Perform YOLO detection on the current frame
        results = walkway_model.predict(source=frame, save=False, show=False)
        detections = results[0].boxes.data.cpu().numpy()  # Get detection data

        # Check if any detection meets the confidence threshold
        for detection in detections:
            confidence = detection[4]  # Confidence score
            if confidence >= confidence_threshold:
                cap.release()
                print(f"Selected frame {frame_idx} with confidence {confidence:.2f}")
                return frame

    cap.release()
    print(f"No frame found with confidence >= {confidence_threshold}")
    return None

# Function to detect walkway contours and save them
def detect_walkway_and_save(image, output_coordinates_path, scaling_factor_x=1, scaling_factor_y=1):
    original_height, original_width = image.shape[:2]

    # Perform detection
    results = walkway_model.predict(source=image, save=False, show=False)

    # Initialize a dictionary to store contour coordinates
    all_coordinates = {}

    # Process results to extract contour coordinates
    for idx, result in enumerate(results):
        if result.masks:  # Ensure masks are available
            masks = result.masks.data.cpu().numpy()

            for mask_idx, mask in enumerate(masks):
                # Resize the mask to match the original image dimensions
                mask_resized = cv2.resize(mask, (original_width, original_height), interpolation=cv2.INTER_NEAREST)
                mask_resized = (mask_resized > 0.5).astype(np.uint8) * 255

                # Find contours
                contours, _ = cv2.findContours(mask_resized, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                for contour_idx, contour in enumerate(contours):
                    # Calculate centroid for Y-scaling
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                    else:
                        cx, cy = 0, 0  # fallback

                    # Scale only Y coordinates of each point
                    contour_scaled = []
                    for pt in contour:
                        px, py = pt[0]
                        x_new = cx + scaling_factor_x * (px - cx)
                        y_new = cy + scaling_factor_y * (py - cy)
                        contour_scaled.append([[int(x_new), int(y_new)]])

                    contour_scaled = np.array(contour_scaled, dtype=np.int32)
                    contour_coords = [{"x": int(pt[0][0]), "y": int(pt[0][1])} for pt in contour_scaled]
                    all_coordinates[f"mask_{mask_idx}contour{contour_idx}"] = contour_coords

    # Save coordinates to a JSON file
    with open(output_coordinates_path, "w") as f:
        json.dump(all_coordinates, f, indent=4)
        print(f"Coordinates saved to {output_coordinates_path}")
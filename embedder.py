import sqlite3
import torch
import os
import cv2
import numpy as np
from PIL import Image
from sentence_transformers import SentenceTransformer

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"--- Using Device: {device.upper()} ---")

model = SentenceTransformer('clip-ViT-B-32', device=device)

conn = sqlite3.connect('media.db')
cursor = conn.cursor()
cursor.execute("SELECT id, path FROM media WHERE embedding IS NULL AND (path LIKE '%.jpeg' OR path LIKE '%.mp4')")
rows = cursor.fetchall()
print(f"Found {len(rows)} items to process.")

def get_video_frame(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 10)
    
    ret, frame = cap.read()
    cap.release()
    if ret:
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    return None

for row_id, linux_path in rows:
    filename = os.path.basename(linux_path)
    
    if linux_path.endswith('.jpeg'):
        local_path = os.path.join("Screens", filename)
    else:
        local_path = filename 

    if not os.path.exists(local_path):
        print(f"Skipping (not found): {local_path}")
        continue

    try:
        if local_path.endswith('.mp4'):
            img = get_video_frame(local_path)
        else:
            img = Image.open(local_path).convert("RGB")

        if img:
            embedding = model.encode(img)
            cursor.execute("UPDATE media SET embedding = ? WHERE id = ?", (embedding.tobytes(), row_id))
            conn.commit()
            print(f"Embedded: {filename}")
        else:
            print(f"Failed to extract frame from: {filename}")

    except Exception as e:
        print(f"Error {filename}: {e}")

conn.close()
print("Finished")

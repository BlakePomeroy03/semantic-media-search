import sqlite3
import torch
import os
from PIL import Image
from sentence_transformers import SentenceTransformer

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using GPU: {device.upper()} ---")

model = SentenceTransformer('clip-ViT-B-32', device=device)

conn = sqlite3.connect('media.db')
cursor = conn.cursor()

cursor.execute("SELECT id, path FROM media WHERE embedding IS NULL AND path LIKE '%.jpeg'")
rows = cursor.fetchall()
print(f"Found {len(rows)} images to process.")

for row_id, linux_path in rows:
    filename = os.path.basename(linux_path)
    local_path = os.path.join("Screens", filename)

    if not os.path.exists(local_path):
        continue

    try:
        img = Image.open(local_path).convert("RGB")
        embedding = model.encode(img)
        cursor.execute("UPDATE media SET embedding = ? WHERE id = ?", (embedding.tobytes(), row_id))
        conn.commit()
        print(f"Embedded: {filename}")
    except Exception as e:
        print(f"Error {filename}: {e}")

conn.close()
print("Finished")

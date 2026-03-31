import sqlite3
import torch
import numpy as np
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('clip-ViT-B-32', device='cpu')

conn = sqlite3.connect('media.db')
cursor = conn.cursor()

cursor.execute("SELECT path, embedding FROM media WHERE embedding IS NOT NULL")
rows = cursor.fetchall()

paths = []
embeddings = []

for path, emb_blob in rows:
    paths.append(path)
    embeddings.append(np.frombuffer(emb_blob, dtype=np.float32))

img_embeddings = torch.from_numpy(np.stack(embeddings))

while True:
    query = input("\nEnter search term (or 'q' to quit): ")
    if query == 'q': break

    query_emb = model.encode(query, convert_to_tensor=True)

    hits = util.semantic_search(query_emb, img_embeddings, top_k=5)[0]

    print(f"\nTop results for '{query}':")
    for hit in hits:
        print(f"{hit['score']:.3f} | {paths[hit['corpus_id']]}")

conn.close()

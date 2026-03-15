# check_qdrant.py
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from qdrant_client import QdrantClient
import config

qdrant = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)

print("\n=== Qdrant Collections ===")
collections = qdrant.get_collections().collections

if not collections:
    print("No collections found — database is empty. Run seed_data.py first.")
else:
    for c in collections:
        info = qdrant.get_collection(c.name)
        print(f"\nCollection : {c.name}")
        print(f"Points     : {info.points_count}")
        print(f"Vector size: {info.config.params.vectors.size}")
        print(f"Distance   : {info.config.params.vectors.distance}")

        if info.points_count > 0:
            # Peek at first stored point
            sample = qdrant.scroll(
                collection_name=c.name,
                limit=1,
                with_payload=True,
                with_vectors=True
            )[0]
            if sample:
                p = sample[0]
                vec = p.vector
                print(f"Sample vector length : {len(vec)}")
                print(f"Sample vector (first 5 values): {[round(v,4) for v in vec[:5]]}")
                print(f"Sample payload keys : {list(p.payload.keys())}")
                print(f"Sample text preview : {p.payload.get('text','')[:80]}...")
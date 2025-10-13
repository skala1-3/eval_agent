# scripts/reset_chroma.py
import os
import chromadb

DB_PATH = os.path.join(os.getcwd(), "db", "chroma_db")
COLLECTION = "financial_companies_evidence"

if __name__ == "__main__":
    client = chromadb.PersistentClient(path=DB_PATH)
    try:
        client.delete_collection(COLLECTION)
        print(f"[OK] deleted collection: {COLLECTION}")
    except Exception as e:
        print(f"[WARN] delete_collection failed or not exists: {e}")

    client.get_or_create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    print(f"[OK] recreated collection: {COLLECTION} at {DB_PATH}")

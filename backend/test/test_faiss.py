"""
Build and query a FAISS index from MySQL papers.

Usage (from project root):
  python -m backend.test.test_faiss

Requires:
- MySQL has papers data (paper_id, title, abstract)
- Dependencies installed: faiss-cpu, sentence-transformers, numpy
"""
from __future__ import annotations

import os
import sys

# Make sure backend/ is importable when running directly
CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from service.dbmanager import DbManager  # noqa: E402
from service.faiss_index import FaissIndex  # noqa: E402


def main():
    db = DbManager()

    fi = FaissIndex()  # reads model/index_dir/normalize from config.yaml (embeddings section)

    print("[1/3] Building FAISS index from DB (title + abstract)...")
    try:
        n, dim = fi.build_from_db(db)
        print(f"    OK. vectors={n}, dim={dim}")
    except Exception as e:
        print(f"    Failed to build: {e}")
        return

    print("[2/3] Running a sample search...")
    query = "large language models for recommendation"
    hits = fi.search(query, k=5)
    print(f"    query='{query}'")
    print(f"    hits(raw): {hits}")

    if not hits:
        print("[WARN] No hits returned.")
        return

    # Fetch details from DB
    ids = tuple(pid for pid, _ in hits)
    placeholders = ",".join(["%s"] * len(ids))
    sql = f"SELECT paper_id, title FROM papers WHERE paper_id IN ({placeholders})"
    rows = db.query_all(sql, ids)
    title_map = {r["paper_id"]: r.get("title") for r in rows}

    print("[3/3] Results:")
    for pid, score in hits:
        print(f"  paper_id={pid:>5}  score={score:.4f}  title={title_map.get(pid, '<unknown>')}")


if __name__ == "__main__":
    main()

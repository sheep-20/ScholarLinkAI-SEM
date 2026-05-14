from __future__ import annotations

import json
from typing import List, Dict, Any, Optional
import numpy as np

from service.dbmanager import DbManager
from service.openrouter_embedding import OpenRouterEmbedding


class SearchService:
    """
    简单语义搜索服务：
    - 将query转为embedding
    - 与paper_embeddings做点积相似度
    - 返回topk论文，同时附带（若有）最新的博客内容
    """

    def __init__(self) -> None:
        self.db = DbManager()
        self.embedding = OpenRouterEmbedding()

    def search(self, query: str, topk: int = 5) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            return []
        try:
            q_vec = self.embedding.embed_text(query.strip(), normalize=True)
        except Exception:
            return []

        # 预取所有论文embedding
        papers = self.db.query_all(
            """
            SELECT pe.paper_id, pe.embedding, p.title, p.abstract, p.author, p.pdf_url
            FROM paper_embeddings pe
            JOIN papers p ON pe.paper_id = p.paper_id
            WHERE pe.embedding IS NOT NULL
            """
        )

        if not papers:
            return []

        # 预取最新博客（如果有）按 paper_id
        blog_rows = self.db.query_all(
            """
            SELECT r.id, r.paper_id, r.blog, r.user_id
            FROM recommendations r
            WHERE r.blog IS NOT NULL
            ORDER BY r.created_at DESC
            """
        )
        blog_map: Dict[int, Dict[str, Any]] = {}
        for r in blog_rows:
            pid = r.get("paper_id")
            if pid and pid not in blog_map:
                blog_map[pid] = {"id": r.get("id"), "blog": r.get("blog"), "user_id": r.get("user_id")}

        q_arr = np.array(q_vec)
        results: List[Dict[str, Any]] = []

        for p in papers:
            try:
                emb = p.get("embedding")
                if isinstance(emb, str):
                    emb = json.loads(emb)
                p_vec = np.array(emb)
                if p_vec.shape != q_arr.shape:
                    continue
                sim = float(np.dot(q_arr, p_vec))
                pid = p["paper_id"]
                blog_info = blog_map.get(pid) or {}
                results.append({
                    "id": blog_info.get("id"),
                    "paper_id": pid,
                    "title": p.get("title"),
                    "abstract": p.get("abstract"),
                    "author": p.get("author"),
                    "pdf_url": p.get("pdf_url"),
                    "similarity": sim,
                    "blog": blog_info.get("blog"),
                    "blog_user_id": blog_info.get("user_id"),
                })
            except Exception:
                continue

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:max(1, min(topk, 50))]


__all__ = ["SearchService"]


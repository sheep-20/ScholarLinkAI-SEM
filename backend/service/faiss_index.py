"""
FAISS vector index builder/searcher for papers.

- Reads MySQL data using DbManager (title + abstract)
- Encodes with sentence-transformers (default: all-MiniLM-L6-v2)
- Builds FAISS index (cosine via normalized + inner product)
- Saves index files to disk and provides load/search APIs

Config (config.yaml):
embeddings:
  model: sentence-transformers/all-MiniLM-L6-v2
  index_dir: backend/service/index
  normalize: true
proxy:                   # 可选，与项目其余部分一致
  enable: true
  host: 127.0.0.1
  port: 7890
  scheme: http

Usage (programmatic):
    from service.faiss_index import FaissIndex
    from service.dbmanager import DbManager

    db = DbManager()
    fi = FaissIndex()  # reads config.yaml
    fi.build_from_db(db)  # build and save

    hits = fi.search("large language models for recommendation", k=5)
    print(hits)  # [(paper_id, score), ...]

CLI runner is provided in backend/test/test_faiss.py
"""
from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional, Tuple

# env
try:
    from dotenv import load_dotenv  # type: ignore
    for _p in [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    ]:
        env_path = os.path.join(_p, ".env")
        if os.path.isfile(env_path):
            load_dotenv(env_path)
            break
    else:
        load_dotenv()
except Exception:
    pass

# yaml
try:
    import yaml  # type: ignore
except Exception:
    yaml = None

import numpy as np

try:
    import faiss  # type: ignore
except Exception as e:  # pragma: no cover
    raise RuntimeError("缺少 faiss-cpu 依赖，请先执行: pip install faiss-cpu")

try:
    from sentence_transformers import SentenceTransformer
except Exception as e:  # pragma: no cover
    raise RuntimeError("缺少 sentence-transformers 依赖，请先执行: pip install sentence-transformers")

from .dbmanager import DbManager


def _project_roots() -> List[str]:
    base = os.path.dirname(__file__)
    return [
        os.path.abspath(os.path.join(base, "..", "..")),
        os.path.abspath(os.path.join(base, "..")),
        os.path.abspath(os.path.join(base, ".")),
    ]


def _load_yaml() -> Optional[Dict[str, Any]]:
    for root in _project_roots():
        cfg = os.path.join(root, "config.yaml")
        if os.path.isfile(cfg):
            if yaml is None:
                raise RuntimeError("检测到 config.yaml，但未安装 PyYAML。请先执行: pip install PyYAML")
            with open(cfg, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return None


def _resolve_conf() -> Dict[str, Any]:
    # defaults
    conf: Dict[str, Any] = {
        "model": os.getenv("EMBEDDING_LOCAL_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        "index_dir": os.getenv("FAISS_INDEX_DIR", os.path.join(os.path.dirname(__file__), "index")),
        "normalize": True,
    }
    try:
        data = _load_yaml() or {}
        emb = data.get("embeddings") or {}
        if isinstance(emb, dict):
            conf["model"] = emb.get("model", conf["model"]) or conf["model"]
            conf["index_dir"] = emb.get("index_dir", conf["index_dir"]) or conf["index_dir"]
            if "normalize" in emb:
                conf["normalize"] = bool(emb.get("normalize"))
    except Exception:
        pass
    return conf


def _resolve_proxy_url() -> Optional[str]:
    try:
        data = _load_yaml() or {}
        pxy = data.get("proxy") or {}
        if isinstance(pxy, dict):
            if pxy.get("enable") is False:
                return None
            if pxy.get("url"):
                return str(pxy["url"]).strip()
            host = str(pxy.get("host", "")).strip()
            port = pxy.get("port")
            scheme = str(pxy.get("scheme", "http")).strip() or "http"
            if host and port:
                return f"{scheme}://{host}:{int(port)}"
    except Exception:
        pass
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
        val = os.getenv(key)
        if val:
            return val
    return None


def _apply_proxy_env():
    proxy = _resolve_proxy_url()
    if proxy:
        os.environ["HTTPS_PROXY"] = proxy
        os.environ["HTTP_PROXY"] = proxy
        os.environ["ALL_PROXY"] = proxy


class FaissIndex:
    def __init__(self, model_name: Optional[str] = None, index_dir: Optional[str] = None, normalize: Optional[bool] = None):
        _apply_proxy_env()
        cfg = _resolve_conf()
        self.model_name = model_name or cfg["model"]
        self.index_dir = os.path.abspath(index_dir or cfg["index_dir"])
        self.normalize = normalize if normalize is not None else cfg["normalize"]
        self.model = SentenceTransformer(self.model_name)
        self.index: Optional[faiss.Index] = None
        self.id_map: List[int] = []  # faiss idx -> paper_id

        self._index_path = os.path.join(self.index_dir, "papers.faiss")
        self._idmap_path = os.path.join(self.index_dir, "id_map.json")
        self._meta_path = os.path.join(self.index_dir, "meta.json")

    def _ensure_dir(self):
        os.makedirs(self.index_dir, exist_ok=True)

    def _encode(self, texts: List[str]) -> np.ndarray:
        emb = self.model.encode(texts, normalize_embeddings=self.normalize)
        emb = np.asarray(emb, dtype="float32")
        return emb

    def build_from_db(self, db: DbManager) -> Tuple[int, int]:
        rows = db.query_all("SELECT paper_id, title, abstract FROM papers")
        pairs: List[Tuple[int, str]] = []
        for r in rows:
            pid = r.get("paper_id")
            txt = f"{r.get('title') or ''} \n {r.get('abstract') or ''}".strip()
            if pid and txt:
                pairs.append((int(pid), txt))
        if not pairs:
            raise RuntimeError("没有可用的论文内容来构建索引（title/abstract 均为空）")

        paper_ids = [pid for pid, _ in pairs]
        texts = [t for _, t in pairs]

        vecs = self._encode(texts)
        dim = int(vecs.shape[1])

        # cosine similarity via inner product on normalized vectors
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(vecs)
        self.id_map = paper_ids

        self._ensure_dir()
        faiss.write_index(self.index, self._index_path)
        with open(self._idmap_path, "w", encoding="utf-8") as f:
            json.dump(self.id_map, f)
        with open(self._meta_path, "w", encoding="utf-8") as f:
            json.dump({"dim": dim, "normalize": self.normalize, "model": self.model_name}, f)

        return len(paper_ids), dim

    def load(self) -> None:
        if not (os.path.isfile(self._index_path) and os.path.isfile(self._idmap_path)):
            raise FileNotFoundError("索引文件不存在，请先构建索引")
        self.index = faiss.read_index(self._index_path)
        with open(self._idmap_path, "r", encoding="utf-8") as f:
            self.id_map = json.load(f)

    def search(self, query: str, k: int = 5) -> List[Tuple[int, float]]:
        if self.index is None:
            self.load()
        qv = self._encode([query])  # (1, dim)
        scores, idxs = self.index.search(qv, k)  # type: ignore
        res: List[Tuple[int, float]] = []
        for s, i in zip(scores[0], idxs[0]):
            if int(i) == -1:
                continue
            res.append((int(self.id_map[int(i)]), float(s)))
        return res


__all__ = ["FaissIndex"]

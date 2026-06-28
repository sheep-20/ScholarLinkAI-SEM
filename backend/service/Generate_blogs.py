from __future__ import annotations

import os
import io
from typing import Any, Dict, Optional, List

# .env
try:
    from dotenv import load_dotenv  # type: ignore
    for _p in [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),  # project root
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),          # backend
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),           # service
    ]:
        env_path = os.path.join(_p, ".env")
        if os.path.isfile(env_path):
            load_dotenv(env_path)
            break
    else:
        load_dotenv()
except Exception:
    pass

# YAML
try:
    import yaml  # type: ignore
except Exception:
    yaml = None

# HTTP + PDF
import requests
from pypdf import PdfReader

# OpenAI SDK (>=1.0.0)
from openai import OpenAI


# -------------- config helpers --------------

def _roots() -> List[str]:
    base = os.path.dirname(__file__)
    return [
        os.path.abspath(os.path.join(base, "..", "..")),
        os.path.abspath(os.path.join(base, "..")),
        os.path.abspath(os.path.join(base, ".")),
    ]


def _load_yaml() -> Optional[Dict[str, Any]]:
    for r in _roots():
        cfg = os.path.join(r, "config.yaml")
        if os.path.isfile(cfg):
            if yaml is None:
                raise RuntimeError("检测到 config.yaml，但未安装 PyYAML。pip install PyYAML")
            with open(cfg, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return None


def _resolve_openai_conf() -> Dict[str, Any]:
    conf: Dict[str, Any] = {
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "base_url": os.getenv("OPENAI_API_BASE", ""),
        "model": os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
        "timeout": 60,
        "language": "zh",
    }
    try:
        data = _load_yaml() or {}
        oa = data.get("openai") or {}
        if isinstance(oa, dict):
            conf["api_key"] = oa.get("api_key", conf["api_key"]) or conf["api_key"]
            conf["base_url"] = oa.get("base_url", conf["base_url"]) or conf["base_url"]
            conf["model"] = oa.get("chat_model", conf["model"]) or conf["model"]
            conf["timeout"] = int(oa.get("timeout", conf["timeout"]))
            conf["language"] = oa.get("language", conf["language"]) or conf["language"]
        sk = data.get("secret_key") or {}
        if isinstance(sk, dict):
            if sk.get("openai_api") or sk.get("openai_api_key"):
                conf["api_key"] = sk.get("openai_api") or sk.get("openai_api_key")
    except Exception:
        pass
    if not conf["api_key"]:
        raise RuntimeError("未找到 OPENAI_API_KEY，请在 config.yaml 或 .env 中配置")
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
    for k in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
        if os.getenv(k):
            return os.getenv(k)
    return None


def _apply_proxy_env():
    proxy = _resolve_proxy_url()
    if proxy:
        os.environ["HTTPS_PROXY"] = proxy
        os.environ["HTTP_PROXY"] = proxy
        os.environ["ALL_PROXY"] = proxy


# -------------- core helpers --------------

def _download_pdf(url: str, timeout: int) -> bytes:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def _extract_text(pdf_bytes: bytes, max_pages: Optional[int] = None) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    out: List[str] = []
    for i, p in enumerate(reader.pages):
        if max_pages is not None and i >= max_pages:
            break
        try:
            t = p.extract_text() or ""
        except Exception:
            t = ""
        if t:
            out.append(t)
    return "\n\n".join(out)


def _chunk(text: str, size: int = 8000) -> List[str]:
    text = text.strip()
    if not text:
        return []
    chunks: List[str] = []
    i, n = 0, len(text)
    while i < n:
        j = min(i + size, n)
        chunks.append(text[i:j])
        i = j
    return chunks


def _sys_prompt(lang: str) -> str:
    if lang.lower().startswith("zh"):
        return (
            "你是一名资深的学术科普写作者，擅长将论文内容转化为通俗易懂、结构清晰的技术博客。"
            "请严格按照要求输出高质量、可直接发布的 Markdown 中文博客。"
        )
    return (
        "You are a senior technical writer who turns academic papers into clear, engaging blog posts."
        "Output high-quality, publish-ready Markdown."
    )


def _chunk_prompt(chunk: str, lang: str) -> List[Dict[str, str]]:
    if lang.lower().startswith("zh"):
        user = (
            "请阅读以下论文片段，提取核心要点（中文）：\n\n"
            f"{chunk}\n\n"
            "请输出：\n- 关键术语\n- 主要方法或思想\n- 实验或评估要点\n- 结论/启示\n（用紧凑的要点列表，勿超过200字）"
        )
    else:
        user = (
            "Read the following paper chunk and extract key points (English):\n\n"
            f"{chunk}\n\n"
            "Output bullet points: terms, methods/ideas, experiments/evaluations, conclusions (<= 120 words)."
        )
    return [
        {"role": "system", "content": _sys_prompt(lang)},
        {"role": "user", "content": user},
    ]


def _final_prompt(merged: str, pdf_url: str, lang: str) -> List[Dict[str, str]]:
    if lang.lower().startswith("zh"):
        user = f"""
根据以下要点，撰写一篇结构完整的中文技术博客（Markdown）：
原文链接：{pdf_url}

要点汇总：
{merged}

写作要求：
- 面向有一定基础的工程师与研究生
- 采用通俗、准确、具体的语言，不要空话
- 必须包含以下章节（使用二级与三级标题组织）：
  1. 摘要与核心贡献
  2. 背景与动机
  3. 方法原理（文本化解释关键公式/流程）
  4. 实验设置与结果解读（定量/定性，对比方法）
  5. 局限性与潜在改进
  6. 应用场景与实践建议
  7. 相关工作与对比
  8. TL;DR（3-5条要点）
- 输出纯 Markdown
"""
    else:
        user = f"""
Based on the following points, write a well-structured technical blog post in Markdown.
Link: {pdf_url}

Key points:
{merged}

Sections: Summary, Background, Method, Experiments, Limitations, Applications, Related Work, TL;DR (3-5 bullets)
"""
    return [
        {"role": "system", "content": _sys_prompt(lang)},
        {"role": "user", "content": user},
    ]


class BlogGenerator:
    def __init__(self, model: Optional[str] = None, language: Optional[str] = None) -> None:
        _apply_proxy_env()
        conf = _resolve_openai_conf()
        self.model = model or conf["model"]
        self.language = language or conf["language"]
        if conf.get("base_url"):
            self.client = OpenAI(api_key=conf["api_key"], base_url=conf["base_url"])  # type: ignore
        else:
            self.client = OpenAI(api_key=conf["api_key"])  # type: ignore
        self.timeout = conf["timeout"]

    def generate_from_pdf_url(self, pdf_url: str) -> str:
        # 1) 下载
        pdf_bytes = _download_pdf(pdf_url, timeout=self.timeout)
        # 2) 提取文本
        text = _extract_text(pdf_bytes)
        if not text:
            raise RuntimeError("未能从该 PDF 中提取到文本")
        # 3) 分段
        chunks = _chunk(text, size=8000)
        # 仅使用第一个分块，直接单次成文调用（牺牲完整性，减少调用次数）
        chunk_text = (chunks[:1] or [""])[0]
        if not chunk_text:
            raise RuntimeError("未能获取首个文本分块")

        # 单轮提示：直接让模型基于首块文本生成博客
        if self.language.lower().startswith("zh"):
            user_prompt = f"""
        请阅读以下论文片段（可能不完整），直接生成一篇可发布的中文技术博客（Markdown）：
        原文链接：{pdf_url}

        片段：
        {chunk_text}

        写作要求：
        - 面向有一定基础的工程师与研究生
        - 结构包含：摘要与核心贡献、背景与动机、方法原理、实验与结果解读、局限与改进、应用场景、相关工作、TL;DR（3-5条）
        - 语言通俗准确，避免空话，正文不超过1500字
        """
        else:
            user_prompt = f"""
        Read the following (possibly partial) paper chunk and write a publishable technical blog in Markdown:
        Link: {pdf_url}

        Chunk:
        {chunk_text}

        Sections: summary/contribution, background, method, experiments/results, limitations, applications, related work, TL;DR (3-5 bullets).
        Keep concise (<=1500 words).
        """

        messages = [
            {"role": "system", "content": _sys_prompt(self.language)},
            {"role": "user", "content": user_prompt},
        ]

        final = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.4,
        )
        return final.choices[0].message.content.strip()



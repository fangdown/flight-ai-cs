from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


FAQ_PATH = Path(__file__).resolve().parent / "faq.txt"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_faq(path: Path = FAQ_PATH) -> str:
    """读取 FAQ 文本。"""

    return path.read_text(encoding="utf-8")


def split_faq(text: str) -> list[dict[str, str]]:
    """按 FAQ 标题切分文档。"""

    docs: list[dict[str, str]] = []
    parts = text.split("\n## ")
    for index, part in enumerate(parts):
        content = part.strip()
        if not content:
            continue
        if index > 0:
            content = "## " + content
        title = content.splitlines()[0].replace("#", "").strip()
        docs.append({"title": title, "content": content})
    return docs


class FAQVectorStore:
    """本地 FAISS FAQ 向量库。"""

    def __init__(self) -> None:
        """加载模型并构建索引。"""

        self.model = SentenceTransformer(MODEL_NAME)
        self.docs = split_faq(load_faq())
        embeddings = self.model.encode(
            [doc["content"] for doc in self.docs],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        self.embeddings = embeddings.astype("float32")
        self.index = faiss.IndexFlatIP(self.embeddings.shape[1])
        self.index.add(self.embeddings)

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """检索最相关 FAQ。"""

        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype("float32")
        scores, indices = self.index.search(query_embedding, top_k)
        vector_scores: dict[int, float] = {}
        for score, idx in zip(scores[0], indices[0], strict=False):
            if idx < 0:
                continue
            vector_scores[int(idx)] = float(score)

        ranked: list[tuple[float, int]] = []
        for idx, doc in enumerate(self.docs):
            keyword_score = self._keyword_score(query, doc)
            vector_score = vector_scores.get(idx, 0.0)
            if vector_score > 0 or keyword_score > 0:
                ranked.append((vector_score + keyword_score, idx))

        results: list[dict[str, Any]] = []
        for score, idx in sorted(ranked, reverse=True)[:top_k]:
            doc = self.docs[int(idx)]
            results.append(
                {
                    "title": doc["title"],
                    "content": doc["content"],
                    "score": float(score),
                }
            )
        return results

    def _keyword_score(self, query: str, doc: dict[str, str]) -> float:
        """计算中文短查询关键词加权分。"""

        terms = [
            "退票",
            "变更",
            "改签",
            "订单",
            "证件",
            "姓名",
            "航班",
            "票价",
            "疾病",
            "婴儿",
            "重复购票",
            "免费",
            "规则",
        ]
        score = 0.0
        title = doc["title"]
        content = doc["content"]
        for term in terms:
            if term not in query:
                continue
            if term in title:
                score += 0.6
            score += min(content.count(term), 4) * 0.18
        return score


_store: FAQVectorStore | None = None


def get_vector_store() -> FAQVectorStore:
    """获取单例向量库。"""

    global _store
    if _store is None:
        _store = FAQVectorStore()
    return _store

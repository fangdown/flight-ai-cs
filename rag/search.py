from typing import Any

from rag.embed import get_vector_store


def search_faq(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """查询 FAQ 知识库。"""

    return get_vector_store().search(query=query, top_k=top_k)

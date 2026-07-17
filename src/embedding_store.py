"""ChromaDB 기반 도서 검색 엔진 (batch add 우회)"""

import os
import re
import shutil
from typing import Optional

import pandas as pd
from chromadb import PersistentClient

CHROMA_DIR = os.path.join("data", "chromadb")
COLLECTION_NAME = "yes24_books"
BATCH_SIZE = 100


class EmbeddingStore:
    def __init__(self):
        self._client: Optional[PersistentClient] = None

    def _get_client(self) -> PersistentClient:
        if self._client is None:
            os.makedirs(CHROMA_DIR, exist_ok=True)
            self._client = PersistentClient(path=CHROMA_DIR)
        return self._client

    def _build_document(self, row: pd.Series) -> str:
        parts = []
        if pd.notna(row.get("Title")):
            parts.append(f"제목: {row['Title']}")
        if pd.notna(row.get("Author")):
            parts.append(f"저자: {row['Author']}")
        if pd.notna(row.get("Publisher")):
            parts.append(f"출판사: {row['Publisher']}")
        desc = row.get("Description", "")
        if pd.notna(desc) and desc != "등록된 책 소개 정보가 없습니다.":
            desc = re.sub(r"\s+", " ", desc).strip()[:400]
            parts.append(f"소개: {desc}")
        return "\n".join(parts)

    def build_index(self, df: pd.DataFrame) -> int:
        # 완전히 새 디렉토리로 초기화
        if os.path.exists(CHROMA_DIR):
            shutil.rmtree(CHROMA_DIR)
        os.makedirs(CHROMA_DIR, exist_ok=True)
        self._client = None
        client = self._get_client()

        # ChromaDB 1.x에서 create_collection이 내부적으로 빈 where 필터로
        # delete를 시도하여 ValueError가 발생하는 문제를 우회한다.
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        ids, documents, metadatas = [], [], []
        for idx, row in df.iterrows():
            doc = self._build_document(row)
            if not doc.strip():
                continue
            ids.append(str(idx))
            documents.append(doc)
            metadatas.append({
                "rank": int(row.get("Rank", 0)),
                "title": str(row.get("Title", "")),
                "author": str(row.get("Author", "")),
                "publisher": str(row.get("Publisher", "")),
                "sale_price": int(row.get("Sale Price", 0)),
                "rating": round(float(row.get("Rating", 0)), 2),
                "detail_link": str(row.get("Detail Link", "")),
            })

        # batch add: BATCH_SIZE씩 나눠서 추가
        total = 0
        for i in range(0, len(ids), BATCH_SIZE):
            batch_end = i + BATCH_SIZE
            collection.add(
                ids=ids[i:batch_end],
                documents=documents[i:batch_end],
                metadatas=metadatas[i:batch_end],
            )
            total += len(ids[i:batch_end])
        return total

    def search(self, query: str, top_k: int = 5):
        client = self._get_client()
        try:
            collection = client.get_collection(COLLECTION_NAME)
        except Exception:
            return []

        count = collection.count()
        if count == 0:
            return []

        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, count),
        )
        if not results["ids"] or not results["ids"][0]:
            return []

        output = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            doc = results["documents"][0][i] if results.get("documents") else ""
            dist = results["distances"][0][i] if results.get("distances") else 0.0
            output.append({
                "title": meta.get("title", ""),
                "author": meta.get("author", ""),
                "publisher": meta.get("publisher", ""),
                "sale_price": meta.get("sale_price", 0),
                "rating": meta.get("rating", 0),
                "detail_link": meta.get("detail_link", ""),
                "document": doc,
                "distance": float(dist),
            })
        return output

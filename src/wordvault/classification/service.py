from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from dataclasses import dataclass

from wordvault.storage.database import LibraryDatabase


@dataclass(frozen=True)
class Recommendation:
    category_id: str
    confidence: str
    score: float
    reasons: tuple[str, ...]


class ClassificationService:
    MAX_DEPTH = 3

    def __init__(self, database: LibraryDatabase) -> None:
        self.database = database

    def create_category(
        self,
        name: str,
        *,
        parent_id: str | None = None,
        description: str = "",
        keywords: tuple[str, ...] = (),
    ) -> str:
        name = name.strip()
        if not name:
            raise ValueError("分类名称不能为空")
        if parent_id is not None and self._depth(parent_id) >= self.MAX_DEPTH:
            raise ValueError("最多支持三级分类")
        category_id = str(uuid.uuid4())
        with self.database.connection:
            self.database.connection.execute(
                """
                INSERT INTO categories(id, name, parent_id, description, keywords_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (category_id, name, parent_id, description.strip(), json.dumps(keywords)),
            )
        return category_id

    def assign(
        self, document_id: str, category_id: str | None, *, needs_review: bool = False
    ) -> None:
        if category_id is not None:
            exists = self.database.connection.execute(
                "SELECT 1 FROM categories WHERE id = ?", (category_id,)
            ).fetchone()
            if exists is None:
                raise ValueError("分类不存在")
        with self.database.connection:
            cursor = self.database.connection.execute(
                "UPDATE documents SET category_id = ?, needs_review = ? WHERE id = ?",
                (category_id, int(needs_review), document_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("文档不存在")

    def update_category(
        self,
        category_id: str,
        *,
        name: str,
        description: str = "",
        keywords: tuple[str, ...] = (),
    ) -> None:
        name = name.strip()
        if not name:
            raise ValueError("分类名称不能为空")
        with self.database.connection:
            cursor = self.database.connection.execute(
                """
                UPDATE categories SET name = ?, description = ?, keywords_json = ?
                WHERE id = ?
                """,
                (name, description.strip(), json.dumps(keywords), category_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("分类不存在")

    def delete_category(
        self,
        category_id: str,
        *,
        migrate_to: str | None = None,
        move_to_uncategorized: bool = False,
    ) -> None:
        child = self.database.connection.execute(
            "SELECT 1 FROM categories WHERE parent_id = ? LIMIT 1", (category_id,)
        ).fetchone()
        if child is not None:
            raise ValueError("分类包含子分类，必须先迁移或删除子分类")
        count = self.database.connection.execute(
            "SELECT count(*) FROM documents WHERE category_id = ?", (category_id,)
        ).fetchone()[0]
        if count and migrate_to is None and not move_to_uncategorized:
            raise ValueError("分类仍包含文档，请选择目标分类或未分类")
        if migrate_to == category_id:
            raise ValueError("目标分类不能是原分类")
        with self.database.connection:
            if count:
                self.database.connection.execute(
                    "UPDATE documents SET category_id = ?, needs_review = 0 WHERE category_id = ?",
                    (migrate_to, category_id),
                )
            self.database.connection.execute("DELETE FROM categories WHERE id = ?", (category_id,))

    def recommend(self, document_id: str) -> Recommendation | None:
        document = self.database.connection.execute(
            "SELECT original_name, content_text FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if document is None:
            raise ValueError("文档不存在")
        content = f"{document[0]}\n{document[1] or ''}".casefold()
        candidates: list[Recommendation] = []
        categories = self.database.connection.execute(
            "SELECT id, description, keywords_json FROM categories"
        ).fetchall()
        for category_id, description, keywords_json in categories:
            keywords = tuple(json.loads(keywords_json))
            matches = tuple(keyword for keyword in keywords if keyword.casefold() in content)
            score = float(len(matches)) + self._sample_score(category_id, content)
            if description and description.casefold() in content:
                score += 1
            if score > 0:
                confidence = "high" if score >= 3 else "medium" if score >= 2 else "low"
                candidates.append(Recommendation(category_id, confidence, score, matches))
        return max(candidates, key=lambda item: item.score, default=None)

    def accept_recommendation(
        self, document_id: str, recommendation: Recommendation | None, *, automatic: bool
    ) -> None:
        if recommendation is None:
            raise ValueError("当前文档没有可接受的分类建议")
        self.assign(document_id, recommendation.category_id, needs_review=automatic)

    def _depth(self, category_id: str) -> int:
        depth = 1
        current = category_id
        visited = set()
        while current is not None:
            if current in visited:
                raise ValueError("分类层级存在循环")
            visited.add(current)
            row = self.database.connection.execute(
                "SELECT parent_id FROM categories WHERE id = ?", (current,)
            ).fetchone()
            if row is None:
                raise ValueError("上级分类不存在")
            current = row[0]
            if current is not None:
                depth += 1
        return depth

    def _sample_score(self, category_id: str, content: str) -> float:
        rows = self.database.connection.execute(
            """
            SELECT content_text FROM documents
            WHERE category_id = ? AND content_text IS NOT NULL AND status = 'active'
            LIMIT 20
            """,
            (category_id,),
        ).fetchall()
        if not rows:
            return 0.0
        sample_terms = Counter(
            term for row in rows for term in self._terms(row[0]) if len(term) >= 2
        ).most_common(20)
        content_terms = self._terms(content)
        overlap = sum(1 for term, _ in sample_terms if term in content_terms)
        return min(overlap * 0.25, 2.0)

    @staticmethod
    def _terms(text: str) -> set[str]:
        normalized = text.casefold()
        words = set(re.findall(r"[a-z0-9]{2,}", normalized))
        chinese_runs = re.findall(r"[\u4e00-\u9fff]+", normalized)
        bigrams = {
            run[index : index + 2]
            for run in chinese_runs
            for index in range(max(0, len(run) - 1))
        }
        return words | bigrams

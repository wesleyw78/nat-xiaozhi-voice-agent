"""Structured Q&A knowledge-base helpers for line-matter documents."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any


FIELD_LABELS = ("主管部门", "申办条件", "申请材料", "办理程序", "收费标准")
CONTENT_FIELDS = ("申办条件", "申请材料", "办理程序", "收费标准")


@dataclass(frozen=True)
class KnowledgeItem:
    id: str
    source_file: str
    line_name: str
    title: str
    department: str
    fields: dict[str, str]
    aliases: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeItem":
        return cls(
            id=str(data["id"]),
            source_file=str(data["source_file"]),
            line_name=str(data["line_name"]),
            title=str(data["title"]),
            department=str(data.get("department", "")),
            fields=dict(data.get("fields", {})),
            aliases=list(data.get("aliases", [])),
        )


@dataclass(frozen=True)
class QaEntry:
    id: str
    item_id: str
    source_file: str
    line_name: str
    title: str
    field: str
    question: str
    answer: str
    aliases: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QaEntry":
        return cls(
            id=str(data["id"]),
            item_id=str(data["item_id"]),
            source_file=str(data["source_file"]),
            line_name=str(data["line_name"]),
            title=str(data["title"]),
            field=str(data["field"]),
            question=str(data["question"]),
            answer=str(data["answer"]),
            aliases=list(data.get("aliases", [])),
        )


@dataclass(frozen=True)
class QaSearchResult:
    entry: QaEntry
    score: float


def parse_items_from_blocks(blocks: list[str], source_file: str, line_name: str) -> list[KnowledgeItem]:
    """Parse standardized service items from extracted DOCX text blocks."""
    positions = _supervisor_positions(blocks)
    items: list[KnowledgeItem] = []
    for idx, (title_start, title, _) in enumerate(positions):
        next_start = positions[idx + 1][0] if idx + 1 < len(positions) else len(blocks)
        next_title = positions[idx + 1][1] if idx + 1 < len(positions) else ""
        section = blocks[title_start:next_start]
        fields = _parse_fields(title, section, next_title=next_title)
        department = fields.pop("主管部门", "")
        item = KnowledgeItem(
            id=_item_id(line_name, title, len(items) + 1),
            source_file=source_file,
            line_name=line_name,
            title=title,
            department=department,
            fields=fields,
            aliases=_aliases_for_title(title),
        )
        items.append(item)
    return items


def build_qa_entries(items: list[KnowledgeItem]) -> list[QaEntry]:
    """Generate deterministic Q&A entries from structured service items."""
    entries: list[QaEntry] = []
    for item in items:
        add_entry(entries, item, "概览", f"{item.title}是什么？", _overview_answer(item))
        if item.department:
            add_entry(entries, item, "主管部门", f"{item.title}主管部门是谁？", item.department)
            add_entry(entries, item, "主管部门", f"{item.title}归哪个部门管？", item.department)

        for field in CONTENT_FIELDS:
            value = item.fields.get(field, "")
            if not value:
                continue
            for question in _questions_for_field(item.title, field):
                add_entry(entries, item, field, question, value)
    return entries


def add_entry(entries: list[QaEntry], item: KnowledgeItem, field: str, question: str, answer: str) -> None:
    answer = _clean(answer)
    if not answer:
        return
    entry_id = f"{item.id}_qa_{len(entries) + 1:04d}"
    entries.append(
        QaEntry(
            id=entry_id,
            item_id=item.id,
            source_file=item.source_file,
            line_name=item.line_name,
            title=item.title,
            field=field,
            question=question,
            answer=answer,
            aliases=item.aliases,
        )
    )


def search_qa_entries(query: str, entries: list[QaEntry], top_k: int = 3) -> list[QaSearchResult]:
    query_text = _clean(query)
    if not query_text:
        return []
    terms = _query_terms(query_text)
    scored: list[QaSearchResult] = []
    for entry in entries:
        text = _clean(
            " ".join(
                [
                    entry.question,
                    entry.title,
                    entry.field,
                    entry.line_name,
                    entry.source_file,
                    " ".join(entry.aliases),
                    entry.answer[:240],
                ]
            )
        )
        score = _score(query_text, terms, text)
        score += _intent_bonus(query_text, entry.field)
        score += _title_intent_bonus(query_text, entry.title)
        if score > 0:
            scored.append(QaSearchResult(entry=entry, score=score))
    scored.sort(key=lambda item: item.score, reverse=True)
    deduped: list[QaSearchResult] = []
    seen: set[tuple[str, str]] = set()
    for result in scored:
        key = (result.entry.item_id, result.entry.field)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
        if len(deduped) >= max(1, top_k):
            break
    return deduped


def format_qa_results(results: list[QaSearchResult]) -> str:
    if not results:
        return "本地問答知識庫沒有匹配信息。"
    lines: list[str] = []
    for idx, result in enumerate(results, start=1):
        entry = result.entry
        lines.append(
            f"{idx}. 來源：{entry.source_file}；事項：{entry.title}；欄位：{entry.field}；答案：{entry.answer}"
        )
    return "\n".join(lines)


def summarize_qa_results_for_log(results: list[QaSearchResult], max_answer_chars: int = 180) -> str:
    if not results:
        return "no matches"
    parts: list[str] = []
    for idx, result in enumerate(results, start=1):
        entry = result.entry
        answer = entry.answer.replace("\n", " ")
        if len(answer) > max_answer_chars:
            answer = answer[:max_answer_chars].rstrip() + "..."
        parts.append(
            f"{idx}. score={result.score:.2f} source={entry.source_file} "
            f"title={entry.title} field={entry.field} answer={answer}"
        )
    return " | ".join(parts)


def write_jsonl(path: Path | str, rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_items(path: Path | str) -> list[KnowledgeItem]:
    return [KnowledgeItem.from_dict(row) for row in read_jsonl(path)]


def load_qa_entries(path: Path | str) -> list[QaEntry]:
    return [QaEntry.from_dict(row) for row in read_jsonl(path)]


def read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    path = Path(path)
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def infer_line_name(source_file: str) -> str:
    name = Path(source_file).stem
    return name.replace("条线", "")


def _supervisor_positions(blocks: list[str]) -> list[tuple[int, str, int]]:
    positions: list[tuple[int, str, int]] = []
    label = "主管部门"
    for idx, block in enumerate(blocks):
        block = _clean(block)
        if block == label and idx > 0:
            positions.append((idx - 1, _clean(blocks[idx - 1]), idx))
        elif block.endswith(label) and len(block) > len(label):
            positions.append((idx, _clean(block[: -len(label)]), idx))
    return [(start, title, header) for start, title, header in positions if title]


def _parse_fields(title: str, section: list[str], next_title: str = "") -> dict[str, str]:
    fields: dict[str, list[str]] = {label: [] for label in FIELD_LABELS}
    current_field = ""
    for idx, raw_block in enumerate(section):
        block = _clean(raw_block)
        if not block or block == title or (next_title and block == next_title):
            continue
        if current_field and _is_next_item_title(section, idx):
            continue
        matched = _match_field_header(title, block)
        if matched:
            current_field = matched
            remainder = _field_remainder(title, block, matched)
            if remainder:
                fields[current_field].append(remainder)
            continue
        if current_field:
            fields[current_field].append(block)

    return {
        label: "\n".join(value for value in values if value).strip()
        for label, values in fields.items()
        if any(values)
    }


def _match_field_header(title: str, block: str) -> str:
    for label in FIELD_LABELS:
        if block == label:
            return label
        if block == f"{title}{label}":
            return label
        if block.startswith(f"{title}{label}"):
            return label
        if block.startswith(f"{label}：") or block.startswith(f"{label}:"):
            return label
    return ""


def _is_next_item_title(section: list[str], idx: int) -> bool:
    block = _clean(section[idx])
    if idx + 1 >= len(section) or not block:
        return False
    next_block = _clean(section[idx + 1])
    return next_block == f"{block}主管部门" or next_block == "主管部门"


def _field_remainder(title: str, block: str, label: str) -> str:
    prefixes = (f"{title}{label}", f"{label}：", f"{label}:")
    for prefix in prefixes:
        if block.startswith(prefix):
            return _clean(block[len(prefix):])
    return ""


def _questions_for_field(title: str, field: str) -> list[str]:
    if field == "申办条件":
        return [
            f"{title}申办条件是什么？",
            f"{title}需要满足什么条件？",
            f"{title}什么人可以办理？",
        ]
    if field == "申请材料":
        return [
            f"{title}需要什么材料？",
            f"{title}申请材料有哪些？",
            f"{title}要带什么？",
        ]
    if field == "办理程序":
        return [
            f"{title}怎么办理？",
            f"{title}办理流程是什么？",
            f"{title}在哪里办理？",
        ]
    if field == "收费标准":
        return [
            f"{title}收费吗？",
            f"{title}收费标准是什么？",
            f"{title}要多少钱？",
        ]
    return [f"{title}{field}是什么？"]


def _overview_answer(item: KnowledgeItem) -> str:
    parts = [f"{item.title}是{item.line_name}条线事项。"]
    if item.department:
        parts.append(f"主管部门：{item.department}。")
    available = "、".join(field for field in CONTENT_FIELDS if item.fields.get(field))
    if available:
        parts.append(f"本地知识库包含：{available}。")
    return "".join(parts)


def _aliases_for_title(title: str) -> list[str]:
    aliases = {title}
    compact = re.sub(r"[《》（）()，,、/]", "", title)
    if compact and compact != title:
        aliases.add(compact)
    if "居住证" in title:
        aliases.update(["办居住证", "居住证办理", "居住证"])
    if "社会保障卡" in title or "社保卡" in title:
        aliases.update(["社保卡", "社会保障卡", "医保卡"])
    if "灵活就业" in title:
        aliases.update(["灵活就业", "自由职业缴费"])
    if "退休住院" in title:
        aliases.update(["退休住院计划", "退休住院"])
    if "婚姻登记档案" in title:
        aliases.update(["婚姻档案", "婚姻登记档案"])
    return sorted(aliases)


def _item_id(line_name: str, title: str, index: int) -> str:
    token = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", f"{line_name}_{title}").strip("_")
    return f"{token}_{index:03d}"


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _query_terms(query: str) -> list[str]:
    raw_terms = re.findall(r"[\w\u4e00-\u9fff]+", query)
    terms: set[str] = {term for term in raw_terms if len(term) >= 2}
    compact = "".join(raw_terms)
    for size in (2, 3, 4):
        for idx in range(0, max(0, len(compact) - size + 1)):
            terms.add(compact[idx : idx + size])
    return sorted(terms, key=len, reverse=True)


def _score(query: str, terms: list[str], text: str) -> float:
    score = 0.0
    for term in terms:
        hits = text.count(term)
        if hits:
            score += hits * (len(term) ** 1.4)
    for token in re.findall(r"[\w\u4e00-\u9fff]+", query):
        if len(token) >= 2 and token in text:
            score += len(token) * 3
    return score


def _intent_bonus(query: str, field: str) -> float:
    intents = {
        "申请材料": ("材料", "带什么", "要带", "资料", "证件"),
        "申办条件": ("条件", "资格", "什么人", "能不能"),
        "办理程序": ("流程", "程序", "怎么办", "办理", "哪里", "地址"),
        "收费标准": ("收费", "费用", "多少钱", "免费", "价格"),
        "主管部门": ("部门", "谁管", "归谁"),
    }
    return 80.0 if any(term in query for term in intents.get(field, ())) else 0.0


def _title_intent_bonus(query: str, title: str) -> float:
    if any(term in query for term in ("签注", "變更", "变更", "挂失", "解挂", "补卡", "補卡")):
        return 0.0
    if any(term in query for term in ("办居住证", "办理居住证", "居住证办理")) and "居住证新办" in title:
        return 140.0
    if any(term in query for term in ("办社保卡", "办理社保卡", "社保卡新办")) and "社保卡申领" in title:
        return 120.0
    return 0.0

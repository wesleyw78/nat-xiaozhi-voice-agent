"""Local DOCX knowledge-base loading and search helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import re
import xml.etree.ElementTree as ET

WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
DEFAULT_KNOWLEDGE_DIR = Path("knowledge/line-matters-docx")
DEFAULT_MAX_CHARS = 900

LINE_MATTER_TERMS = (
    "残联",
    "殘聯",
    "档案",
    "檔案",
    "公安",
    "经信",
    "經信",
    "民政",
    "人社",
    "税务",
    "稅務",
    "卫健",
    "衛健",
    "医保",
    "醫保",
    "住建",
    "总工会",
    "總工會",
    "居住证",
    "居住證",
    "失业登记",
    "失業登記",
    "社会保障卡",
    "社會保障卡",
    "灵活就业",
    "靈活就業",
    "扣款协议",
    "扣款協議",
    "退休住院计划",
    "退休住院計畫",
    "婚姻登记档案",
    "婚姻登記檔案",
    "住房租赁",
    "住房租賃",
    "计划生育",
    "計劃生育",
    "盲人公共交通证",
    "盲人公共交通證",
)

SERVICE_QUERY_TERMS = (
    "办理",
    "辦理",
    "申请",
    "申請",
    "申办",
    "申辦",
    "查询",
    "查詢",
    "材料",
    "条件",
    "條件",
    "流程",
    "程序",
    "受理",
    "事项",
    "事項",
    "主管部门",
    "主管部門",
    "哪里办",
    "哪裡辦",
    "怎么办",
    "怎麼辦",
)


@dataclass(frozen=True)
class KnowledgeChunk:
    source: str
    title: str
    text: str


@dataclass(frozen=True)
class SearchResult:
    source: str
    title: str
    snippet: str
    score: float


def extract_docx_blocks(path: Path | str) -> list[str]:
    """Extract paragraph and table-row text blocks from a DOCX file."""
    path = Path(path)
    with ZipFile(path) as docx:
        document_xml = docx.read("word/document.xml")

    root = ET.fromstring(document_xml)
    blocks: list[str] = []
    body = root.find(".//w:body", WORD_NS)
    if body is None:
        return blocks

    for child in list(body):
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = _node_text(child)
            if text:
                blocks.append(text)
        elif tag == "tbl":
            for row in child.findall(".//w:tr", WORD_NS):
                cells = [_node_text(cell) for cell in row.findall("./w:tc", WORD_NS)]
                row_text = " | ".join(cell for cell in cells if cell)
                if row_text:
                    blocks.append(row_text)
    return blocks


def build_chunks(source_name: str, blocks: list[str], max_chars: int = DEFAULT_MAX_CHARS) -> list[KnowledgeChunk]:
    """Group extracted blocks into bounded chunks while preserving the document title."""
    normalized = [_clean_text(block) for block in blocks if _clean_text(block)]
    if not normalized:
        return []

    title = normalized[0]
    chunks: list[KnowledgeChunk] = []
    current: list[str] = []
    current_len = 0

    for block in normalized:
        block_len = len(block)
        separator_len = 1 if current else 0
        if current and current_len + separator_len + block_len > max_chars:
            chunks.append(KnowledgeChunk(source=source_name, title=title, text="\n".join(current)))
            current = []
            current_len = 0
        current.append(block)
        current_len += block_len + (1 if len(current) > 1 else 0)

    if current:
        chunks.append(KnowledgeChunk(source=source_name, title=title, text="\n".join(current)))
    return chunks


def load_docx_chunks(knowledge_dir: Path | str = DEFAULT_KNOWLEDGE_DIR, max_chars: int = DEFAULT_MAX_CHARS) -> list[KnowledgeChunk]:
    """Load all DOCX files in a directory into searchable chunks."""
    root = Path(knowledge_dir)
    chunks: list[KnowledgeChunk] = []
    for path in sorted(root.glob("*.docx")):
        if path.name.startswith("~$"):
            continue
        try:
            blocks = extract_docx_blocks(path)
        except (BadZipFile, KeyError, ET.ParseError):
            continue
        chunks.extend(build_chunks(path.name, blocks, max_chars=max_chars))
    return chunks


def search_chunks(query: str, chunks: list[KnowledgeChunk], top_k: int = 3) -> list[SearchResult]:
    """Search chunks with deterministic local scoring."""
    query_text = _clean_text(query)
    if not query_text:
        return []

    terms = _query_terms(query_text)
    scored: list[SearchResult] = []
    for chunk in chunks:
        searchable = _clean_text(f"{chunk.source} {chunk.title} {chunk.text}")
        score = _score(query_text, terms, searchable)
        if score <= 0:
            continue
        scored.append(
            SearchResult(
                source=chunk.source,
                title=chunk.title,
                snippet=_snippet(chunk.text, terms),
                score=score,
            )
        )

    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[: max(1, top_k)]


def format_results(results: list[SearchResult]) -> str:
    """Format search results for a voice-agent tool response."""
    if not results:
        return "未在本地條線知識庫找到相關內容。"

    lines: list[str] = []
    for idx, item in enumerate(results, start=1):
        lines.append(
            f"{idx}. 來源：{item.source}；標題：{item.title}；內容：{item.snippet}"
        )
    return "\n".join(lines)


def should_search_line_matter_knowledge(query: str) -> bool:
    """Return True when a user query should consult the bundled knowledge base."""
    text = _clean_text(query)
    return bool(text)


def _node_text(node: ET.Element) -> str:
    return _clean_text("".join(text.text or "" for text in node.findall(".//w:t", WORD_NS)))


def _clean_text(text: str) -> str:
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


def _snippet(text: str, terms: list[str], max_chars: int = 220) -> str:
    cleaned = _clean_text(text)
    if len(cleaned) <= max_chars:
        return cleaned

    first_hit = -1
    for term in terms:
        pos = cleaned.find(term)
        if pos >= 0 and (first_hit < 0 or pos < first_hit):
            first_hit = pos

    if first_hit < 0:
        return cleaned[:max_chars].rstrip() + "..."

    start = max(0, first_hit - max_chars // 3)
    end = min(len(cleaned), start + max_chars)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(cleaned) else ""
    return prefix + cleaned[start:end].rstrip() + suffix

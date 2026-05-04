"""Register the local line-matter DOCX knowledge-base tool with NAT."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

from nat_xiaozhi_voice.tools.knowledge_base import (
    DEFAULT_KNOWLEDGE_DIR,
    build_chunks,
    extract_docx_blocks,
    format_results,
    search_chunks,
)

logger = logging.getLogger(__name__)


class LineMatterKnowledgeConfig(FunctionBaseConfig, name="line_matter_knowledge"):
    """Config for the local line-matter DOCX knowledge tool."""

    knowledge_dir: str = Field(default=str(DEFAULT_KNOWLEDGE_DIR))
    top_k: int = Field(default=3)
    max_chars: int = Field(default=900)


@register_function(config_type=LineMatterKnowledgeConfig)
async def line_matter_knowledge_tool(config: LineMatterKnowledgeConfig, builder: Builder):
    knowledge_dir = Path(config.knowledge_dir)
    chunks = []
    for path in sorted(knowledge_dir.glob("*.docx")):
        blocks = extract_docx_blocks(path)
        chunks.extend(build_chunks(path.name, blocks, max_chars=config.max_chars))

    logger.info(
        "line_matter_knowledge registered (dir=%s, docs=%d, chunks=%d)",
        knowledge_dir,
        len(list(knowledge_dir.glob("*.docx"))),
        len(chunks),
    )

    async def line_matter_knowledge(query: str = "") -> str:
        """Search local government line-matter DOCX documents.

        Use for questions about the bundled line-matter service documents,
        including disability federation, archives, public security, economy
        and informatization, civil affairs, human resources and social
        security, tax, health, medical insurance, housing construction, and
        trade union matters.
        """
        if not query or not query.strip():
            return "請提供要查詢的條線事項問題。"
        results = search_chunks(query, chunks, top_k=config.top_k)
        return format_results(results)

    yield FunctionInfo.from_fn(
        line_matter_knowledge,
        description=(
            "Search the local DOCX knowledge base for Shanghai line-matter "
            "government service information. Use for questions about 殘聯, "
            "檔案, 公安, 經信, 民政, 人社, 稅務, 衛健, 醫保, 住建, or 總工會 matters."
        ),
    )

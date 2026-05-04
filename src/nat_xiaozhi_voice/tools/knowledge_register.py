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
    format_results,
    load_docx_chunks,
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
    chunks = load_docx_chunks(knowledge_dir, max_chars=config.max_chars)
    doc_count = len([path for path in knowledge_dir.glob("*.docx") if not path.name.startswith("~$")])

    logger.info(
        "line_matter_knowledge registered (dir=%s, docs=%d, chunks=%d)",
        knowledge_dir,
        doc_count,
        len(chunks),
    )

    async def line_matter_knowledge(query: str = "") -> str:
        """Search local government service DOCX knowledge base.

        Use this tool for bundled government service documents, including:
        残联/殘聯, 档案/檔案, 公安, 经信/經信, 民政, 人社, 税务/稅務,
        卫健/衛健, 医保/醫保, 住建, 总工会/總工會. Also use it for
        service questions such as 居住证/居住證, 社会保障卡/社會保障卡,
        灵活就业/靈活就業, 退休住院计划/退休住院計畫, 婚姻登记档案,
        材料, 条件, 流程, 主管部门, 办理, 申请, 查询.
        """
        if not query or not query.strip():
            return "請提供要查詢的條線事項問題。"
        results = search_chunks(query, chunks, top_k=config.top_k)
        return format_results(results)

    yield FunctionInfo.from_fn(
        line_matter_knowledge,
        description=(
            "Search the local DOCX knowledge base for government service matters. "
            "MUST use for questions about 残联/殘聯, 档案/檔案, 公安, 经信/經信, "
            "民政, 人社, 税务/稅務, 卫健/衛健, 医保/醫保, 住建, 总工会/總工會, "
            "or service items like 居住证, 社会保障卡, 灵活就业, 退休住院计划, "
            "婚姻登记档案, 材料, 条件, 流程, 主管部门, 办理, 申请, 查询."
        ),
    )

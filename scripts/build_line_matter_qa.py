"""Build structured Q&A knowledge files from bundled line-matter DOCX files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nat_xiaozhi_voice.tools.knowledge_base import extract_docx_blocks
from nat_xiaozhi_voice.tools.knowledge_qa import (
    build_qa_entries,
    infer_line_name,
    parse_items_from_blocks,
    write_jsonl,
)


def build(source_dir: Path, output_dir: Path) -> dict:
    items = []
    doc_report = []
    for path in sorted(source_dir.glob("*.docx")):
        if path.name.startswith("~$"):
            continue
        blocks = extract_docx_blocks(path)
        doc_items = parse_items_from_blocks(
            blocks,
            source_file=path.name,
            line_name=infer_line_name(path.name),
        )
        items.extend(doc_items)
        doc_report.append(
            {
                "source_file": path.name,
                "line_name": infer_line_name(path.name),
                "blocks": len(blocks),
                "items": len(doc_items),
            }
        )

    qa_entries = build_qa_entries(items)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "items.jsonl", [item.to_dict() for item in items])
    write_jsonl(output_dir / "qa.jsonl", [entry.to_dict() for entry in qa_entries])

    report = {
        "source_dir": str(source_dir),
        "output_dir": str(output_dir),
        "doc_count": len(doc_report),
        "item_count": len(items),
        "qa_count": len(qa_entries),
        "documents": doc_report,
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", default="knowledge/line-matters-docx")
    parser.add_argument("--output-dir", default="knowledge/line-matters-qa")
    args = parser.parse_args()

    report = build(Path(args.source_dir), Path(args.output_dir))
    print(
        f"Built Q&A knowledge base: docs={report['doc_count']} "
        f"items={report['item_count']} qa={report['qa_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

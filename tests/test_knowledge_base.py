import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from nat_xiaozhi_voice.tools.knowledge_base import (
    build_chunks,
    extract_docx_blocks,
    search_chunks,
)


DOC_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _write_minimal_docx(path: Path, body_xml: str) -> None:
    with ZipFile(path, "w") as docx:
        docx.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
        docx.writestr(
            "word/document.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{DOC_NS}">
  <w:body>{body_xml}</w:body>
</w:document>""",
        )


class KnowledgeBaseTests(unittest.TestCase):
    def test_extract_docx_blocks_reads_paragraphs_and_table_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "测试.docx"
            _write_minimal_docx(
                path,
                """
<w:p><w:r><w:t>居住证新办</w:t></w:r></w:p>
<w:p><w:r><w:t>主管部门</w:t></w:r><w:r><w:t>市公安局</w:t></w:r></w:p>
<w:tbl>
  <w:tr>
    <w:tc><w:p><w:r><w:t>申请条件</w:t></w:r></w:p></w:tc>
    <w:tc><w:p><w:r><w:t>合法稳定居住</w:t></w:r></w:p></w:tc>
  </w:tr>
</w:tbl>
""",
            )

            self.assertEqual(
                extract_docx_blocks(path),
                ["居住证新办", "主管部门市公安局", "申请条件 | 合法稳定居住"],
            )

    def test_build_chunks_keeps_source_and_groups_blocks(self):
        chunks = build_chunks(
            source_name="公安条线.docx",
            blocks=["居住证新办", "主管部门市公安局", "申请条件：合法稳定居住"],
            max_chars=20,
        )

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].source, "公安条线.docx")
        self.assertEqual(chunks[0].title, "居住证新办")
        self.assertIn("主管部门市公安局", chunks[0].text)
        self.assertEqual(chunks[1].title, "居住证新办")

    def test_search_chunks_prioritizes_matching_phrase_and_source(self):
        chunks = build_chunks(
            source_name="公安条线.docx",
            blocks=["居住证新办", "主管部门市公安局", "申请条件：合法稳定居住"],
            max_chars=200,
        ) + build_chunks(
            source_name="医保.docx",
            blocks=["申领社会保障卡", "主管部门市医保局"],
            max_chars=200,
        )

        results = search_chunks("公安 居住证新办 申请条件", chunks, top_k=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "公安条线.docx")
        self.assertIn("申请条件", results[0].snippet)


if __name__ == "__main__":
    unittest.main()

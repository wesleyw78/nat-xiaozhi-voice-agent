import tempfile
import unittest
from pathlib import Path

from nat_xiaozhi_voice.tools.knowledge_qa import (
    build_qa_entries,
    parse_items_from_blocks,
    search_qa_entries,
    summarize_qa_results_for_log,
    write_jsonl,
    load_qa_entries,
)


class KnowledgeQaTests(unittest.TestCase):
    def test_parse_items_from_blocks_extracts_standard_fields(self):
        blocks = [
            "居住证新办",
            "居住证新办主管部门",
            "市公安局",
            "居住证新办申办条件",
            "办理居住登记满半年。",
            "居住证新办申请材料",
            "1、身份证原件",
            "2、居住登记凭证",
            "居住证新办办理程序",
            "到社区事务受理服务中心申请。",
            "居住证新办收费标准",
            "免费",
        ]

        items = parse_items_from_blocks(blocks, source_file="公安条线.docx", line_name="公安")

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.title, "居住证新办")
        self.assertEqual(item.department, "市公安局")
        self.assertIn("满半年", item.fields["申办条件"])
        self.assertIn("身份证原件", item.fields["申请材料"])
        self.assertEqual(item.fields["收费标准"], "免费")

    def test_build_qa_entries_generates_field_questions_and_aliases(self):
        item = parse_items_from_blocks(
            [
                "居住证新办",
                "主管部门",
                "市公安局",
                "居住证新办申请材料",
                "1、身份证原件",
                "居住证新办收费标准",
                "免费",
            ],
            source_file="公安条线.docx",
            line_name="公安",
        )[0]

        qa = build_qa_entries([item])
        questions = [entry.question for entry in qa]

        self.assertIn("居住证新办需要什么材料？", questions)
        self.assertIn("居住证新办收费吗？", questions)
        self.assertTrue(any("办居住证" in alias for alias in item.aliases))

    def test_search_qa_entries_matches_colloquial_material_query(self):
        items = parse_items_from_blocks(
            [
                "居住证新办",
                "居住证新办主管部门",
                "市公安局",
                "居住证新办申请材料",
                "1、身份证原件",
                "2、上海市居住证申请表",
                "居住证签注",
                "居住证签注主管部门",
                "市公安局",
                "居住证签注申请材料",
                "1、本人居住证",
                "居住证信息变更",
                "居住证信息变更主管部门",
                "市公安局",
                "居住证信息变更申请材料",
                "1、本人有效的上海市居住证",
            ],
            source_file="公安条线.docx",
            line_name="公安",
        )
        qa = build_qa_entries(items)

        results = search_qa_entries("办居住证要带什么？", qa, top_k=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].entry.title, "居住证新办")
        self.assertEqual(results[0].entry.field, "申请材料")
        self.assertIn("身份证原件", results[0].entry.answer)

    def test_parse_items_does_not_leak_next_title_into_previous_field(self):
        items = parse_items_from_blocks(
            [
                "灵活就业及城乡居民个人委托扣款协议签订",
                "灵活就业及城乡居民个人委托扣款协议签订主管部门",
                "国家税务总局上海市税务局",
                "灵活就业及城乡居民个人委托扣款协议签订收费标准",
                "免费",
                "城乡居民社会保险费缴纳",
                "城乡居民社会保险费缴纳主管部门",
                "国家税务总局上海市税务局",
            ],
            source_file="税务.docx",
            line_name="税务",
        )

        self.assertEqual(items[0].fields["收费标准"], "免费")

    def test_write_and_load_jsonl_round_trips_qa_entries(self):
        item = parse_items_from_blocks(
            ["市民网上实名认证服务", "市民网上实名认证服务主管部门", "经信委"],
            source_file="经信条线.docx",
            line_name="经信",
        )[0]
        qa = build_qa_entries([item])

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "qa.jsonl"
            write_jsonl(path, [entry.to_dict() for entry in qa])
            loaded = load_qa_entries(path)

        self.assertEqual(len(loaded), len(qa))
        self.assertEqual(loaded[0].source_file, "经信条线.docx")

    def test_summarize_qa_results_for_log_includes_returned_content(self):
        item = parse_items_from_blocks(
            [
                "居住证新办",
                "居住证新办主管部门",
                "市公安局",
                "居住证新办申请材料",
                "1、身份证原件",
            ],
            source_file="公安条线.docx",
            line_name="公安",
        )[0]
        results = search_qa_entries("居住证新办材料", build_qa_entries([item]), top_k=1)

        summary = summarize_qa_results_for_log(results)

        self.assertIn("公安条线.docx", summary)
        self.assertIn("居住证新办", summary)
        self.assertIn("申请材料", summary)
        self.assertIn("身份证原件", summary)


if __name__ == "__main__":
    unittest.main()

import base64
import unittest

from nat_xiaozhi_voice.frontend.web_chat import (
    WebChatValidationError,
    build_error_response,
    build_success_response,
    normalize_chat_text,
)


class WebChatHelperTests(unittest.TestCase):
    def test_normalize_chat_text_rejects_blank_text(self):
        with self.assertRaises(WebChatValidationError) as ctx:
            normalize_chat_text("   \n\t  ")
        self.assertEqual(str(ctx.exception), "text is empty")

    def test_normalize_chat_text_strips_outer_whitespace(self):
        self.assertEqual(normalize_chat_text("  你好  "), "你好")

    def test_build_success_response_encodes_audio(self):
        result = build_success_response(
            device_id="web-client",
            reply="你好",
            audio_bytes=b"abc",
            mime_type="audio/mpeg",
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["device_id"], "web-client")
        self.assertEqual(result["reply"], "你好")
        self.assertEqual(result["audio"]["mime_type"], "audio/mpeg")
        self.assertEqual(base64.b64decode(result["audio"]["data_base64"]), b"abc")

    def test_build_success_response_without_audio_is_partial(self):
        result = build_success_response(
            device_id="web-client",
            reply="你好",
            audio_bytes=None,
            mime_type=None,
            error="TTS failed",
        )
        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["audio"])
        self.assertEqual(result["error"], "TTS failed")

    def test_build_error_response(self):
        self.assertEqual(
            build_error_response("text is empty"),
            {"status": "error", "message": "text is empty"},
        )


if __name__ == "__main__":
    unittest.main()

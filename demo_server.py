"""Local browser demo for the OrbitTech customer-support assistant."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from domain_assistant import DomainAssistant

ROOT = Path(__file__).resolve().parent
_assistant: DomainAssistant | None = None


def get_assistant() -> DomainAssistant:
    global _assistant
    if _assistant is None:
        _assistant = DomainAssistant.from_corpus(ROOT / "data" / "technology_store")
    return _assistant


class DemoHandler(BaseHTTPRequestHandler):
    server_version = "OrbitTechDemo/1.0"

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        route = urlsplit(self.path).path
        if route == "/":
            page = (ROOT / "demo.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(page)
            return
        if route == "/api/health":
            self._send_json(200, {"status": "ready"})
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/answer":
            self._send_json(404, {"error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length < 1 or content_length > 16_384:
                self._send_json(413, {"error": "Nội dung câu hỏi rỗng hoặc vượt quá dung lượng cho phép."})
                return
            payload = json.loads(self.rfile.read(content_length))
            question = payload.get("question", "") if isinstance(payload, dict) else ""
            if not isinstance(question, str) or not question.strip():
                self._send_json(400, {"error": "Vui lòng nhập câu hỏi để tiếp tục."})
                return
            if len(question) > 1_000:
                self._send_json(413, {"error": "Vui lòng giữ câu hỏi dưới 1.000 ký tự."})
                return

            response = get_assistant().answer_with_trace(question.strip())
            sources = [
                {
                    "source_doc": chunk.source_doc,
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "score": chunk.score,
                }
                for chunk in response.retrieved_chunks
            ]
            self._send_json(
                200,
                {
                    "question": response.question,
                    "answer": response.actual_answer,
                    "sources": sources,
                },
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "Dữ liệu yêu cầu phải là định dạng JSON hợp lệ."})
        except Exception:
            self._send_json(
                502,
                {"error": "Trợ lý không thể phản hồi. Vui lòng kiểm tra cấu hình máy chủ cục bộ."},
            )

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Khởi chạy giao diện web demo OrbitTech cục bộ.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    print(f"Giao diện demo OrbitTech đã sẵn sàng tại http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Đang dừng demo OrbitTech.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
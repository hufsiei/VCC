# local_fn.py — Cloud Functions 대신 미리 PC에서 띄우는 개발용 서버 함수
# 실행: PowerShell에서
#   cd C:\dev\VCC\functions
#   $env:CLOVA_KEY = "발급받은_키"          # HCX 작업용
#   $env:ANTHROPIC_API_KEY = "발급받은_키"  # Claude 작업용(요약·일치검사 등을 쓸 때만)
#   python local_fn.py
#
# AI는 반드시 ai.py의 callAI(작업명, ...)로만 부른다. 모델 선택은 ai.py의 PROVIDER 표.
# 지금은 연결 확인용 경로 하나뿐. askBoo 등은 작업 18부터 경로(/askBoo …)로 추가한다.
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from ai import callAI


class Handler(BaseHTTPRequestHandler):
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204); self.cors(); self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        question = json.loads(self.rfile.read(n) or b"{}").get("question", "안녕하세요?")
        r = callAI(
            "연습",
            [{"role": "user", "content": question}],
            system="너는 한국외대 선배 경험을 전하는 도우미다. 두 문장 이내로 답한다.",
        )
        out = {"answer": r["text"], "model": r["model"]} if r["ok"] else {"error": r["error"]}
        b = json.dumps(out, ensure_ascii=False).encode()
        self.send_response(200); self.cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers(); self.wfile.write(b)


if __name__ == "__main__":
    print("개발 서버 함수 실행 중: http://localhost:8787  (끄려면 Ctrl+C)")
    HTTPServer(("localhost", 8787), Handler).serve_forever()

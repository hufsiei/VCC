# local_fn.py — Cloud Functions 대신 내 PC에서 띄우는 연습용 서버 함수
# 실행: PowerShell에서
#   cd C:\dev\연습
#   $env:CLOVA_KEY = "발급받은_키"
#   python local_fn.py
import json, os, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

KEY = os.environ.get("CLOVA_KEY")
if not KEY:
    raise SystemExit("CLOVA_KEY가 없습니다. 먼저  $env:CLOVA_KEY = \"발급받은_키\"  를 실행하세요.")

URL = "https://clovastudio.stream.ntruss.com/v3/chat-completions/HCX-005"  # ← 플레이그라운드 '코드 보기'의 주소로 교체


def ask_clova(question):
    body = json.dumps({
        "messages": [
            {"role": "system", "content": "너는 한국외대 선배 경험을 전하는 도우미다. 두 문장 이내로 답한다."},
            {"role": "user", "content": question}
        ],
        "maxTokens": 256, "temperature": 0.5
    }).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": "Bearer " + KEY,   # ← '코드 보기'의 헤더 형식과 대조
        "Content-Type": "application/json"
    })
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    return data.get("result", {}).get("message", {}).get("content") or json.dumps(data, ensure_ascii=False)


class Handler(BaseHTTPRequestHandler):
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204); self.cors(); self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        question = json.loads(self.rfile.read(n) or b"{}").get("question", "안녕하세요?")
        try:
            out = {"answer": ask_clova(question)}
        except urllib.error.HTTPError as e:
            out = {"error": e.code, "detail": e.read().decode("utf-8", "replace")}
        except Exception as e:
            out = {"error": str(e)}
        b = json.dumps(out, ensure_ascii=False).encode()
        self.send_response(200); self.cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers(); self.wfile.write(b)


print("연습 서버 함수 실행 중: http://localhost:8787  (끄려면 Ctrl+C)")
HTTPServer(("localhost", 8787), Handler).serve_forever()

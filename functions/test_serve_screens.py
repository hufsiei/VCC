# test_serve_screens.py — 로컬 화면 서버가 .env·로그·runtime을 열지 않는지 (serve_screens.py, 11/24)
# 실행: cd functions && python test_serve_screens.py
# 임시 폴더에 가짜 저장소(가짜 .env 포함)를 만들고 빈 포트에 띄워 본다. 실제 .env는 읽지 않는다. AI 호출 없음.
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import serve_screens

fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


tmp = Path(tempfile.mkdtemp())
files = {
    ".env": "FAKE_KEY=not-a-real-key\n",
    ".git/config": "[core]\n",
    "functions/logs/ai-calls.jsonl": "{}\n",
    "functions/ai.py": "# code\n",
    "data/runtime/messages.json": "[]\n",
    "data/programs.json": "[]\n",
    "docs/hub-data.json": "{}\n",
    "tools/x.py": "# tool\n",
    "README.md": "# readme\n",
    "screens/login/index.html": "<p>login</p>\n",
    "common/style.css": "body{}\n",
    "assets/a.png": "png\n",
}
for rel, text in files.items():
    p = tmp / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

serve_screens.Handler.log_message = lambda *a: None   # 시험 출력에 접속 줄을 찍지 않는다
server = serve_screens.make_server(0, tmp)
host, port = server.server_address[:2]
threading.Thread(target=server.serve_forever, daemon=True).start()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


opener = urllib.request.build_opener(NoRedirect)


def get(path):
    try:
        with opener.open(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


expect("127.0.0.1에만 묶임(다른 기기 접속 불가)", host == "127.0.0.1")
expect("HOST 상수도 127.0.0.1", serve_screens.HOST == "127.0.0.1")

ok_paths = ["/screens/login/", "/screens/login/index.html", "/common/style.css", "/assets/a.png",
            "/data/programs.json", "/screens/login/?server=all"]
for path in ok_paths:
    expect(f"열림 200 {path}", get(path)[0] == 200)

blocked = [
    "/.env", "/.ENV", "/%2eenv", "/.env.", "/screens/../.env", "/screens/%2e%2e/.env",
    "/screens/..%5c.env", "/.git/config", "/.git/", "/functions/logs/", "/functions/logs/ai-calls.jsonl",
    "/functions/ai.py", "/data/runtime/", "/data/runtime/messages.json", "/Data/Runtime/messages.json",
    "/data/runtime./messages.json", "/data/runtime%20/messages.json", "/data/RUNTIM~1/messages.json",
    "/data/programs.json::$DATA", "/docs/hub-data.json", "/tools/x.py", "/README.md",
    "/screens/", "/data/",   # 폴더 목록도 안 보임
]
for path in blocked:
    status, body = get(path)
    expect(f"막힘 {status} {path}", status in (403, 404) and b"not-a-real-key" not in body)

status, _ = get("/")
expect("/ → 302 (로그인 화면으로)", status == 302)

server.shutdown()
server.server_close()

if fails:
    print(f"\n틀림 {len(fails)}건")
    sys.exit(1)
print("\n전부 통과")

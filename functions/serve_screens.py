# serve_screens.py — 로컬 화면 서버 (11/24, `python -m http.server 8000` 대신)
# 실행: 저장소 맨 위에서  python functions/serve_screens.py          → http://localhost:8000/screens/login/
#       포트 바꾸기:       python functions/serve_screens.py 8001
#
# 왜: `python -m http.server`는 저장소 전체를 0.0.0.0(같은 와이파이의 다른 기기 포함)으로 연다.
#     그러면 http://<PC주소>:8000/.env 로 키가 보이고 functions/logs·data/runtime도 열린다.
# 그래서 이 서버는
#   1) 127.0.0.1에만 묶는다 — 이 PC 밖에서는 접속되지 않는다(바꾸는 옵션 없음).
#   2) 화면에 필요한 폴더만 연다: screens/ · common/ · assets/ · data/(data/runtime 제외).
#      그 밖(.env · .git · functions/ · docs/ · tools/ · 맨 위 파일)과 점(.)으로 시작하는 이름은 모두 404.
#   / 로 들어오면 /screens/login/ 으로 보낸다. AI를 부르지 않는다.
import posixpath
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1"
PORT = 8000
ALLOWED_TOP = {"screens", "common", "assets", "data"}
BLOCKED = {("data", "runtime")}


def allowed(url_path):
    """URL 경로(쿼리 제외)를 열어도 되면 True. 대소문자·%인코딩·역슬래시·Windows 이름 꼼수도 막는다."""
    path = unquote(url_path).replace("\\", "/")
    parts = []
    for raw in path.split("/"):
        # Windows는 이름 끝의 점·공백을 버린다(data/runtime. == data/runtime), 대소문자를 가리지 않는다
        seg = raw.rstrip(". ").lower()
        if raw in ("", "."):
            continue
        if raw == ".." or not seg:
            return False
        if seg.startswith(".") or ":" in seg or "~" in seg:   # 숨김 파일·ADS(::$DATA)·8.3 짧은 이름
            return False
        parts.append(seg)
    if not parts or parts[0] not in ALLOWED_TOP:
        return False
    return not any(tuple(parts[:len(b)]) == b for b in BLOCKED)


class Handler(SimpleHTTPRequestHandler):
    def send_head(self):
        path = urlsplit(self.path).path
        if path in ("", "/"):
            self.send_response(302)
            self.send_header("Location", "/screens/login/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        if not allowed(path):
            self.send_error(404, "Not Found")
            return None
        return super().send_head()

    def list_directory(self, path):   # 폴더 목록은 보여 주지 않는다
        self.send_error(404, "Not Found")
        return None

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")   # 고친 화면이 바로 보이게
        super().end_headers()


def make_server(port=PORT, root=ROOT):
    return ThreadingHTTPServer((HOST, port), partial(Handler, directory=str(root)))


def main(argv):
    port = int(argv[1]) if len(argv) > 1 else PORT
    server = make_server(port)
    print(f"화면 서버: http://localhost:{port}/screens/login/  (이 PC에서만, 끄기 Ctrl+C)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main(sys.argv)

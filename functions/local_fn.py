# local_fn.py — Cloud Functions 대신 미리 PC에서 띄우는 개발용 서버 함수
# 실행: PowerShell에서
#   cd C:\dev\VCC\functions
#   python local_fn.py
# 키(CLOVA_KEY, ANTHROPIC_API_KEY)는 저장소 맨 위 .env에서 ai.py가 읽는다(이미 있는 환경변수가 먼저).
#
# 주소: POST http://localhost:8787/<함수 이름>   (예: /sendMessage)
#   - 로그인한 사용자는 헤더 X-Token으로 받는다(data.js가 붙여 준다). sessions.resolve()가 colreg_no로 바꾼다(작업 73).
#   - 쓰기 기록(쪽지·질문함·동의·신고)은 runtime_fns.py → store.py → data/runtime/*.json (spec 2-1)
#   - 경로 없이 POST / 는 연결 확인용 AI 연습 호출(그대로 둠)
#
# AI는 반드시 ai.py의 callAI(작업명, ...)로만 부른다. 모델 선택은 ai.py의 PROVIDER 표.
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

import account
import admin
import limits
import sessions
from askboo import askBoo
from interview import interviewNext, summarizeInterview
from runtime_fns import ROUTES

# AI를 쓰는 함수는 runtime_fns(AI 없음)와 따로 둔다. login·getMe는 account.py
ROUTES = {**ROUTES, **account.ROUTES, **admin.ROUTES, "askBoo": askBoo, "interviewNext": interviewNext, "summarizeInterview": summarizeInterview}
NEEDS_NO_LOGIN = {"checkMessage", "login"}
# 사용자별 호출 한도(limits.py, 분당 10·일 100)를 세는 함수. AI를 부르는 함수를 새로 연결하면 여기에 더한다
# (checkMessage의 비방 판정은 작업 27).
AI_ROUTES = {"askBoo", "interviewNext", "summarizeInterview"}


def practice(question):
    from ai import callAI
    r = callAI(
        "연습",
        [{"role": "user", "content": question}],
        system="너는 한국외대 선배 경험을 전하는 도우미다. 두 문장 이내로 답한다.",
    )
    return {"answer": r["text"], "model": r["model"]} if r["ok"] else {"error": r["error"]}


class Handler(BaseHTTPRequestHandler):
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Token")

    def do_OPTIONS(self):
        self.send_response(204); self.cors(); self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self.reply({"error": "요청 형식이 JSON이 아니에요"})
        name = unquote(self.path.split("?")[0].strip("/"))
        token = (self.headers.get("X-Token") or "").strip()
        me = sessions.resolve(token)

        if name in ("", "연습"):
            return self.reply(practice(payload.get("question", "안녕하세요?")))
        fn = ROUTES.get(name)
        if fn is None:
            return self.reply({"error": f"아직 서버에 없는 함수예요: {name}"})
        if not me and name not in NEEDS_NO_LOGIN:
            return self.reply({"error": "로그인이 필요해요"})
        if name in AI_ROUTES:   # 순서: 토큰 확인(위) → 전역 상한 → 사용자별 한도 (limits.check가 이 순서로 본다)
            over = limits.check(me)
            if over:
                return self.reply(over)
        if name == "logout":   # 폐기할 토큰은 헤더의 것만 쓴다(본문 값은 믿지 않는다)
            payload = {**payload, "token": token}
        try:
            self.reply(fn(me, payload))
        except Exception as e:   # 시연 중 서버가 죽지 않게
            self.reply({"error": f"서버 처리 중 문제가 생겼어요: {e}"})

    def reply(self, out):
        b = json.dumps(out, ensure_ascii=False).encode()
        self.send_response(200); self.cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers(); self.wfile.write(b)

    def log_message(self, fmt, *args):   # 요청 로그를 한 줄로
        print(f"{self.command} {unquote(self.path)} ({'로그인' if self.headers.get('X-Token') else '-'})")


if __name__ == "__main__":
    print("개발 서버 함수 실행 중: http://localhost:8787  (끄려면 Ctrl+C)")
    ThreadingHTTPServer(("localhost", 8787), Handler).serve_forever()

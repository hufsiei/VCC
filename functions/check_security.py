# check_security.py — 보안 점검표 자동 점검 (PRD 9-4, 작업 32 통합 배포 직후·작업 38 최종 검증, 11/21)
# 실행: cd functions && python -X utf8 check_security.py          (AI 호출 없음, 1분 이내)
#
# 9-4의 일곱 항목 중 코드로 확인할 수 있는 것을 한 번에 본다. 결과: 통과 / 실패 / 사람 확인(브라우저로 봐야 하는 것).
#   1 남의 기록     임시 서버(임시 runtime, 빈 포트)를 띄워 다른 계정 토큰으로 남의 쪽지·초안·관리자 함수를 직접 부른다 → 거절
#   2 XSS          screens·common에 innerHTML·insertAdjacentHTML·outerHTML·document.write 0건 + 서버 리포트 HTML이 글자를 escape
#   3 키·연락처    .env가 커밋 안 됨, 커밋된 파일·로그·data에 .env 값(8자 이상)이 없음, 흔한 키 모양(sk-ant- 등) 0건
#                  (버킷 이름처럼 비밀이 아닌 설정 값은 NON_SECRET_ENV_KEYS에 키 이름으로 적어 뺀다)
#   4 AI 로그      ai-calls.jsonl에 글 내용 칸이 없고 연락처·메일 모양이 없음
#   5 가상 데이터  data/에 실제 학번 모양(20으로 시작하는 9자리) 0건, 메일은 example.com·noreply만
#   6 토큰         토큰 없이·X-User 헤더만·가짜 토큰으로 부르면 「로그인이 필요해요」
#   7 공개 저장소  11/20 이후 커밋 작성자 메일이 noreply인지, GitHub secret scanning·push protection 상태
#   8 새 AI 경로   (11/27 작업 38) 대화형 들려주기(VCC_TELL_CHAT)·물어보기 대화(VCC_ASK_CHAT)·쪽지 program을 가짜 AI로 끝까지 돌려
#                  callAI로만 부름(직접 호출 0) · callAI 입구가 연락처·메일·학번·URL을 가림 · 요청마다 한도를 먼저 셈 ·
#                  tellChat에 말 원문 없음·남에게 안 보임·7일 지나면 지움 · 쪽지 응답에 상대 학번 없음 ·
#                  점검 중 생긴 기록이 모두 초기화(reset_runtime) 대상
#                  (화면 textContent는 2번이 screens·common 전체를 본다 — 새 화면 코드도 자동으로 들어온다)
# .env 값은 대조에만 쓰고 출력하지 않는다. 하나라도 「실패」면 종료코드 1.
import json
import re
import subprocess
import sys
import tempfile
import threading
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

import paths
import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"     # 실제 data/runtime을 건드리지 않는다

# AI 차단: callAI와 그 아래 호출(CLOVA·Claude)을 모두 막는다. 어디서든 불리면 세고(AI_CALLS), 요금 나가는 호출은 하지 않는다.
# 서버 코드는 `from ai import callAI`로 이름을 복사해 가므로 callAI만 바꾸면 빠진다 → 맨 아래 call_hcx·call_claude도 막는다.
import ai
AI_CALLS = []
ORIG_CALL_AI = ai.callAI    # 8번 마스킹 검사가 진짜 입구(가리기)만 쓴다 — 아래 하위 호출은 가짜로 바꿔 둔 채
# 8번(새 AI 경로, 11/27): 요청마다 한도(limits.check)를 먼저 셌는지 본다. 서버는 요청 하나를 스레드 하나로 돌린다
_REQ = threading.local()
AI_UNLIMITED = []           # 서버 요청 안에서 한도를 세기 전에 AI를 부르려 한 작업명
FAKE_JSON = {}              # 작업명 → 가짜 json(8번이 새 경로를 끝까지 지나가게). 비어 있으면 모두 실패로 돌려준다


def _blocked_call_ai(작업명, *a, **k):
    AI_CALLS.append(작업명)
    if threading.current_thread() is not threading.main_thread() and not getattr(_REQ, "limited", False):
        AI_UNLIMITED.append(작업명)
    if 작업명 in FAKE_JSON:
        j = FAKE_JSON[작업명]
        return {"ok": True, "text": json.dumps(j, ensure_ascii=False), "json": j, "model": "점검"}
    return {"ok": False, "text": "", "json": None, "model": "점검", "error": "점검 중 AI 차단"}


def _blocked_leaf(*a, **k):
    AI_CALLS.append("(하위 호출)")
    raise RuntimeError("점검 중 AI 차단")


ai.callAI = _blocked_call_ai
ai.call_hcx = _blocked_leaf
ai.call_claude = _blocked_leaf

import limits
_orig_limits_check = limits.check


def _counted_check(me, *a, **k):
    _REQ.limited = True
    return _orig_limits_check(me, *a, **k)


limits.check = _counted_check   # local_fn·main·runtime_fns 모두 limits.check(모듈 속성)로 부른다
AI_LOG = paths.LOGS / "ai-calls.jsonl"
AI_LOG_BEFORE = AI_LOG.read_text(encoding="utf-8").count("\n") if AI_LOG.exists() else 0

ROOT = paths.ROOT
results = []   # (번호, 항목, 상태, 설명)


def add(no, item, ok, detail, manual=False):
    results.append((no, item, "사람 확인" if manual else ("통과" if ok else "실패"), detail))


def git(*args):
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout


def tracked_files():
    # -z: 한글 이름 파일(docs/운영노트.md 등)을 git이 "\354\234…"로 감싸 내보내면 is_file()이 거짓이라 검사에서 빠진다
    return [ROOT / p for p in git("ls-files", "-z").split("\0") if p]


# .env에 있어도 비밀이 아닌 설정 값(버킷 이름·주소·지역·접두사). 문서·시험·README에 그대로 적혀 있어도 노출이 아니다.
# 키 이름으로만 뺀다 — 목록에 없는 이름(키·비번 등)은 값이 어디 나와도 실패. 새 설정 값이 생기면 여기에 적는다.
NON_SECRET_ENV_KEYS = {"NCP_OS_BUCKET", "NCP_OS_ENDPOINT", "NCP_OS_REGION", "NCP_OS_PREFIX"}


# ---------- 1·6: 임시 서버로 실제 HTTP 요청 ----------
def start_server():
    import local_fn
    srv = ThreadingHTTPServer(("127.0.0.1", 0), local_fn.Handler)
    local_fn.Handler.log_message = lambda *a, **k: None     # 점검 중 요청 로그는 끈다
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def call(base, name, payload=None, token=None, headers=None):
    h = {"Content-Type": "application/json", **(headers or {})}
    if token:
        h["X-Token"] = token
    req = urllib.request.Request(f"{base}/{name}", data=json.dumps(payload or {}).encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def check_access_and_tokens():
    import runtime_fns
    import sessions
    srv, base = start_server()
    try:
        junior, senior, other = sessions.issue("H0143"), sessions.issue("H0469"), sessions.issue("H0745")
        # 새 쪽지 요청은 「선배 추천 열림」(demand.py) 뒤에만 보낼 수 있다. 안 열면 요청이 잠김으로 막혀 threadId가 없고,
        # 남의 쪽지 접근도 「쪽지가 없어서」 거절되는 헛 통과가 된다. 보낸 사람·남(other) 둘 다 열어 둬서 거절 이유를 소유자 검사로 좁힌다.
        store.load("demands", []).extend({"id": f"R-{h}", "owner": h} for h in ("H0143", "H0745"))
        # 후배1 → 선배1 쪽지 요청, 후배1 내 경험노트 초안 하나
        sent = call(base, "sendMessage", {"to": runtime_fns.peer_ref("H0143", "H0469"), "text": "마르부르크 파견 준비가 궁금해요."}, junior)
        tid = sent.get("threadId")
        runtime_fns.save_my_note("H0143", "마르부르크필립스대학교", "D-test", {"sections": []},
                                 {"sections": [{"name": "생활", "lines": [{"lineId": "L1", "text": "기숙사가 편했어요."}]}]})
        denied = []
        mine = [t["threadId"] for t in call(base, "getMessages", {}, other).get("threads", [])]
        denied.append(("다른 사람 쪽지 목록에 안 보임", tid not in mine))
        r = call(base, "respondRequest", {"threadId": tid, "accept": True}, other)
        denied.append(("남의 쪽지 수락", "error" in r))
        r = call(base, "respondRequest", {"threadId": tid, "cancel": True}, other)
        denied.append(("남의 쪽지 취소", "error" in r))
        r = call(base, "saveConsent", {"draftId": "D-test", "consent": True, "edits": {}}, other)
        denied.append(("남의 경험노트 공개 동의", "error" in r))
        r = call(base, "getAdminOverview", {"dept": "ALL"}, junior)
        denied.append(("학생이 관리자 집계", "error" in r))
        r = call(base, "getIssuedReport", {"reportId": "R-0001"}, junior)
        denied.append(("학생이 발행 리포트", "error" in r))
        bad = [n for n, ok in denied if not ok]
        # 대조군: 당사자(보낸 후배·받은 선배)에게는 그 쪽지가 보인다 — 아니면 위 거절이 「원래 없는 쪽지」라서일 수 있다
        own = [tid in [t["threadId"] for t in call(base, "getMessages", {}, tok).get("threads", [])] for tok in (junior, senior)]
        if not tid:
            add(1, "남의 기록 직접 입력 → 거절", False, "점검용 쪽지 요청이 만들어지지 않음: " + str(sent.get("reason") or sent.get("error") or sent))
        elif not all(own):
            add(1, "남의 기록 직접 입력 → 거절", False, "당사자에게도 쪽지가 안 보여 거절을 가릴 수 없음")
        else:
            add(1, "남의 기록 직접 입력 → 거절", not bad, "6가지 모두 거절(당사자 둘에게는 보임)" if not bad else "거절 안 됨: " + ", ".join(bad))
        add(1, "화면에서 남의 URL 직접 입력", True, "주소창에 남의 threadId·노트 id를 넣어 보기(화면 연결 뒤)", manual=True)

        tries = [("토큰 없음", call(base, "getMessages", {})),
                 ("X-User 헤더만", call(base, "getMessages", {}, headers={"X-User": "H0469"})),
                 ("가짜 토큰", call(base, "getMessages", {}, "not-a-real-token")),
                 ("로그아웃한 토큰", (call(base, "logout", {}, senior), call(base, "getMessages", {}, senior))[1])]
        bad = [n for n, r in tries if r.get("error") != "로그인이 필요해요"]
        add(6, "토큰 없이·임의 헤더로 요청 → 거절", not bad, "4가지 모두 「로그인이 필요해요」" if not bad else "통과됨: " + ", ".join(bad))

        # 새 함수 대조: ROUTES에 있는 함수를 전부 토큰 없이 불러 거절되는지 본다. 나중에 함수가 늘어도 자동으로 들어온다
        # (로그인 없이 부를 수 있는 함수는 local_fn.NEEDS_NO_LOGIN에 적힌 것만 빼 준다)
        import local_fn
        open_ok = [n for n in local_fn.ROUTES if n not in local_fn.NEEDS_NO_LOGIN
                   and call(base, n, {}).get("error") != "로그인이 필요해요"]
        add(6, f"ROUTES 전 함수({len(local_fn.ROUTES)}개) 토큰 없이 → 거절", not open_ok,
            f"로그인 없이 열린 것 {sorted(local_fn.NEEDS_NO_LOGIN)} 외 모두 거절" if not open_ok else "열려 있음: " + ", ".join(open_ok))
        # 관리자 함수는 학생 토큰으로도 거절돼야 한다(콘솔 함수가 학생에게 열리면 집계·리포트가 샌다). 거절 모양은 error 칸
        import admin
        open_adm = [n for n in admin.ROUTES if "error" not in call(base, n, {}, junior)]
        add(1, f"관리자 함수({len(admin.ROUTES)}개) 학생 토큰 → 거절", not open_adm,
            "모두 거절" if not open_adm else "학생에게 열림: " + ", ".join(open_adm))
    finally:
        srv.shutdown()


# ---------- 2: XSS ----------
def check_xss():
    sinks = re.compile(r"\.innerHTML\s*=|\.outerHTML\s*=|insertAdjacentHTML\s*\(|document\.write\s*\(")
    hits = []
    for f in tracked_files():
        if f.suffix in (".js", ".html") and f.parts[len(ROOT.parts)] in ("screens", "common"):
            for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if sinks.search(line):
                    hits.append(f"{f.relative_to(ROOT).as_posix()}:{i}")
    add(2, "화면 코드에 innerHTML 계열 0건", not hits, "0건" if not hits else f"{len(hits)}건: " + ", ".join(hits[:5]))

    import admin
    import suggest
    suggest.callAI = lambda *a, **k: {"ok": False, "json": None, "model": "점검", "error": "AI 안 부름"}
    evil = "<script>alert('XSS')</script><img src=x onerror=\"alert('XSS')\">"
    admin.USAGE.setdefault("questions", [])
    admin.USAGE["questions"] += [{"id": f"XSS{i}", "at": f"2026-10-1{i}T10:00:00+09:00", "colreg_no": "H0100", "crs_nm": evil,
                                  "프로그램명": "마르부르크필립스대학교", "칸": "생활", "status": "hold", "질문": evil,
                                  "운영부서코드": "D01"} for i in range(9)]
    admin.saveReportSettings("staff01", {"dept": "D01", "settings": {"period": "monthly", "day": 1,
                                                                    "recipients": ["intl@example.com"], "sections": admin.SECTIONS}})
    html = admin.issueReport("staff01", {"dept": "D01", "period": {"type": "semester", "value": "2026-2"}}).get("html", "")
    raw = "<script" in html.lower() or "<img" in html.lower()   # escape되면 &lt;img … onerror=로 남는다(글자라 안전)
    add(2, "리포트 HTML이 입력 글자를 escape", bool(html) and not raw, "태그 0건(&lt;script&gt;로 남음)" if not raw else "태그가 그대로 들어감")
    add(2, "입력창에 XSS 두 줄 → 글자로만 보임", True,
        "질문·인터뷰 답·쪽지·콘솔 메일 칸에 두 줄을 넣어 화면 확인(화면 연결 뒤)", manual=True)


# ---------- 3·4·5: 키·로그·데이터 ----------
def env_values():
    vals = []
    for path in paths.env_files():
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            continue
        for line in lines:
            k, sep, v = line.strip().partition("=")
            v = v.strip().strip('"').strip("'")
            if sep and not k.strip().startswith("#") and k.strip() not in NON_SECRET_ENV_KEYS and len(v) >= 8:
                vals.append(v)
                try:   # VCC_LOGIN_PW(JSON)는 안의 비번 하나하나도 본다
                    vals += [str(x) for x in json.loads(v).values() if len(str(x)) >= 8]
                except (ValueError, AttributeError):
                    pass
    return vals


def check_secrets():
    tracked = [p for p in git("ls-files", "-z").split("\0") if p]
    add(3, ".env가 커밋 안 됨", not any(Path(p).name == ".env" for p in tracked), "저장소에 .env 없음")
    vals = env_values()
    key_like = re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY|nv-[A-Za-z0-9]{24,}")
    leaked, shaped = [], []
    for f in tracked_files():
        if not f.is_file() or f.stat().st_size > 20_000_000:
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        if any(v in t for v in vals):
            leaked.append(f.relative_to(ROOT).as_posix())
        if key_like.search(t):
            shaped.append(f.relative_to(ROOT).as_posix())
    add(3, "커밋된 파일에 .env 값 없음", not leaked,
        f".env 값 {len(vals)}개 대조, 0건" if not leaked else "발견: " + ", ".join(leaked[:5]) + " → 키 폐기·재발급")
    add(3, "커밋된 파일에 키 모양 문자열 없음", not shaped, "0건" if not shaped else "확인: " + ", ".join(shaped[:5]))
    # -S "sk-ant-"는 이 파일의 정규식 글자까지 잡아 오탐(원우 11/22). 실제 키 모양(뒤에 20자 이상)만 찾는다
    hist = git("log", "-p", "--all", "-G", "sk-ant-[A-Za-z0-9_-]{20,}", "--format=%h").split()
    add(3, "커밋 이력에 sk-ant- 없음", not hist, "0건" if not hist else f"{len(hist)}개 커밋에 흔적")

    logs = list(paths.LOGS.glob("*")) if paths.LOGS.exists() else []
    in_logs = [p.name for p in logs if p.is_file() and any(v in p.read_text(encoding="utf-8", errors="replace") for v in vals)]
    add(3, "로그에 .env 값 없음", not in_logs, f"로그 {len(logs)}개, 0건" if not in_logs else "발견: " + ", ".join(in_logs))
    add(3, "브라우저 네트워크 탭에 키 없음", True, "개발자 도구 Network에서 요청 헤더·본문 확인(키는 서버에만 있음)", manual=True)

    from mask import find
    log = paths.LOGS / "ai-calls.jsonl"
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()] if log.exists() else []
    # 캐시쓰기·캐시읽기토큰은 Claude 호출의 토큰 수(숫자)다. 글 내용 칸이 아니니 허용(11/26 A안 캐시)
    # 웹검색은 작업 99 시험(11/26)의 검색 횟수(숫자). 미리 PC 로그에 남아 있어 허용(Q-60)
    allowed = {"at", "작업", "모델", "입력토큰", "출력토큰", "캐시쓰기토큰", "캐시읽기토큰", "웹검색", "ms", "ok", "error"}
    extra = sorted({k for r in rows for k in r} - allowed)
    pii = sum(1 for r in rows for v in r.values() if isinstance(v, str) and find(v))
    add(4, "AI 호출 로그에 글 내용·연락처 없음", not extra and not pii,
        f"{len(rows)}줄 · 칸은 시각·작업·모델·토큰·시간·성공만" + ("" if not pii else f" · 연락처 모양 {pii}건")
        if not extra else "글 내용 칸이 있음: " + ", ".join(extra))

    data = ROOT / "data"
    ids, mails = 0, set()
    for f in data.glob("*.*"):
        if f.suffix in (".json", ".csv"):
            t = f.read_text(encoding="utf-8", errors="replace")
            ids += len(re.findall(r"(?<!\d)20\d{7}(?!\d)", t))
            mails |= set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", t))
    real = sorted(m for m in mails if not m.endswith(("example.com", "example.org", "users.noreply.github.com")))
    # 금지 열: 시트에만 두는 이름·성별·나이(CLAUDE.md). JSON은 모든 키를, CSV는 머리 줄을 본다. 비번 이름도 data/에 없어야 한다
    banned = {"studt_na_kr", "sex", "나이(만)", "VCC_LOGIN_PW"}
    found = set()

    def walk(o):
        if isinstance(o, dict):
            found.update(banned & set(o))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    for f in data.glob("*.*"):
        try:
            if f.suffix == ".json":
                walk(json.loads(f.read_text(encoding="utf-8")))
            elif f.suffix == ".csv":
                head = f.read_text(encoding="utf-8-sig").splitlines()[0].split(",")
                found.update(banned & {h.strip().strip('"') for h in head})
        except (ValueError, IndexError, OSError):
            continue
    add(5, "data/에 금지 열(studt_na_kr·sex·나이(만)) 없음", not found, "0건" if not found else "발견: " + ", ".join(sorted(found)))
    add(5, "data/에 실제 학번 모양 없음", ids == 0, "0건" if ids == 0 else f"{ids}건")
    add(5, "data/의 메일은 가상 주소만", not real, f"{len(mails)}개 모두 example 주소" if not real else "확인: " + ", ".join(real[:5]))


# ---------- 8: 새 AI 경로 (11/27 작업 38 — 110 대화형 들려주기 · 119 물어보기 대화 · #379 쪽지 program) ----------
KST = timezone(timedelta(hours=9))
PII_SAMPLE ="연락은 010-1234-5678, hong.gildong@gmail.com, 학번 202312345, https://open.kakao.com/o/abc 로 주세요"
PII_RAW = ("010-1234-5678", "hong.gildong@gmail.com", "202312345", "open.kakao.com")


def _direct_ai_calls():
    """functions/ 안에서 ai.py 밖이 AI를 직접 부르는 곳(모델 호출 함수·SDK·CLOVA 주소). 이 파일의 글자는 조각으로 써서 안 걸린다."""
    rx = re.compile("|".join([r"\bcall_" + r"hcx\s*\(", r"\bcall_" + r"claude\s*\(", r"import\s+anth" + "ropic",
                              r"from\s+anth" + "ropic", r"messages\." + r"create\s*\(", "chat-" + "completions"]))
    # 예외(1차 점검 C-2): 배포 경로 1회 점검용 콘솔 붙여넣기 액션 — 고정 문구만 보내고 사용자 글이 없다. 새 예외는 이유와 함께 여기에
    allowed = {"cloud/clova_once.py"}
    hits = []
    for f in sorted((ROOT / "functions").rglob("*.py")):
        rel = f.relative_to(ROOT / "functions")
        if f.name == "ai.py" or rel.as_posix() in allowed or "lib" in rel.parts:
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if rx.search(line) and not line.lstrip().startswith("#"):
                hits.append(f"{f.relative_to(ROOT).as_posix()}:{i}")
    return hits


def _mask_at_entry():
    """진짜 callAI 입구에 연락처·메일·학번·URL을 넣고, 모델 호출 직전에 받은 글에 원문이 남았는지 본다(HCX·Claude 길 둘 다)."""
    from mask import find
    seen = []

    def grab(messages, system, *a):
        seen.append(json.dumps({"m": messages, "s": system}, ensure_ascii=False))
        return '{"ok": true}', {}
    old_log = ai.LOG_FILE
    ai.LOG_FILE = Path(tempfile.mkdtemp()) / "ai-calls.jsonl"   # 실제 로그에 점검 줄을 남기지 않는다
    ai.call_hcx, ai.call_claude = grab, grab
    try:
        for 작업 in ("말판정", "대화쓰기"):
            ORIG_CALL_AI(작업, [{"role": "user", "content": PII_SAMPLE}], system="선배 말: " + PII_SAMPLE)
    finally:
        ai.call_hcx, ai.call_claude, ai.LOG_FILE = _blocked_leaf, _blocked_leaf, old_log
    left = [r for r in PII_RAW if any(r in s for s in seen)]
    shaped = sum(1 for s in seen if find(s))
    return len(seen) == 2 and not left and not shaped, left, shaped


def check_new_paths():
    import os
    import askboo
    import notes
    import reset_runtime
    import runtime_fns
    import sessions
    import tell_chat

    hits = _direct_ai_calls()
    add(8, "AI는 callAI로만(ai.py 밖 직접 호출 0)", not hits, "0건" if not hits else "직접 호출: " + ", ".join(hits[:5]))
    ok, left, shaped = _mask_at_entry()
    add(8, "callAI 입구가 연락처·메일·학번·URL을 가림", ok,
        "HCX·Claude 길 모두 원문 0건" if ok else f"남음: {', '.join(left) or '-'} · 모양 {shaped}건")

    P = "마르부르크필립스대학교"
    senior, junior, other = "H0469", "H0143", "H0745"
    tok = {u: sessions.issue(u) for u in (senior, junior, other)}
    srv, base = start_server()
    old_env = {k: os.environ.get(k) for k in ("VCC_TELL_CHAT", "VCC_ASK_CHAT")}
    try:
        # ── 110 대화형 들려주기: 가짜 말판정·대화쓰기로 한 턴씩(궁금 → 질문함, 연락처 궁금 → 안 담김) ──
        os.environ["VCC_TELL_CHAT"] = "1"
        FAKE_JSON.update({"쪽지검사": {"ok": True},
                          "말판정": {"종류": "답", "궁금": "현지 기숙사 신청은 언제 하나요?"}})
        s0 = call(base, "interviewNext", {"program": P, "answers": []}, tok[senior])
        FAKE_JSON["대화쓰기"] = {"반응": "좋은 기억이네요.", "칸": s0.get("section"), "더묻기": False, "질문": None}
        said1 = "기숙사는 조용해서 좋았어요. 제 번호는 010-1234-5678이에요. 현지 기숙사 신청은 언제 하나요?"
        a1 = [{"question": s0.get("question"), "section": s0.get("section"), "answer": said1}]
        n_ai = len(AI_CALLS)
        s1 = call(base, "interviewNext", {"program": P, "answers": a1}, tok[senior])
        tried = AI_CALLS[n_ai:]
        FAKE_JSON["말판정"] = {"종류": "답", "궁금": "제 번호 010-1234-5678로 연락 주세요"}
        a2 = a1 + [{"question": s1.get("question"), "section": s1.get("section"), "answer": "제 번호 010-1234-5678로 연락 주세요"}]
        s2 = call(base, "interviewNext", {"program": P, "answers": a2}, tok[senior])
        ran = "말판정" in tried and "대화쓰기" in tried and "heard" in s1
        add(8, "대화형 들려주기가 가짜 AI로 한 턴을 지남", ran,
            f"말판정·대화쓰기 지남 · heard {s1.get('heard')}" if ran else f"안 지남: 시도 {tried} · 응답 {sorted(s1)[:8]}")

        rows = store.load("tellChat", {})
        rec = rows.get(f"{senior}|{P}") or {}
        dumped = json.dumps(rec, ensure_ascii=False)
        raw_left = [x for x in ("010-1234-5678", "기숙사는 조용해서") if x in dumped]
        add(8, "tellChat에 선배 말 원문·연락처 없음(해시만)", bool(rec) and not raw_left and rec.get("owner") == senior,
            f"기록 1건 · 칸 {sorted(rec)}" if rec and not raw_left else ("기록이 안 생김" if not rec else "원문 남음: " + ", ".join(raw_left)))
        planned = {c[0]: c[2] for c in reset_runtime.plan([senior], store.load)}
        add(8, "tellChat·궁금 질문이 12/3 초기화(--only) 대상", bool(planned.get("tellChat")) and bool(planned.get("questions")),
            f"tellChat {planned.get('tellChat', 0)}건 · 질문 {planned.get('questions', 0)}건 지울 목록에 듦"
            if planned.get("tellChat") and planned.get("questions") else f"지울 목록: {planned}")

        held = [q for q in store.load("questions", []) if q.get("colreg_no") == senior]
        bad_held = [q["id"] for q in held if "010-1234-5678" in (q.get("질문") or "")]
        good = [q for q in held if q.get("id") == s1.get("heldQuestionId")]
        add(8, "궁금 → 내 질문함(관문: 연락처 담긴 궁금은 안 담김)",
            bool(good) and not bad_held and "heldQuestionId" not in s2 and good[0].get("프로그램명") == P,
            f"담음 {good[0]['id']}(hold, {P}) · 연락처 궁금 안 담김" if good and not bad_held and "heldQuestionId" not in s2
            else f"담긴 것 {[q.get('id') for q in held]} · s2 heldQuestionId {s2.get('heldQuestionId')}")

        their = call(base, "getInbox", {}, tok[other])
        theirs = json.dumps(their, ensure_ascii=False)
        peek = tell_chat.load(other, P)
        sneak = bool(good) and good[0]["id"] in theirs
        add(8, "남의 tellChat·궁금 질문 안 보임", not sneak and not peek["said"] and not peek["asked"],
            "다른 계정 질문함·판정 기록에 없음" if not sneak and not peek["said"] else "다른 계정에 보임")

        old = (datetime.now(KST) - timedelta(days=tell_chat.KEEP_DAYS + 1)).isoformat(timespec="seconds")
        with store.lock():
            store.load("tellChat", {})[f"{senior}|{P}"]["at"] = old
        tell_chat.save(junior, P, {"said": {}, "asked": {}, "last": None})   # 아무 저장이나 오래된 기록을 지운다
        gone = f"{senior}|{P}" not in store.load("tellChat", {})
        tell_chat.drop(junior, P)
        add(8, f"tellChat 보관기간 {tell_chat.KEEP_DAYS}일 지나면 지움", gone, "8일 된 기록 지워짐" if gone else "8일 된 기록이 남음")

        os.environ["VCC_TELL_CHAT"] = "0"
        n_ai = len(AI_CALLS)
        call(base, "interviewNext", {"program": P, "answers": a1}, tok[other])
        off = [c for c in AI_CALLS[n_ai:] if c in ("말판정", "대화쓰기")]
        add(8, "VCC_TELL_CHAT 끄면 말판정·대화쓰기 안 부름", not off, "0건" if not off else f"{len(off)}건")

        # ── 119 물어보기 대화 응답(VCC_ASK_CHAT): 인사말은 질문함에 안 담김. 병합 전이면 플래그는 아무것도 안 바꾼다 ──
        os.environ["VCC_ASK_CHAT"] = "1"
        FAKE_JSON["대화응답"] = {"message": "반가워요. 연락은 010-1234-5678로 주세요."}
        before = len([q for q in store.load("questions", []) if q.get("colreg_no") == junior])
        r = call(base, "askBoo", {"question": "안녕 BOO 고마워"}, tok[junior])
        after = len([q for q in store.load("questions", []) if q.get("colreg_no") == junior])
        merged = "VCC_ASK_CHAT" in (ROOT / "functions" / "askboo.py").read_text(encoding="utf-8")
        # askLog(초기화 대상 아님, 사람 칸 없음)에 남는 message도 본다 — 119 뒤에는 AI가 쓴 글이 이 칸에 들어간다
        last_log = (store.load("askLog", []) or [{}])[-1]
        leak = "010-1234-5678" in json.dumps([r, last_log.get("message")], ensure_ascii=False)
        add(8, "물어보기 대화(VCC_ASK_CHAT): 질문함 안 담음·대화에 없는 연락처 버림", before == after and not leak,
            (f"status {r.get('status')} · 질문함 그대로" + ("" if merged else " · 참고: 119 병합 전(플래그 코드 없음) — 병합 뒤 다시 돌린다"))
            if before == after and not leak else f"질문함 {before}→{after} · 연락처 응답에 남음 {leak}")

        # ── #379 쪽지 program: 보낸 사람이 그 노트 추천에서 받은 선배일 때만, 응답에 상대 학번 없음 ──
        target = "H0241"
        store.load("demands", []).append({"id": "R-H0143-8", "owner": junior})
        store.load("shownSeniors", {}).setdefault(junior, {})[notes.note_id(P)] = {"ids": [target]}
        sent = call(base, "sendMessage", {"to": runtime_fns.peer_ref(junior, target), "noteId": notes.note_id(P),
                                          "text": "기숙사 준비가 궁금해요."}, tok[junior])
        threads = call(base, "getMessages", {}, tok[junior]).get("threads", [])
        t = next((x for x in threads if x.get("threadId") == sent.get("threadId")), {})
        forged = runtime_fns._request_program(junior, target, notes.note_id("없는 프로그램"))
        add(8, "쪽지 program은 받은 추천의 노트만", t.get("program") == P and forged is None,
            f"{P} 저장 · 추천 안 받은 노트 → 없음" if t.get("program") == P and forged is None
            else f"program {t.get('program')!r} · 위조 {forged!r} · {sent.get('reason') or sent.get('error') or ''}")
        ids_out = sorted(set(re.findall(r"H\d{4}", json.dumps(threads, ensure_ascii=False))) - {junior})
        add(8, "쪽지 응답에 상대 학번 없음", not ids_out, "0건" if not ids_out else "보임: " + ", ".join(ids_out))
    finally:
        srv.shutdown()
        FAKE_JSON.clear()
        for k, v in old_env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    add(8, "서버 요청은 AI 전에 한도(분당 10·일 100)를 셈", not AI_UNLIMITED,
        "한도 밖 AI 시도 0건" if not AI_UNLIMITED else "한도 안 세고 부름: " + ", ".join(sorted(set(AI_UNLIMITED))))
    # 점검 중 생긴 기록(임시 runtime)이 모두 초기화 도구의 규칙 안인지 — 새 기록 이름이 생기면 여기서 걸린다
    names = sorted(p.stem for p in store.RUNTIME.glob("*.json")) if store.RUNTIME.exists() else []
    names = sorted(set(names) | set(getattr(store, "_cache", {}) or {}))   # 저장 전 메모리에만 있는 기록도
    known = reset_runtime.HANDLED | set(reset_runtime.UNTOUCHED)
    loose = [n for n in names if n not in known]
    add(8, "점검 중 생긴 기록이 모두 초기화 규칙 안", not loose,
        f"기록 {len(names)}종 · reset_runtime 규칙 밖 0" if not loose else "규칙 밖: " + ", ".join(loose))


# ---------- 7: 공개 저장소 ----------
def check_public_repo():
    # 기준: noreply 규칙을 넣은 커밋(a49e5d4, PR #73) 다음부터. 그 전 커밋은 기록을 고칠 수 없어 개수만 알린다.
    # 공개 저장소에 붙여 넣을 수 있는 출력이라 메일 주소 자체는 찍지 않는다.
    rows = [l.split(" ", 1) for l in git("log", "a49e5d4..HEAD", "--format=%h %ae").splitlines() if l]
    bad = [h for h, a in rows if not a.endswith("users.noreply.github.com")]
    old = sum(1 for a in git("log", "a49e5d4", "--format=%ae").splitlines() if not a.endswith("users.noreply.github.com"))
    add(7, "규칙(PR #73) 이후 커밋 메일이 noreply", not bad,
        (f"커밋 {len(rows)}개 모두 noreply" if not bad else f"noreply 아님 {len(bad)}개: " + ", ".join(bad[:5]))
        + f" · 참고: 규칙 전 커밋 {old}개는 개인 메일(기록이라 그대로 둠)")
    try:
        r = subprocess.run(["gh", "api", "repos/hufsiei/VCC", "-q", ".security_and_analysis"],
                           capture_output=True, text=True, timeout=20)
        sa = json.loads(r.stdout or "{}")
        on = {k: (v or {}).get("status") for k, v in sa.items()}
        need = ["secret_scanning", "secret_scanning_push_protection"]
        off = [k for k in need if on.get(k) != "enabled"]
        add(7, "secret scanning·push protection 켜짐", not off, "둘 다 켜짐" if not off else "꺼짐: " + ", ".join(off))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        add(7, "secret scanning·push protection 켜짐", True, "GitHub 저장소 Settings → Code security에서 확인", manual=True)


def main():
    for step in (check_access_and_tokens, check_xss, check_secrets, check_public_repo, check_new_paths):
        try:
            step()
        except Exception as e:   # 한 항목이 깨져도 나머지는 본다
            add(0, step.__name__, False, f"점검 중 오류: {type(e).__name__}: {e}")
    # 서버 흐름이 AI를 부르려 한 것(예: sendMessage의 쪽지검사)은 위 가짜 callAI가 막아 실제 호출·요금은 0이다.
    # 막힌 시도는 알려 주기만 한다. 실패는 하위 호출(CLOVA·Claude)까지 닿은 경우 = 차단이 뚫린 경우.
    # ai-calls.jsonl 줄 수는 다른 창이 AI를 돌리면 함께 늘어 증거가 못 되니 참고로만 적는다.
    after = AI_LOG.read_text(encoding="utf-8").count("\n") if AI_LOG.exists() else 0
    leaked = [c for c in AI_CALLS if c == "(하위 호출)"]
    tried = sorted({c for c in AI_CALLS if c != "(하위 호출)"})
    add(0, "점검 중 AI 실제 호출 0건", not leaked,
        f"실제 호출 0건 · 막은 시도 {len(AI_CALLS)}건" + (f"({', '.join(tried)})" if tried else "")
        + f" · 참고: ai-calls.jsonl +{after - AI_LOG_BEFORE}줄(다른 창 호출 포함)" if not leaked
        else f"차단이 뚫려 AI 하위 호출 {len(leaked)}건 — 점검 중단하고 키 사용량 확인")
    print("보안 점검표 (PRD 9-4)\n")
    for no, item, state, detail in sorted(results, key=lambda r: r[0]):
        print(f"{state:6} {no} {item} — {detail}")
    fails = sum(1 for r in results if r[2] == "실패")
    manual = sum(1 for r in results if r[2] == "사람 확인")
    print(f"\n통과 {sum(1 for r in results if r[2] == '통과')} · 실패 {fails} · 사람 확인 {manual}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

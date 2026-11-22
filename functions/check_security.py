# check_security.py — 보안 점검표 자동 점검 (PRD 9-4, 작업 32 통합 배포 직후·작업 38 최종 검증, 11/21)
# 실행: cd functions && python -X utf8 check_security.py          (AI 호출 없음, 1분 이내)
#
# 9-4의 일곱 항목 중 코드로 확인할 수 있는 것을 한 번에 본다. 결과: 통과 / 실패 / 사람 확인(브라우저로 봐야 하는 것).
#   1 남의 기록     임시 서버(임시 runtime, 빈 포트)를 띄워 다른 계정 토큰으로 남의 쪽지·초안·관리자 함수를 직접 부른다 → 거절
#   2 XSS          screens·common에 innerHTML·insertAdjacentHTML·outerHTML·document.write 0건 + 서버 리포트 HTML이 글자를 escape
#   3 키·연락처    .env가 커밋 안 됨, 커밋된 파일·로그·data에 .env 값(8자 이상)이 없음, 흔한 키 모양(sk-ant- 등) 0건
#   4 AI 로그      ai-calls.jsonl에 글 내용 칸이 없고 연락처·메일 모양이 없음
#   5 가상 데이터  data/에 실제 학번 모양(20으로 시작하는 9자리) 0건, 메일은 example.com·noreply만
#   6 토큰         토큰 없이·X-User 헤더만·가짜 토큰으로 부르면 「로그인이 필요해요」
#   7 공개 저장소  11/20 이후 커밋 작성자 메일이 noreply인지, GitHub secret scanning·push protection 상태
# .env 값은 대조에만 쓰고 출력하지 않는다. 하나라도 「실패」면 종료코드 1.
import json
import re
import subprocess
import sys
import tempfile
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import paths
import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"     # 실제 data/runtime을 건드리지 않는다

ROOT = paths.ROOT
results = []   # (번호, 항목, 상태, 설명)


def add(no, item, ok, detail, manual=False):
    results.append((no, item, "사람 확인" if manual else ("통과" if ok else "실패"), detail))


def git(*args):
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout


def tracked_files():
    return [ROOT / p for p in git("ls-files").splitlines() if p]


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
        # 후배1 → 선배1 쪽지 요청, 후배1 내 경험노트 초안 하나
        sent = call(base, "sendMessage", {"to": "H0469", "text": "마르부르크 파견 준비가 궁금해요."}, junior)
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
        add(1, "남의 기록 직접 입력 → 거절", not bad and bool(tid),
            "6가지 모두 거절" if not bad else "거절 안 됨: " + ", ".join(bad))
        add(1, "화면에서 남의 URL 직접 입력", True, "주소창에 남의 threadId·노트 id를 넣어 보기(화면 연결 뒤)", manual=True)

        tries = [("토큰 없음", call(base, "getMessages", {})),
                 ("X-User 헤더만", call(base, "getMessages", {}, headers={"X-User": "H0469"})),
                 ("가짜 토큰", call(base, "getMessages", {}, "not-a-real-token")),
                 ("로그아웃한 토큰", (call(base, "logout", {}, senior), call(base, "getMessages", {}, senior))[1])]
        bad = [n for n, r in tries if r.get("error") != "로그인이 필요해요"]
        add(6, "토큰 없이·임의 헤더로 요청 → 거절", not bad, "4가지 모두 「로그인이 필요해요」" if not bad else "통과됨: " + ", ".join(bad))
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
            if sep and not k.strip().startswith("#") and len(v) >= 8:
                vals.append(v)
                try:   # VCC_LOGIN_PW(JSON)는 안의 비번 하나하나도 본다
                    vals += [str(x) for x in json.loads(v).values() if len(str(x)) >= 8]
                except (ValueError, AttributeError):
                    pass
    return vals


def check_secrets():
    tracked = git("ls-files").splitlines()
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
    allowed = {"at", "작업", "모델", "입력토큰", "출력토큰", "ms", "ok", "error"}
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
    add(5, "data/에 실제 학번 모양 없음", ids == 0, "0건" if ids == 0 else f"{ids}건")
    add(5, "data/의 메일은 가상 주소만", not real, f"{len(mails)}개 모두 example 주소" if not real else "확인: " + ", ".join(real[:5]))


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
    for step in (check_access_and_tokens, check_xss, check_secrets, check_public_repo):
        try:
            step()
        except Exception as e:   # 한 항목이 깨져도 나머지는 본다
            add(0, step.__name__, False, f"점검 중 오류: {type(e).__name__}: {e}")
    print("보안 점검표 (PRD 9-4)\n")
    for no, item, state, detail in sorted(results, key=lambda r: r[0]):
        print(f"{state:6} {no} {item} — {detail}")
    fails = sum(1 for r in results if r[2] == "실패")
    manual = sum(1 for r in results if r[2] == "사람 확인")
    print(f"\n통과 {sum(1 for r in results if r[2] == '통과')} · 실패 {fails} · 사람 확인 {manual}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

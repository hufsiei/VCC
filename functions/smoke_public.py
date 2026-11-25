# smoke_public.py — 공개 서버 연기(煙氣) 시험 (작업 39, 미리)
# 실행: cd functions && python -X utf8 smoke_public.py [--base <공개 주소>] [--ai]
#   서버 zip을 다시 올릴 때마다(12/3 최종 배포 포함) 사람이 화면을 눌러 보던 것을 명령 한 줄로 한다.
#   1 _diag(꺼져 있으면 「건너뜀」 — 정상)  2 시연 계정 5개 로그인  3 계정에 맞는 읽기 함수 1회씩  4 로그아웃(토큰 폐기)
#   결과를 「함수 · 계정 · 통과/실패 · 걸린 시간」 표로 출력, 실패가 하나라도 있으면 종료코드 1.
# 기본은 읽기만 한다. 쓰기 함수(sendMessage·saveConsent·scrapNote 등)와 AI 함수는 부르지 않는다.
#   --ai: askBoo 1회(H0143, 질문함에 남는다 — 기본 꺼짐). 그 밖의 AI 함수(interviewNext·summarizeInterview·issueReport)는 어떤 옵션으로도 부르지 않는다.
#   getReportSettings·listIssuedReports는 부르면 서버가 리포트를 자동 발행(_auto_issue)할 수 있어 뺐다.
# 로그인 비번은 .env의 VCC_LOGIN_PW에서만 읽고 출력하지 않는다. 응답 내용도 출력하지 않고 통과/실패와 오류 문구만 보인다.
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

import paths

DEFAULT_BASE = "https://x1ey63q7ei.apigw.ntruss.com/vcc-api/dev"   # common/data.js FN_PUBLIC과 같다
STUDENTS = ("H0143", "H0469", "H0241")
STAFF = ("staff01", "staff02")
TIMEOUT = 30

rows = []   # (함수, 계정, 상태, ms, 비고)


def post(base, name, payload=None, token=None):
    """data.js와 같은 규약: POST {base}/{name}?fn={name}, 헤더 X-Token. 돌려주는 값: (응답 dict, ms)."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Token"] = token
    req = urllib.request.Request(f"{base.rstrip('/')}/{name}?fn={name}", data=json.dumps(payload or {}).encode(),
                                 headers=headers, method="POST")
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        out = _parse(body, f"HTTP {e.code}")
    except (urllib.error.URLError, OSError) as e:
        return {"error": f"연결 실패: {type(e).__name__}"}, round((time.perf_counter() - t) * 1000)
    else:
        out = _parse(body, "응답이 JSON이 아님")
    return out, round((time.perf_counter() - t) * 1000)


def _parse(body, fallback):
    try:
        out = json.loads(body)
        return out if isinstance(out, dict) else {"error": fallback}
    except ValueError:
        return {"error": fallback}


def record(fn, who, out, ms, ok=None, note=""):
    """ok를 안 주면 「error 칸이 없으면 통과」."""
    good = ("error" not in out) if ok is None else ok
    rows.append((fn, who, "통과" if good else "실패", ms, "" if good else str(out.get("error") or note or "예상과 다른 응답")[:60]))
    return good


def passwords():
    paths.load_env()
    raw = os.environ.get("VCC_LOGIN_PW", "")
    try:
        table = json.loads(raw)
    except ValueError:
        table = {}
    return table if isinstance(table, dict) else {}


def run(base, with_ai):
    # 1 _diag — 서버에서 VCC_DIAG를 꺼 두면 「없는 함수」로 거절한다. 그것도 정상(건너뜀).
    out, ms = post(base, "_diag")
    if "arg_keys" in out:
        record("_diag", "-", out, ms, ok="net" in out, note="net 칸 없음")
    elif "없는 함수" in str(out.get("error", "")) or "서버에 없는" in str(out.get("error", "")):
        rows.append(("_diag", "-", "건너뜀", ms, "VCC_DIAG 꺼짐(정상)"))
    else:
        record("_diag", "-", out, ms, ok=False)

    table = passwords()
    if not table:
        rows.append(("login", "-", "실패", 0, ".env의 VCC_LOGIN_PW를 읽지 못함"))
        return
    tokens = {}
    try:
        # 2 로그인 — 학생은 개별 항목 → 공용("*") 순, 직원은 개별 항목만(account.login과 같은 규칙)
        for uid in (*STUDENTS, *STAFF):
            pw = table.get(uid, table.get("*") if uid.startswith("H") else None)
            if pw is None:
                rows.append(("login", uid, "실패", 0, "VCC_LOGIN_PW에 이 계정 비번이 없음"))
                continue
            out, ms = post(base, "login", {"id": uid, "pw": pw})
            user = out.get("user") or {}
            if record("login", uid, out, ms, ok=bool(out.get("ok") and user.get("token")), note="로그인 거절"):
                tokens[uid] = user["token"]

        # 3 학생 읽기 함수
        note_id = None
        for uid in STUDENTS:
            tk = tokens.get(uid)
            if not tk:
                continue
            out, ms = post(base, "getMe", {}, tk)
            record("getMe", uid, out, ms, ok="error" not in out and out.get("colreg_no") == uid, note="본인 정보가 아님")
            out, ms = post(base, "listNotes", {}, tk)
            cards = out.get("notes") if isinstance(out.get("notes"), list) else (out if isinstance(out, list) else [])
            record("listNotes", uid, out, ms, ok="error" not in out and bool(cards), note="노트 카드 0장")
            if note_id is None and cards:
                note_id = cards[0].get("id")
            out, ms = post(base, "getMessages", {}, tk)
            record("getMessages", uid, out, ms)
            out, ms = post(base, "getInbox", {}, tk)
            record("getInbox", uid, out, ms)
            if uid == "H0143":   # 내 경험노트가 있으면 상세도 한 번(없으면 건너뜀)
                mine = [c.get("id") for c in (out.get("myNotes") or []) if isinstance(c, dict) and c.get("id")]
                if mine:
                    out2, ms2 = post(base, "getMyNote", {"id": mine[0]}, tk)
                    record("getMyNote", uid, out2, ms2)
        if note_id and tokens.get("H0143"):
            out, ms = post(base, "getNote", {"id": note_id}, tokens["H0143"])
            record("getNote", "H0143", out, ms, ok="error" not in out and out.get("id") == note_id, note="노트 id 불일치")
            # 추천은 선배 추천이 안 열린 계정이면 {locked} 응답 — error가 아니라 통과(읽기만, 상태를 바꾸지 않는다)
            out, ms = post(base, "recommendSeniors", {"noteId": note_id}, tokens["H0143"])
            record("recommendSeniors", "H0143", out, ms)
        elif note_id is None:
            rows.append(("getNote·recommendSeniors", "H0143", "실패", 0, "노트 id를 못 구함(listNotes 실패)"))

        # 3 관리자 읽기 함수(직원: 총괄 staff01·부서 staff02)
        for uid in STAFF:
            tk = tokens.get(uid)
            if not tk:
                continue
            out, ms = post(base, "getDepartments", {}, tk)
            record("getDepartments", uid, out, ms, ok="error" not in out and bool(out.get("departments")), note="부서 목록 비어 있음")
            out, ms = post(base, "getAdminOverview", {}, tk)
            record("getAdminOverview", uid, out, ms)
            out, ms = post(base, "getAdminSuggestions", {}, tk)
            record("getAdminSuggestions", uid, out, ms)

        # 권한 확인(실패해야 통과): 학생 토큰으로 관리자 함수 → 거절
        if tokens.get("H0143"):
            out, ms = post(base, "getAdminOverview", {}, tokens["H0143"])
            record("getAdminOverview(학생 거절)", "H0143", out, ms, ok="error" in out, note="학생에게 관리자 집계가 열림")

        # --ai: askBoo 1회(질문함에 남는다)
        if with_ai and tokens.get("H0143"):
            out, ms = post(base, "askBoo", {"question": "독일 파견 준비는 어떻게 해야 하나요?"}, tokens["H0143"])
            record("askBoo(--ai)", "H0143", out, ms)
    finally:
        # 4 토큰 폐기
        for uid, tk in tokens.items():
            out, ms = post(base, "logout", {}, tk)
            record("logout", uid, out, ms, ok=bool(out.get("ok")), note="토큰 폐기 실패")


def main():
    ap = argparse.ArgumentParser(description="공개 서버 연기 시험(읽기만)")
    ap.add_argument("--base", default=DEFAULT_BASE, help="서버 주소(기본: 공개 API Gateway)")
    ap.add_argument("--ai", action="store_true", help="askBoo 1회 추가(질문함에 남음)")
    a = ap.parse_args()
    print(f"대상: {a.base}" + ("  (--ai: askBoo 1회 포함)" if a.ai else "  (읽기만)"))
    run(a.base, a.ai)
    w = max(len(r[0]) for r in rows)
    print(f"\n{'함수'.ljust(w)}  {'계정':<8} {'결과':<4} {'시간(ms)':>8}  비고")
    for fn, who, st, ms, note in rows:
        print(f"{fn.ljust(w)}  {who:<8} {st:<4} {ms:>8}  {note}")
    bad = [r for r in rows if r[2] == "실패"]
    print(f"\n통과 {sum(r[2] == '통과' for r in rows)} · 건너뜀 {sum(r[2] == '건너뜀' for r in rows)} · 실패 {len(bad)}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

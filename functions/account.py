# account.py — login·getMe 서버 함수 (작성: 미리)
# 응답 모양은 docs/spec-v1.md 4장 login·getMe. 읽기만 하고 저장하지 않는다. AI 없음.
#
#   login(me, {id, pw})  — 환경변수 VCC_LOGIN_PW(JSON {"학번":"비번"})와 대조하고 토큰을 발급한다(작업 73).
#                          students.json의 비번 열은 읽지 않는다. 로그인 전이라 me는 비어 있다.
#   logout(me, {token})  — 토큰을 폐기한다.
#   getMe(me, {})        — 내 학생 행(번호·비번 제외) + 이수 기록 3종(시트 헤더 그대로, 본문 칸 제외)
import json
import os
from pathlib import Path

import sessions
from runtime_fns import student

DATA = Path(__file__).resolve().parent.parent / "data"
FAIL = {"ok": False, "reason": "아이디 또는 비밀번호가 맞지 않아요."}
HIDDEN = {"번호", "비번"}   # 응답에 넣지 않는 열(spec 0장)

# 이수 기록에 담는 열(spec 4장 getMe 예시). 귀국보고서 문항·현장실습 후기 본문은 뺀다.
EXTRA_KEYS = ["이수학년도", "이수학기(1~4)", "학기구분", "프로그램명", "비교과 유형", "이수 당시 학년"]
REPORT_KEYS = ["학년도", "학기", "국가", "대학명"]
INTERN_KEYS = ["학년도", "학기", "업체명", "직군"]

_cache = {}


def _load_env():
    """저장소 맨 위의 .env(KEY=값 줄)를 환경변수로 읽는다(ai.py와 같은 규칙). 이미 있는 환경변수는 덮지 않는다."""
    try:
        text = (DATA.parent / ".env").read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        k, sep, v = line.strip().partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if sep and k and v and not k.startswith("#") and k not in os.environ:
            os.environ[k] = v


_load_env()


def _passwords():
    """VCC_LOGIN_PW(JSON 문자열)를 {학번: 비번}으로. 없거나 형식이 틀리면 빈 표(아무도 로그인 못 함)."""
    try:
        pw = json.loads(os.environ.get("VCC_LOGIN_PW") or "{}")
    except ValueError:
        return {}
    return pw if isinstance(pw, dict) else {}


def _rows(name):
    if name not in _cache:
        try:
            _cache[name] = json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _cache[name] = []
    return _cache[name]


def _pick(rows, id_key, me, keys):
    return [{k: r.get(k) for k in keys} for r in rows if r.get(id_key) == me]


def login(me, p):
    uid = str(p.get("id") or "").strip()
    row = student(uid)
    expected = _passwords().get(uid)
    if not row or expected is None or str(p.get("pw") or "") != str(expected):
        return FAIL
    token = sessions.issue(uid)
    if not uid.startswith("staff"):
        return {"ok": True, "user": {"colreg_no": uid, "status": "학생", "token": token}}
    dept = row.get("crs_nm") or ""
    user = {"colreg_no": uid, "token": token, "status": "직원", "부서명": dept, "권한": "총괄" if dept == "전체" else "부서"}
    code = next((d["부서코드"] for d in _rows("departments") if d.get("부서명") == dept), None)
    if code:
        user["부서코드"] = code
    return {"ok": True, "user": user}


def logout(me, p):
    sessions.revoke(p.get("token"))
    return {"ok": True}


def getMe(me, p):
    row = student(me)
    if not row:
        return {"error": "학생 정보를 찾지 못했어요"}
    out = {k: v for k, v in row.items() if k not in HIDDEN}
    out["비교과이수내역"] = _pick(_rows("extracurricular"), "가상학번", me, EXTRA_KEYS)
    out["귀국보고서"] = _pick(_rows("reports"), "학번", me, REPORT_KEYS)
    out["현장실습후기"] = _pick(_rows("internships"), "학번", me, INTERN_KEYS)
    return out


ROUTES = {"login": login, "logout": logout, "getMe": getMe}

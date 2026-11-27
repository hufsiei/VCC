# test_reset_runtime.py — 시연 계정만 초기화 reset_runtime.py --only (작업 39, 11/25)
# 실행: cd functions && python -X utf8 test_reset_runtime.py   하나라도 틀리면 종료코드 1. 네트워크·AI를 부르지 않는다.
# 가짜 저장소: ① 임시 폴더(file)  ② 가짜 버킷(ncp — 저장 직전 다시 읽어 합치는 길). data/runtime·실제 버킷을 건드리지 않는다.
import contextlib
import copy
import io
import json
import os
import re
import runpy
import sys
import tempfile
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import reset_runtime as rr

DEMO = ["H0143", "H0469", "H0241", "staff01", "staff02"]
J1, S1, S2 = "H0143", "H0469", "H0241"        # 후배1 · 선배1 · 선배2
OTHER, OTHER2 = "H0102", "H0555"              # 미리 시험 계정(다른 계정)
NM, NX = "N-marburg", "N-other"
fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


SEED = {
    "messages": {
        "T-0001": {"asker": J1, "senior": S1, "askerNickname": "용감한 수달", "status": "accepted", "messages": [],
                   "program": "마르부르크"},   # #379 쪽지 기준 프로그램 — 대화째 지워지면 함께 없어진다
        "T-0002": {"asker": OTHER, "senior": S2, "askerNickname": "느긋한 판다", "status": "waiting", "messages": []},  # 섞인 대화
        "T-0003": {"asker": OTHER, "senior": OTHER2, "askerNickname": "조용한 고래", "status": "accepted", "messages": [{"from": OTHER, "text": "안녕"}],
                   "program": "마르부르크"},
    },
    "nicknames": {J1: {S1: "A", S2: "B"}, OTHER: {S2: "A", OTHER2: "B"}},
    "pendingNicknames": {f"{S1}|{J1}": "수줍은 토끼", f"{S2}|{OTHER}": "x", f"{OTHER2}|{OTHER}": "밝은 여우"},
    "shownSeniors": {J1: {NM: {"ids": [S1, S2], "version": 1}}, OTHER: {NM: {"ids": [S2, OTHER2], "version": 1}}},
    "questions": [
        {"id": "Q-0001", "colreg_no": J1, "질문": "기숙사?", "status": "hold"},
        {"id": "Q-0002", "colreg_no": OTHER, "질문": "학점?", "status": "answered"},
    ],
    "demands": [{"id": "R-0001", "owner": J1}, {"id": "R-0002", "owner": OTHER}],
    "consents": {"D-0001": {"owner": S1}, "D-0002": {"owner": OTHER2}},
    "myNotes": {"M-0001": {"owner": S1, "program": "마르부르크"}, "M-0002": {"owner": OTHER2, "program": "마르부르크"}},
    "noteLines": [
        {"noteId": NM, "owner": S1, "text": "선배1 문장", "myNoteId": "M-0001"},
        {"noteId": NM, "owner": OTHER2, "text": "시험 인터뷰 문장", "myNoteId": "M-0002"},
        {"noteId": NX, "owner": OTHER2, "text": "다른 노트 문장", "myNoteId": "M-0003"},
    ],
    "noteVersions": {NM: 3, NX: 1},
    "reported": {"L-I0001": {"by": J1}, "L-I0002": {"by": OTHER}},
    "askLog": [{"id": "a1", "question": "기숙사?"}],
    "threadReports": [{"threadId": "T-0002", "by": OTHER}, {"threadId": "T-0003", "by": OTHER2}],
    "recommendOptOut": {S2: {"at": "x"}, OTHER2: {"at": "x"}},
    "alerts": {
        S1: [{"text": "요청", "threadId": "T-0001"}],
        OTHER: [{"text": "요청 수락", "threadId": "T-0002"}, {"text": "답", "questionId": "Q-0002"}, {"text": "새 대화", "threadId": "T-0003"}],
        OTHER2: [{"text": "질문 답 알림(지워지는 질문)", "questionId": "Q-0001"}, {"text": "반영", "noteId": NM}],
    },
    "counters": {"T": 3, "Q": 2},
    "aiUsage": {"_all": {"day": "d", "dayCount": 9}, J1: {"dayCount": 3}, OTHER: {"dayCount": 2}},
    "sessions": {"tok1": {"me": J1, "exp": 1}, "tok2": {"me": "staff01", "exp": 1}, "tok3": {"me": OTHER, "exp": 1}},
    "interviewDrafts": {f"{S2}|마르부르크": {"owner": S2}, f"{OTHER2}|마르부르크": {"owner": OTHER2}},
    "scraps": {J1: [NM], OTHER: [NM]},
    "tellChat": {f"{S1}|마르부르크": {"owner": S1}, f"{OTHER2}|마르부르크": {"owner": OTHER2}},   # 작업 110
    "loginFails": {J1: {"since": 1, "fails": 5, "until": 2}, OTHER: {"since": 1, "fails": 1, "until": 0}},
    "reportSettings": {"D04": {"by": "staff01"}},
    "issuedReports": [{"reportId": "R-0009", "dept": "D04"}],
    "reportHtml": {"R-0009": "<p/>"},
    "suggestionStatus": {"S-1": {"by": "staff01"}},
    "mystery": {"H0143": 1},
}


def seed_files():
    store.RUNTIME.mkdir(parents=True, exist_ok=True)
    for p in store.RUNTIME.glob("*.json"):
        p.unlink()
    for name, v in SEED.items():
        (store.RUNTIME / f"{name}.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
    store._cache.clear()
    store._base.clear()


def read(name):
    return json.loads((store.RUNTIME / f"{name}.json").read_text(encoding="utf-8"))


def run_cli(*args):
    old = sys.argv
    sys.argv = ["reset_runtime.py", *args]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            runpy.run_path(str(Path(rr.__file__)), run_name="__main__")
    finally:
        sys.argv = old
    return buf.getvalue()


def check_after(r, tag):
    """r(name) = 초기화 뒤 기록."""
    m = r("messages")
    expect(f"{tag} 시연 계정 사이 대화 지움", "T-0001" not in m)
    expect(f"{tag} 섞인 대화(다른 계정 ↔ 선배2) 지움", "T-0002" not in m)
    expect(f"{tag} 다른 계정끼리 대화 그대로", m.get("T-0003") == SEED["messages"]["T-0003"])
    expect(f"{tag} 닉네임: 시연 계정 지움·다른 계정 그대로", r("nicknames") == {OTHER: {S2: "A", OTHER2: "B"}})
    expect(f"{tag} 미리 정한 닉네임: 시연 계정 들어간 것만 지움", r("pendingNicknames") == {f"{OTHER2}|{OTHER}": "밝은 여우"})
    expect(f"{tag} 추천 목록: 시연 계정 지움", list(r("shownSeniors")) == [OTHER])
    expect(f"{tag} 질문: 다른 계정 것만", [q["id"] for q in r("questions")] == ["Q-0002"])
    expect(f"{tag} 궁금한 것 정리: 다른 계정 것만", r("demands") == [{"id": "R-0002", "owner": OTHER}])
    expect(f"{tag} 공개 동의: 다른 계정 것만", list(r("consents")) == ["D-0002"])
    expect(f"{tag} 내 경험노트(시험 인터뷰) 그대로", r("myNotes") == {"M-0002": SEED["myNotes"]["M-0002"]})
    expect(f"{tag} noteLines: 선배1 문장만 빠짐", [x["text"] for x in r("noteLines")] == ["시험 인터뷰 문장", "다른 노트 문장"])
    expect(f"{tag} noteVersions: 문장이 빠진 노트만 +1", r("noteVersions") == {NM: 4, NX: 1})
    expect(f"{tag} 문장 신고: 시연 계정 신고만 지움", list(r("reported")) == ["L-I0002"])
    expect(f"{tag} 대화 신고: 지운 대화 것 지움", r("threadReports") == [{"threadId": "T-0003", "by": OTHER2}])
    expect(f"{tag} 추천받기 끔: 선배2만 지움", list(r("recommendOptOut")) == [OTHER2])
    al = r("alerts")
    expect(f"{tag} 알림: 시연 계정 것 지움", S1 not in al)
    expect(f"{tag} 알림: 다른 계정이 받은 지운 대화 알림 지움·나머지 그대로",
           al.get(OTHER) == [{"text": "답", "questionId": "Q-0002"}, {"text": "새 대화", "threadId": "T-0003"}])
    expect(f"{tag} 알림: 지운 질문의 알림 지움", al.get(OTHER2) == [{"text": "반영", "noteId": NM}])
    expect(f"{tag} AI 호출 수: 시연 계정만 지움(전체 합계 그대로)", r("aiUsage") == {"_all": SEED["aiUsage"]["_all"], OTHER: {"dayCount": 2}})
    expect(f"{tag} 로그인: 시연 계정 토큰만 지움", list(r("sessions")) == ["tok3"])
    expect(f"{tag} 인터뷰 초안: 다른 계정 것만", list(r("interviewDrafts")) == [f"{OTHER2}|마르부르크"])
    expect(f"{tag} 스크랩: 다른 계정 것만", r("scraps") == {OTHER: [NM]})
    expect(f"{tag} 대화형 인터뷰 판정: 다른 계정 것만", list(r("tellChat")) == [f"{OTHER2}|마르부르크"])
    expect(f"{tag} 로그인 실패 기록: 다른 계정 것만", list(r("loginFails")) == [OTHER])
    for name in ("askLog", "counters", "reportSettings", "issuedReports", "reportHtml", "suggestionStatus", "mystery"):
        expect(f"{tag} {name} 건드리지 않음", r(name) == SEED[name])


# ── 1. file: 기본은 보기만 ─────────────────────────────────────────────
seed_files()
before = {p.name: p.read_text(encoding="utf-8") for p in store.RUNTIME.glob("*.json")}
out = run_cli("--only", ",".join(DEMO))
after = {p.name: p.read_text(encoding="utf-8") for p in store.RUNTIME.glob("*.json")}
expect("--yes 없으면 아무것도 안 지움", before == after)
expect("보기: messages 2건(섞인 1건)", "messages.json  2건 — 쪽지 대화(다른 계정과 섞인 대화 1건 포함)" in out)
expect("보기: noteVersions 노트 이름", "noteVersions.json  1건 — 노트 버전 +1(추천 다시 계산): N-marburg" in out)
expect("보기: askLog 건드리지 않음 표시", "askLog.json  건드리지 않음 — 사람 칸 없음" in out)
expect("보기: 관리자 파일 표시", "reportHtml.json  건드리지 않음 — 관리자 파일" in out)
expect("보기: 규칙에 없는 파일 표시", "mystery.json  건드리지 않음 — 규칙에 없는 파일" in out)
expect("보기: --yes 안내", "--yes" in out)
out = run_cli("--only", ",".join(DEMO), "--yes", "--dry")
expect("--dry가 있으면 --yes여도 보기만", before == {p.name: p.read_text(encoding="utf-8") for p in store.RUNTIME.glob("*.json")})

# ── 2. file: --yes ────────────────────────────────────────────────────
out = run_cli("--only", ",".join(DEMO), "--yes")
expect("--yes: 지웠다는 줄", "시연 계정 기록만 지웠어요" in out)
check_after(read, "file")
store._cache.clear()
out = run_cli("--only", ",".join(DEMO))
expect("두 번째 실행: 지울 기록 없음", "지울 기록 없음" in out)

# ── 3. file: --only 없이 --dry는 목록만, 그냥은 전부 지움(지금처럼) ──────────
seed_files()
out = run_cli("--dry")
expect("전부 --dry: 파일 수만", f"사라질 파일 {len(SEED)}개" in out and len(list(store.RUNTIME.glob('*.json'))) == len(SEED))
out = run_cli()
expect("--only 없이: 전부 지움", list(store.RUNTIME.glob("*.json")) == [])
try:
    run_cli("--only")
    expect("--only 빈 값이면 멈춤", False)
except SystemExit:
    expect("--only 빈 값이면 멈춤", True)

# ── 4. ncp: 가짜 버킷 + 저장 중 다른 컨테이너가 끼어들어도 그 기록을 지우지 않음 ──────
os.environ.update(STORE_BACKEND="ncp", NCP_OS_BUCKET="b", NCP_OS_ACCESS_KEY="a" * 8, NCP_OS_SECRET_KEY="s" * 8,
                  NCP_OS_PREFIX="runtime/")
bucket, etag, seq = {}, {}, [0]
intrude = {}


def fake_s3(method, key="", body=b"", query=None, extra=None):
    cond = {k.lower(): v for k, v in (extra or {}).items()}
    if method == "GET" and query:
        keys = "".join(f"<Key>{k}</Key>" for k in bucket if k.startswith(query.get("prefix", "")))
        return 200, f"<ListBucketResult>{keys}</ListBucketResult>".encode(), {}
    if method == "GET":
        return (200, bucket[key], {"etag": etag[key]}) if key in bucket else (404, b"", {})
    if method == "PUT":
        if key in intrude:                      # 저장 직전 다른 컨테이너가 새 대화를 씀
            seq[0] += 1
            bucket[key], etag[key] = intrude.pop(key), f'"i{seq[0]}"'
        cur = etag.get(key)
        if ("if-match" in cond and cond["if-match"] != cur) or ("if-none-match" in cond and cur is not None):
            return 412, b"", {}
        seq[0] += 1
        bucket[key], etag[key] = body, f'"v{seq[0]}"'
        return 200, b"", {}
    raise AssertionError(f"이 시험에서 {method}는 부르지 않아야 함")


store._s3 = fake_s3
for name, v in SEED.items():
    bucket[f"runtime/{name}.json"] = json.dumps(v, ensure_ascii=False).encode()
    etag[f"runtime/{name}.json"] = '"v0"'
bucket["runtime/sub/old.json"] = b"{}"          # 접두어 아래 폴더 — 목록에서 뺀다
store._cache.clear()
store._base.clear()
expect("ncp list_names: 하위 폴더 뺌", store.list_names() == sorted(SEED))
late = copy.deepcopy(SEED["messages"])
late["T-0004"] = {"asker": OTHER2, "senior": OTHER, "askerNickname": "늦은 사슴", "status": "waiting", "messages": []}
intrude["runtime/messages.json"] = json.dumps(late, ensure_ascii=False).encode()
before_bucket = dict(bucket)
run_cli("--ncp", "--only", ",".join(DEMO))
expect("ncp 보기만: 버킷 그대로", bucket == before_bucket)
store._cache.clear()
store._base.clear()
run_cli("--ncp", "--only", ",".join(DEMO), "--yes")


def nread(name):
    return json.loads(bucket[f"runtime/{name}.json"].decode("utf-8"))


m = nread("messages")
expect("ncp: 그사이 생긴 다른 계정 대화 T-0004 남음", "T-0004" in m)
nread_wo_late = lambda name: ({k: v for k, v in nread(name).items() if k != "T-0004"} if name == "messages" else nread(name))
check_after(nread_wo_late, "ncp")

# ── 5. 12/3 초기화 목록(시연 계정 + H0002·H0004, 11/26 결정 A): 시험 계정 기록도 지우고 나머지는 남김 ──────
TRY = ["H0002", "H0004"]
extra = copy.deepcopy(SEED)
for i, who in enumerate(TRY, 1):
    extra["questions"].append({"id": f"Q-009{i}", "colreg_no": who, "status": "hold"})
    extra["demands"].append({"id": f"R-009{i}", "owner": who, "detail": "1회성"})   # #376 전의 옛 유형 이름
    extra["noteLines"].append({"noteId": NX, "owner": who, "text": f"{who} 문장"})
    extra["tellChat"][f"{who}|마르부르크"] = {"owner": who}
new = {name: v for name, v, _, _ in rr.plan(DEMO + TRY, lambda n, d: copy.deepcopy(extra.get(n, d)))}
expect("12/3 목록: H0002·H0004 질문·옛 수요 기록 지움, 다른 계정 남음",
       [q["id"] for q in new["questions"]] == ["Q-0002"] and new["demands"] == [{"id": "R-0002", "owner": OTHER}])
expect("12/3 목록: H0002·H0004 공개 문장·대화형 판정 지움, 다른 계정 남음",
       [x["owner"] for x in new["noteLines"]] == [OTHER2, OTHER2] and list(new["tellChat"]) == [f"{OTHER2}|마르부르크"])

# ── 6. 서버 코드가 쓰는 runtime 이름은 모두 초기화 규칙(HANDLED)이나 남기는 목록(UNTOUCHED)에 있다 ──────
used, unknown = {"counters"}, []   # counters는 store.next_id가 쓴다
for path in sorted(Path(rr.__file__).parent.glob("*.py")):
    if path.name.startswith(("test_", "eval_", "check_")) or path.name in ("store.py", "reset_runtime.py"):
        continue
    src = path.read_text(encoding="utf-8")
    consts = dict(re.findall(r'^([A-Z_]+)\s*=\s*"(\w+)"', src, re.M))
    for arg in re.findall(r'\bstore\.(?:load|save)\(\s*([^,)\s]+)', src):
        name = arg[1:-1] if arg[0] in "\"'" else consts.get(arg)
        if name:
            used.add(name)
        else:
            unknown.append(f"{path.name}: {arg}")
expect(f"runtime 이름을 모두 읽어 냄 {unknown or ''}", not unknown)
missing = sorted(used - rr.HANDLED - set(rr.UNTOUCHED))
expect(f"초기화 규칙에 없는 runtime 기록 없음 {missing or ''}", not missing)

print("\n" + (f"FAIL {len(fails)}건" if fails else "모두 통과"))
sys.exit(1 if fails else 0)

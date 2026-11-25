# test_store_race.py — 컨테이너(Cloud Functions 인스턴스)가 둘일 때 쪽지 답장이 사라지지 않는지 (작업 58 ②, 11/25)
# 실행: cd functions && python -X utf8 test_store_race.py   하나라도 틀리면 종료코드 1. 네트워크·AI를 부르지 않는다.
#
# 11/25 두 창 시험: H0469(선배) 답장이 보였다가 새로고침 뒤 양쪽에서 사라짐. 화면이 몇 초마다 부르는 getMessages가
# 바뀐 게 없어도 messages를 통째로 저장했고, 다른 컨테이너의 늦게 끝난 읽기 요청이 옛 기록으로 덮어썼다.
# 고친 것: ① getMessages·recommendSeniors는 바뀐 게 있을 때만 저장  ② store(ncp).save는 다시 읽고 이번 요청의 변경만 얹음
#         ③ 그 쓰기는 다시 읽은 ETag를 If-Match(없던 기록은 If-None-Match: *)로 붙이고, 412면 다시 읽어 합치기를 3번까지(7절).
#
# 가짜 컨테이너: store._cache·_base를 컨테이너마다 다른 dict로 바꿔 끼운다(같은 가짜 버킷을 본다).
#   request(name)  그 컨테이너에서 새 요청 시작(begin_request → 버킷에서 새로 읽음)
#   resume(name)   아직 끝나지 않은 요청으로 돌아감(옛 캐시 그대로 = 늦게 끝나는 요청)
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"
os.environ.update(STORE_BACKEND="ncp", NCP_OS_BUCKET="b", NCP_OS_ACCESS_KEY="a" * 8, NCP_OS_SECRET_KEY="s" * 8)

bucket, puts = {}, []
etags = {}          # key → 지금 ETag(가짜: 쓸 때마다 다른 값). NCP처럼 If-Match가 어긋나면 412, If-None-Match: *인데 있으면 412
intruders = {}      # key → body: 그 key에 PUT하기 직전에 다른 컨테이너가 끼어들어 쓴 것처럼(한 번만. always면 매번)
always_intrude = set()
put_log = []        # (key, 상태 코드, 조건 헤더 이름) — 모든 PUT
_seq = [0]


def _intrude(key, body):
    _seq[0] += 1
    bucket[key], etags[key] = body, f'"intruder-{_seq[0]}"'


def fake_s3(method, key="", body=b"", query=None, extra=None):
    cond = {k.lower(): v for k, v in (extra or {}).items()}
    if method == "GET" and query:
        keys = "".join(f"<Key>{k}</Key>" for k in bucket if k.startswith(query.get("prefix", "")))
        return 200, f"<ListBucketResult>{keys}</ListBucketResult>".encode(), {}
    if method == "GET":
        return (200, bucket[key], {"etag": etags[key]}) if key in bucket else (404, b"", {})
    if method == "PUT":
        if key in intruders:
            _intrude(key, intruders[key] if key in always_intrude else intruders.pop(key))
        cur = etags.get(key)
        if ("if-match" in cond and cond["if-match"] != cur) or ("if-none-match" in cond and cur is not None):
            put_log.append((key, 412, sorted(cond)))
            return 412, b"", {}
        _seq[0] += 1
        bucket[key], etags[key] = body, f'"v{_seq[0]}"'
        puts.append(key)
        put_log.append((key, 200, sorted(cond)))
        return 200, b"", {"etag": etags[key]}
    if method == "DELETE":
        bucket.pop(key, None)
        etags.pop(key, None)
        return 204, b"", {}


store._s3 = fake_s3

import runtime_fns as rf  # noqa: E402
from runtime_fns import getMessages, recommendSeniors, respondRequest, sendMessage  # noqa: E402

JUNIOR, SENIOR1 = "H0143", "H0469"
JUNIOR2, SENIOR2 = "H0995", "H0745"
MARBURG = "N-marburg"
HELLO = "안녕하세요, 마르부르크 파견 준비가 궁금해서 쪽지 드려요."
REPLY = "반가워요! 무엇이든 물어보세요."
fails = []

clock = [datetime(2026, 11, 25, 10, 0, tzinfo=rf.KST)]
rf.now = lambda: clock[0].isoformat(timespec="seconds")


def later(seconds=1):
    clock[0] += timedelta(seconds=seconds)


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


containers = {}


def resume(name):
    store._cache, store._base = containers.setdefault(name, ({}, {}))


def request(name):
    resume(name)
    store.begin_request()


def in_bucket(name):
    raw = bucket.get(f"runtime/{name}.json")
    return json.loads(raw) if raw else None


def thread_in_bucket(tid):
    return (in_bucket("messages") or {}).get(tid)


def msg_puts():
    return sum(1 for k in puts if k == "runtime/messages.json")


# ── 0. 준비: 요청 → 수락 (한 컨테이너에서) ──────────────────────────────
request("A")
store.load("demands", []).extend({"id": f"R-{h}", "owner": h} for h in (JUNIOR, JUNIOR2))   # 수요 인터뷰를 마친 것처럼
store.save("demands")
tid = sendMessage(JUNIOR, {"to": SENIOR1, "text": HELLO})["threadId"]
later()
request("A")
expect("준비: 수락", respondRequest(SENIOR1, {"threadId": tid, "accept": True})["status"] == "accepted")
getMessages(JUNIOR, {})          # 선배 글자(nicknames)를 미리 정해 둔다
later()

# ── 1. 핵심 장면: 늦게 끝나는 getMessages(목록)가 다른 컨테이너의 답장을 덮어쓰지 않음 ──
request("A")                      # 후배 화면의 주기 호출이 먼저 읽기 시작
store.load("messages", {})
request("B")                      # 그사이 선배가 답장(다른 컨테이너)
expect("B: 선배 답장 저장", sendMessage(SENIOR1, {"to": JUNIOR, "text": REPLY})["ok"])
expect("B: 버킷에 답장", any(m["text"] == REPLY for m in thread_in_bucket(tid)["messages"]))
before = msg_puts()
resume("A")                       # A가 옛 캐시로 마무리
m = getMessages(JUNIOR, {})
expect("A(옛 캐시) 목록 응답은 아직 답장 없음(이 요청은 옛 기록을 봄)", not any(x["text"] == REPLY for x in next(t for t in m["threads"] if t["threadId"] == tid)["messages"]))
expect("① 목록만 보는 getMessages는 저장하지 않음", msg_puts() == before)
request("C")
expect("새 요청: 답장이 남아 있음", any(x["text"] == REPLY for x in next(t for t in getMessages(JUNIOR, {})["threads"] if t["threadId"] == tid)["messages"]))
expect("새 요청: 선배 쪽에서도 답장이 남아 있음", any(x["text"] == REPLY for x in next(t for t in getMessages(SENIOR1, {})["threads"] if t["threadId"] == tid)["messages"]))

# ── 2. 같은 대화: 늦게 끝나는 getMessages(read)가 저장해도 합쳐져서 답장이 남음 ──
later()
request("A")
store.load("messages", {})        # 후배가 대화창을 여는 요청이 먼저 읽음
request("B")
later()
expect("B: 선배 두 번째 답장", sendMessage(SENIOR1, {"to": JUNIOR, "text": REPLY + " 2"})["ok"])
later()
resume("A")
read_at = rf.now()
getMessages(JUNIOR, {"read": tid})
t = thread_in_bucket(tid)
expect("② A(read) 저장 뒤 버킷에 두 답장 모두", [x["text"] for x in t["messages"]][-2:] == [REPLY, REPLY + " 2"])
expect("② A의 읽음 표시도 들어감", t["lastRead"].get(JUNIOR) == read_at)
request("C")
mine = next(x for x in getMessages(JUNIOR, {})["threads"] if x["threadId"] == tid)
expect("새 요청: 메시지 3개(요청 + 답장 2)", len(mine["messages"]) == 3)

# ── 3. 새 요청 둘이 겹침(다른 컨테이너·옛 counters): 번호가 겹치지 않고 둘 다 남음 ──
request("A")
store.load("messages", {})
store.load("counters", {})
request("B")
store.load("messages", {})
store.load("counters", {})
resume("A")
a = sendMessage(JUNIOR, {"to": SENIOR2, "text": HELLO})
resume("B")
b = sendMessage(JUNIOR2, {"to": SENIOR1, "text": HELLO})
expect("둘 다 성공, threadId가 다름", a["ok"] and b["ok"] and a["threadId"] != b["threadId"])
request("C")
all_tids = set(store.load("messages", {}))
expect("버킷에 세 대화 모두", {tid, a["threadId"], b["threadId"]} <= all_tids and len(all_tids) == 3)
expect("counters는 3", store.load("counters", {})["T"] == 3)

# ── 4. 저장하지 않는 읽기: recommendSeniors 목록이 그대로면 PUT 없음 ──
request("A")
recommendSeniors(JUNIOR, {"noteId": MARBURG})
n = puts.count("runtime/shownSeniors.json")
request("A")
r = recommendSeniors(JUNIOR, {"noteId": MARBURG})
expect("① 같은 목록이면 shownSeniors 저장 없음", puts.count("runtime/shownSeniors.json") == n and r["shown"] >= 1)
request("A")
recommendSeniors(JUNIOR, {"noteId": MARBURG, "more": True})
expect("더 보기(목록 바뀜)는 저장", puts.count("runtime/shownSeniors.json") == n + 1)

# ── 5. _merge 규칙 ──────────────────────────────────────────────────────
M = store._MISSING
mg = store._merge
expect("내가 안 바꾸면 저쪽 것", mg({"a": 1}, {"a": 1}, {"a": 2}) == {"a": 2})
expect("저쪽이 안 바꾸면 내 것", mg({"a": 1}, {"a": 2}, {"a": 1}) == {"a": 2})
expect("dict: 서로 다른 키", mg({"a": 1}, {"a": 1, "b": 2}, {"a": 1, "c": 3}) == {"a": 1, "b": 2, "c": 3})
expect("dict: 내가 지운 키, 저쪽은 그대로 → 지움", mg({"a": 1, "b": 2}, {"a": 1}, {"a": 1, "b": 2}) == {"a": 1})
expect("dict: 내가 지운 키, 저쪽이 고침 → 저쪽 것", mg({"a": 1, "b": 2}, {"a": 1}, {"a": 1, "b": 9}) == {"a": 1, "b": 9})
expect("dict: 저쪽이 지운 키, 나는 그대로 → 지움", mg({"a": 1, "b": 2}, {"a": 1, "b": 2}, {"a": 1}) == {"a": 1})
expect("list: 양쪽이 덧붙임 → 저쪽 것 뒤에 내 것", mg([1], [1, 2], [1, 3]) == [1, 3, 2])
expect("list: 저쪽이 줄였고 나는 고침 → 내 것", mg([1, 2], [1, 2, 3], [1]) == [1, 2, 3])
expect("정수: 더한 만큼", mg({"T": 3}, {"T": 4}, {"T": 5}) == {"T": 6})
expect("정수: 둘 다 처음 만듦", mg({}, {"T": 1}, {"T": 1}) == {"T": 2})
expect("문자열 충돌은 내 것", mg({"s": "a"}, {"s": "b"}, {"s": "c"}) == {"s": "b"})
expect("bool은 더하지 않음", mg({"x": False}, {"x": True}, {"x": True}) == {"x": True})
expect("없던 기록을 양쪽이 만듦", mg(M, {"a": 1}, {"b": 2}) == {"a": 1, "b": 2})

# ── 6. next_id: 옛 counters로 뽑아도 저쪽이 뽑은 번호를 건너뜀 ──
request("A")
store.load("counters", {})
request("B")
expect("B가 먼저 Q-0001", store.next_id("Q") == "Q-0001")
resume("A")
expect("A는 합친 뒤 Q-0002", store.next_id("Q") == "Q-0002")

# ── 7. 조건부 쓰기(If-Match): 다시 읽기와 쓰기 사이에 끼어든 쓰기 → 412 → 다시 읽어 합쳐 둘 다 남음 ──
PK = "runtime/probe.json"
request("A")
probe = store.load("probe", {})           # 없던 기록
probe["mine"] = 1
intruders[PK] = json.dumps({"theirs": 2}).encode()   # 첫 PUT 직전에 다른 컨테이너가 같은 기록을 만듦
n0 = len(put_log)
store.save("probe")
log = [(s, c) for k, s, c in put_log[n0:] if k == PK]
expect("새 기록: 첫 PUT은 If-None-Match:* → 412, 다시 읽어 If-Match로 200", log == [(412, ["if-none-match"]), (200, ["if-match"])])
expect("버킷에 둘 다 남음", in_bucket("probe") == {"mine": 1, "theirs": 2})
expect("요청이 들고 있는 dict도 합친 모습", probe == {"mine": 1, "theirs": 2} and store.load("probe", {}) is probe)

request("A")
probe = store.load("probe", {})           # 있는 기록(ETag 있음)
probe["mine"] = 5
intruders[PK] = json.dumps({"mine": 1, "theirs": 2, "late": 3}).encode()
n0 = len(put_log)
store.save("probe")
log = [(s, c) for k, s, c in put_log[n0:] if k == PK]
expect("있는 기록: If-Match 어긋남 → 412 → 다시 합쳐 200", log == [(412, ["if-match"]), (200, ["if-match"])])
expect("내 변경(mine=5)과 끼어든 변경(late) 둘 다", in_bucket("probe") == {"mine": 5, "theirs": 2, "late": 3})

request("A")
probe = store.load("probe", {})
probe["mine"] = 9
intruders[PK] = json.dumps({"mine": 5, "theirs": 2, "late": 4}).encode()
always_intrude.add(PK)                    # 매번 끼어듦 → 재시도를 다 써도 412
n0 = len(put_log)
try:
    store.save("probe")
    expect("재시도 초과 → RuntimeError", False)
except RuntimeError as e:
    expect("재시도 초과 → RuntimeError", "저장 충돌" in str(e))
expect(f"PUT은 1 + 재시도 {store.RETRIES}번 = {store.RETRIES + 1}번, 모두 412",
       [s for k, s, c in put_log[n0:] if k == PK] == [412] * (store.RETRIES + 1))
expect("실패한 요청의 변경은 캐시에 그대로(mine=9), _base는 안 바뀜", probe["mine"] == 9 and store._base["probe"]["mine"] == 5)
always_intrude.discard(PK)
intruders.pop(PK, None)
store.save("probe")                       # 끼어들기가 멎으면 같은 요청이 다시 저장할 수 있음
expect("다시 저장하면 내 변경 + 끼어든 변경 모두", in_bucket("probe") == {"mine": 9, "theirs": 2, "late": 4})

# ── 7-2. 바뀐 것이 없으면 save는 GET·PUT 0회 ──
request("A")
probe = store.load("probe", {})
calls = []
_orig_s3 = store._s3
store._s3 = lambda *a, **k: (calls.append(a[0]), _orig_s3(*a, **k))[1]
store.save("probe")
expect("바뀐 것 없음 → save는 GET·PUT 0회", calls == [])
probe["mine"] = probe.get("mine", 0) + 1
store.save("probe")
expect("바뀐 것 있으면 GET 1 + PUT 1", calls == ["GET", "PUT"])
store._s3 = _orig_s3

expect("모든 PUT에 조건 헤더(If-Match 또는 If-None-Match)", all(c in (["if-match"], ["if-none-match"]) for k, s, c in put_log))

# ── 8. file 방식은 그대로(스냅샷 없이 바로 씀) ───────────────────────────
os.environ["STORE_BACKEND"] = "file"
store._cache, store._base = {}, {}
store.load("x", {"a": 1})["b"] = 2
store.save("x")
expect("file: 저장 파일 그대로", json.loads((store.RUNTIME / "x.json").read_text(encoding="utf-8")) == {"a": 1, "b": 2})
expect("file: _base를 쓰지 않음", store._base == {})

print()
if fails:
    print(f"틀림 {len(fails)}건")
    sys.exit(1)
print("모두 통과")

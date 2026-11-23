# runtime_fns.py — 쓰기 저장소를 쓰는 서버 함수 (작업 51)
# 응답 모양은 docs/spec-v1.md 4장. 저장은 store.py만 거친다. AI 없음.
#
# 모든 함수 모양: 함수(me, payload) -> dict
#   me = 요청 헤더 X-Token을 sessions.resolve()로 바꾼 colreg_no (local_fn.py가 넣어 준다)
#
# 다른 작업에서 쓰라고 열어 둔 도우미:
#   add_question(me, text, ...)    — askBoo가 hold일 때 질문함에 넣기(작업 18)
#   save_my_note(me, ...)          — summarizeInterview가 내 경험노트를 저장할 때(작업 21)
#   senior_label(viewer, senior)   — recommendSeniors 카드 이름(작업 22). 쪽지창과 같은 값
# saveConsent → publish_lines: 동의 통과 문장을 noteLines에 쌓고, 후배 질문 답이면 질문 answered + 질문자 알림(작업 74).
# 노트 읽기(getNote·listNotes)와 askBoo 근거 풀은 notes.py.
# 내 경험노트(11/22): getInbox.myNotes 카드(share·filled/total·sharedLines)와 getMyNote(id) 상세는 _my_note_view 하나로 계산.
# 쪽지 규칙(11/18·11/20, spec 4장 sendMessage, 작업 85): 선배당 요청 1건 · 보낸 사람 수락 대기 3건 · 받는 선배 5건 ·
#   요청 취소(7일 재요청 금지) · 7일 자동 만료. status = waiting | accepted | declined | cancelled | expired | blocked
# 쪽지 신고·차단(11/23, reportThread): 신고는 threadReports.json에 남고, 차단하면 그 두 사람 사이 대화는 양쪽 다 더 못 보낸다.
#   상대에게 알리지 않는다. 차단 풀기는 P1.
# 선배 추천 열림(11/22, demand.py): 경험 나눔(답변 3 + 1문장 공유) 또는 수요 제공(궁금한 것 정리하기) 전에는
#   recommendSeniors·previewNickname·sendMessage(새 요청)가 {locked} / reason "잠김"으로 막는다. 받은 선배의 답장은 막지 않는다.
# recommendSeniors(작업 85): 점수는 score.py(원우), 목록 보관·더 보기·재계산은 여기(spec 4장 인원 규칙).
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import demand
import notes
import score
import store
from msg_check import check_message, check_public_text

KST = timezone(timedelta(hours=9))
DATA = Path(__file__).resolve().parent.parent / "data"

WAIT_LIMIT = 3               # 보낸 사람의 수락 대기 요청 한도
RECEIVE_LIMIT = score.REQUEST_LIMIT   # 받는 선배의 수락 대기 요청 한도(5) — score.py의 requestsFull과 같은 값
EXPIRE_DAYS = 7              # 보낸 뒤 이 기간 안에 답이 없으면 expired
COOLDOWN_DAYS = 7            # 취소한 선배에게 다시 요청하지 못하는 기간
PAGE, MAX_SHOWN = 3, 9       # 닮은선배: 처음 3명, 더 보기마다 3명, 한 번에 보이는 목록 최대 9명
EXPIRED_ALERT = "선배가 아직 못 봤어요. 다른 선배에게 보내 볼까요?"
REQUEST_ALERT = "쪽지 요청이 왔어요"
BLOCKED_MESSAGE = "더 이어 갈 수 없는 대화예요"
REASON_MAX = 100             # 신고 사유 글자 수 상한(화면은 고르기 + 기타)

ADJECTIVES = ["용감한", "조용한", "느긋한", "다정한", "씩씩한", "궁금한", "반짝이는", "부지런한",
              "차분한", "명랑한", "수줍은", "든든한", "포근한", "재빠른", "꼼꼼한", "따뜻한"]
ANIMALS = ["수달", "고래", "다람쥐", "펭귄", "여우", "부엉이", "판다", "고슴도치",
           "해달", "토끼", "거북이", "사슴", "참새", "돌고래", "너구리", "알파카"]


def now():
    return datetime.now(KST).isoformat(timespec="seconds")


# ---------- 학생 정보 (원우의 data/students.json, 없으면 빈 값으로 동작) ----------
_students = None


def student(colreg_no):
    global _students
    if _students is None:
        try:
            rows = json.loads((DATA / "students.json").read_text(encoding="utf-8"))
            _students = {r.get("colreg_no"): r for r in rows if isinstance(r, dict)}
        except (OSError, ValueError):
            _students = {}
    return _students.get(colreg_no, {})


# ---------- 이름 규칙 (spec 0장) ----------
def senior_label(viewer, senior):
    """보는 사람 기준 '독일어과 선배 A'. 처음 만난 순서대로 A, B, C… 한 번 정하면 그대로."""
    with store.lock():
        table = store.load("nicknames", {})
        mine = table.setdefault(viewer, {})
        if senior not in mine:
            mine[senior] = _letter(len(mine))
            store.save("nicknames")
        dept = student(senior).get("crs_nm", "")
        return f"{dept} 선배 {mine[senior]}".strip()


def _letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _new_animal_name(senior):
    """같은 선배가 받은 다른 대화와 겹치지 않는 '형용사 + 동물'."""
    used = {t["askerNickname"] for t in store.load("messages", {}).values() if t["senior"] == senior}
    used |= {v for (s, _), v in _pending_names().items() if s == senior}
    choices = [f"{a} {b}" for a in ADJECTIVES for b in ANIMALS if f"{a} {b}" not in used]
    return random.choice(choices)


def _pending_names():
    raw = store.load("pendingNicknames", {})     # "선배|보낸사람" -> 미리 정한 이름
    return {tuple(k.split("|")): v for k, v in raw.items()}


def _find_thread(asker, senior):
    for tid, t in _threads().items():
        if t["asker"] == asker and t["senior"] == senior:
            return tid, t
    return None, None


def _threads():
    """messages.json. 11/20 이전 기록의 status "requested"는 "waiting"으로 읽는다."""
    threads = store.load("messages", {})
    for t in threads.values():
        if t.get("status") == "requested":
            t["status"] = "waiting"
        t.setdefault("requestedAt", t.get("createdAt"))
    return threads


def _days_since(iso):
    try:
        return (datetime.fromisoformat(now()) - datetime.fromisoformat(iso)).total_seconds() / 86400
    except (TypeError, ValueError):
        return 0


def _expire_old():
    """보낸 뒤 7일 동안 답이 없는 요청을 expired로(스케줄러 없이 호출할 때 판정, spec 4장)."""
    changed = False
    for tid, t in _threads().items():
        if t["status"] == "waiting" and _days_since(t["requestedAt"]) >= EXPIRE_DAYS:
            t.update(status="expired", expiredAt=now())
            _drop_request_alert(t["senior"], tid)
            _alert(t["asker"], EXPIRED_ALERT, threadId=tid)
            changed = True
    if changed:
        store.save("messages")


def _waiting(asker=None, senior=None):
    return sum(1 for t in _threads().values() if t["status"] == "waiting"
               and (asker is None or t["asker"] == asker) and (senior is None or t["senior"] == senior))


def _limit_error(me, to):
    if _waiting(asker=me) >= WAIT_LIMIT:
        return {"ok": False, "reason": "한도",
                "message": "답을 기다리는 쪽지가 3건이에요. 기다리는 요청을 취소하거나 선배가 답하면 더 보낼 수 있어요."}
    if _waiting(senior=to) >= RECEIVE_LIMIT:
        return {"ok": False, "reason": "선배한도",
                "message": "지금은 이 선배에게 요청이 많아요. 질문함에 남기면 선배 인터뷰 때 함께 물어볼게요."}
    return None


def _drop_request_alert(senior, tid):
    """취소·만료된 요청은 선배 화면에서 조용히 사라진다(알림도 지운다)."""
    alerts = store.load("alerts", {})
    mine = alerts.get(senior, [])
    kept = [a for a in mine if not (a.get("threadId") == tid and a.get("text") == REQUEST_ALERT)]
    if len(kept) != len(mine):
        alerts[senior] = kept
        store.save("alerts")


def _alert(to, text, **extra):
    alerts = store.load("alerts", {})
    alerts.setdefault(to, []).append({"text": text, "at": now(), **extra})
    store.save("alerts")


# ---------- 쪽지 ----------
def checkMessage(me, p):
    """학번·연락처·금지어는 코드 규칙(msg_check.py, 작업 27)이 막는다. 메일은 허용.
    비방 AI 판정(P1, callAI("쪽지검사"))은 이 규칙을 통과한 쪽지에만 이어서 붙인다."""
    return check_message(p.get("text", ""))


def previewNickname(me, p):
    to = p.get("to")
    if not to:
        return {"error": "받는 선배가 없어요"}
    with store.lock():
        _, t = _find_thread(me, to)
        if t:
            return {"myNickname": t["askerNickname"]}
        lk = demand.locked(me)
        if lk:
            return lk
        raw = store.load("pendingNicknames", {})
        key = f"{to}|{me}"
        if key not in raw:
            raw[key] = _new_animal_name(to)
            store.save("pendingNicknames")
        return {"myNickname": raw[key]}


def sendMessage(me, p):
    to, text = p.get("to"), (p.get("text") or "").strip()
    if not to or not text:
        return {"error": "받는 사람과 내용을 확인해 주세요"}
    if to == me:
        return {"error": "나에게는 쪽지를 보낼 수 없어요"}
    check = checkMessage(me, {"text": text})
    if not check["ok"]:
        return {"ok": False, **check}

    with store.lock():
        threads = _threads()
        _expire_old()
        # 받은 선배가 답하는 경우가 먼저(취소·만료된 요청은 선배 쪽에서 없는 대화), 아니면 내가 보낸 대화
        tid, t = _find_thread(to, me)
        if t and t["status"] in ("cancelled", "expired"):
            tid, t = None, None
        if t:
            if t["status"] == "waiting":
                return {"ok": False, "reason": "상태", "message": "쪽지 요청을 먼저 수락해 주세요"}
            if t["status"] == "declined":
                return {"ok": False, "reason": "상태", "message": "받지 않은 요청이에요"}
        else:
            tid, t = _find_thread(me, to)
        if t and t["status"] == "blocked":               # 누가 차단했든 그 두 사람 사이는 막힌다(11/23)
            return {"ok": False, "reason": "차단", "message": BLOCKED_MESSAGE}

        if t is None:                                   # 첫 메시지 = 쪽지 요청
            lk = demand.locked(me)
            if lk:
                return {"ok": False, "reason": "잠김", "message": lk["message"], "recommend": lk["recommend"]}
            err = _limit_error(me, to)
            if err:
                return err
            nickname = previewNickname(me, {"to": to})["myNickname"]
            store.load("pendingNicknames", {}).pop(f"{to}|{me}", None)
            store.save("pendingNicknames")
            tid = store.next_id("T")
            t = threads[tid] = {"asker": me, "senior": to, "askerNickname": nickname, "status": "waiting",
                                "createdAt": now(), "requestedAt": now(), "messages": [], "lastRead": {}}
            _alert(to, REQUEST_ALERT, threadId=tid)
        elif t["status"] == "declined":
            return {"ok": False, "reason": "상태", "message": "선배가 이 요청을 받지 않았어요"}
        elif t["status"] in ("cancelled", "expired"):    # 같은 선배에게 다시 요청 = 같은 대화를 다시 연다
            if t["status"] == "cancelled" and _days_since(t.get("cancelledAt")) < COOLDOWN_DAYS:
                return {"ok": False, "reason": "취소",
                        "message": "요청을 취소한 선배에게는 7일 뒤에 다시 보낼 수 있어요."}
            lk = demand.locked(me)
            if lk:
                return {"ok": False, "reason": "잠김", "message": lk["message"], "recommend": lk["recommend"]}
            err = _limit_error(me, to)
            if err:
                return err
            t.update(status="waiting", requestedAt=now())
            _alert(to, REQUEST_ALERT, threadId=tid)
        # waiting(내가 보낸 요청에 덧붙이기)·accepted는 그대로 이어 쓴다 — 선배 한 명당 요청 1건

        at = now()
        t["messages"].append({"from": me, "text": text, "at": at})
        t["lastRead"][me] = at
        store.save("messages")
        out = {"ok": True, "threadId": tid, "at": at}
        if t["asker"] == me:
            out["myNickname"] = t["askerNickname"]
        return out


def getMessages(me, p):
    """내 대화 목록. 부르면 안 읽은 메시지를 읽음으로 바꾼다(unread는 이번 응답에만 보임)."""
    with store.lock():
        out = []
        threads = _threads()
        _expire_old()
        for tid, t in sorted(threads.items(), key=lambda kv: kv[1]["requestedAt"], reverse=True):
            if me not in (t["asker"], t["senior"]):
                continue
            role = "asker" if t["asker"] == me else "senior"
            if role == "senior" and t["status"] in ("cancelled", "expired"):
                continue                                 # 선배 목록에서는 조용히 사라진다
            other = t["senior"] if role == "asker" else t["asker"]
            last = t["lastRead"].get(me, "")
            item = {
                "threadId": tid, "role": role, "withId": other,
                "nickname": senior_label(me, other) if role == "asker" else t["askerNickname"],
                "status": t["status"], "requestedAt": t["requestedAt"],
                "accepted": t["status"] == "accepted",   # 옛 필드(화면 호환). 새 화면은 status를 쓴다
                "unread": sum(1 for m in t["messages"] if m["from"] != me and m["at"] > last),
                "messages": [{"from": "me" if m["from"] == me else "them", "text": m["text"], "at": m["at"]}
                             for m in t["messages"]],
            }
            if role == "asker":
                item["myNickname"] = t["askerNickname"]
            else:
                item["askerInfo"] = _asker_info(t["asker"])
            if t["status"] == "declined":
                item["declined"] = True
            if t["status"] == "blocked":
                item["blockedByMe"] = t.get("blockedBy") == me
            t["lastRead"][me] = now()
            out.append(item)
        store.save("messages")
        return {"threads": out, "waitingCount": _waiting(asker=me), "waitingLimit": WAIT_LIMIT}


def _asker_info(asker):
    """선배에게 보여 줄 보낸 사람 정보: 학년 + 관심(「교환학생·독일」, 최대 2) + 시기(수요 인터뷰에서 고른 것).
    학과·상황 답변 원문은 넣지 않는다(11/22, demand.py)."""
    info = {"학년": student(asker).get("regst_grad"), "관심": demand.interest_labels(asker)}
    when = demand.latest_when(asker)
    if when:
        info["시기"] = when
    return info


def respondRequest(me, p):
    """선배의 수락·거절 {threadId, accept} 또는 보낸 사람의 요청 취소 {threadId, cancel: true}."""
    tid = p.get("threadId")
    with store.lock():
        _expire_old()
        t = _threads().get(tid)
        if p.get("cancel"):
            if not t or t["asker"] != me:
                return {"error": "볼 수 없는 기록이에요"}
            if t["status"] != "waiting":
                return {"ok": False, "reason": "상태", "status": t["status"]}
            t.update(status="cancelled", cancelledAt=now())
            store.save("messages")
            _drop_request_alert(t["senior"], tid)        # 선배에게 알리지 않는다
            return {"ok": True, "status": "cancelled"}
        if not t or t["senior"] != me or t["status"] in ("cancelled", "expired"):
            return {"error": "볼 수 없는 기록이에요"}
        if t["status"] != "waiting":
            return {"ok": False, "reason": "상태", "status": t["status"]}
        accept = bool(p.get("accept"))
        t["status"] = "accepted" if accept else "declined"
        store.save("messages")
        label = senior_label(t["asker"], me)
        _alert(t["asker"], f"쪽지 요청이 수락됐어요 · {label}" if accept else f"이번 쪽지 요청은 연결되지 않았어요 · {label}",
               threadId=tid)
        return {"ok": True, "status": t["status"], "accepted": accept}


def reportThread(me, p):
    """쪽지 대화 신고·차단 {threadId, reason?, block?} (11/23, 작업 28 ⋮ 메뉴).
    reason이 있으면 신고 기록(threadReports.json), block이면 status blocked — 양쪽 모두 더 보낼 수 없다.
    상대에게 알리지 않는다. 대화의 asker·senior만 부를 수 있다(선배 목록에서 사라진 취소·만료 요청은 선배가 못 부름)."""
    tid = p.get("threadId")
    reason = str(p.get("reason") or "").strip()[:REASON_MAX]
    block = bool(p.get("block"))
    if not reason and not block:
        return {"error": "신고 사유를 골라 주세요"}
    with store.lock():
        _expire_old()
        t = _threads().get(tid)
        if not t or me not in (t["asker"], t["senior"]) or                 (me == t["senior"] and t["status"] in ("cancelled", "expired")):
            return {"error": "볼 수 없는 기록이에요"}
        if reason:
            store.load("threadReports", []).append({
                "threadId": tid, "by": me, "role": "asker" if t["asker"] == me else "senior",
                "reason": reason, "block": block, "at": now()})
            store.save("threadReports")
        if block and t["status"] != "blocked":
            if t["status"] == "waiting":
                _drop_request_alert(t["senior"], tid)
            t.update(status="blocked", blockedBy=me, blockedAt=now(), statusBeforeBlock=t["status"])
            store.save("messages")
        return {"ok": True, "reported": bool(reason), "blocked": t["status"] == "blocked", "status": t["status"]}


# ---------- 닮은선배 (spec 4장 recommendSeniors, 작업 85) ----------
def _program_of(note_id):
    """noteId → 프로그램 이름. notes.json이 생기기 전 방식(noteId = 프로그램 이름)도 받는다."""
    n = notes.NOTES.get(note_id)
    if n and n.get("program"):
        return n["program"]
    for program, nid in notes.FIXED_IDS.items():
        if nid == note_id:
            return program
    return note_id


def note_version(nid):
    return store.load("noteVersions", {}).get(nid, 0)


def recommendSeniors(me, p):
    """처음 3명, more면 3명씩 더해 최대 9명. 목록은 shownSeniors.json에 노트 버전과 함께 보관하고
    노트 버전이 바뀌었을 때(saveConsent)만 다시 계산한다. 학기·프로필 변경 재계산은 P1(아직 없음)."""
    note_id = p.get("noteId")
    if not note_id:
        return {"error": "노트를 골라 주세요"}
    lk = demand.locked(me)          # 경험 나눔·수요 제공 전에는 잠김(11/22)
    if lk:
        return lk
    program = _program_of(note_id)
    nid = notes.note_id(program)
    with store.lock():
        _expire_old()
        waiting = {}
        for t in _threads().values():
            if t["status"] == "waiting":
                waiting[t["senior"]] = waiting.get(t["senior"], 0) + 1
        ranked = score.rank_seniors(me, program, waiting=waiting)
        by_id = {r["studentId"]: r for r in ranked}
        cap = min(MAX_SHOWN, len(ranked))

        shown = store.load("shownSeniors", {})
        saved = shown.setdefault(me, {}).get(nid)
        version = note_version(nid)
        new_count = 0
        if saved is None:
            ids = [r["studentId"] for r in ranked[:PAGE]]
        elif saved.get("version") != version:            # 새 경험이 공유됨 → 같은 크기로 다시 계산
            size = max(PAGE, len(saved["ids"]))
            ids = [r["studentId"] for r in ranked[:size]]
            new_count = len(set(ids) - set(saved["ids"]))
        else:                                            # 저장된 목록 그대로(사라진 후보만 뺀다)
            ids = [h for h in saved["ids"] if h in by_id]
        if p.get("more"):
            rest = [r["studentId"] for r in ranked if r["studentId"] not in ids]
            ids += rest[:max(0, min(PAGE, cap - len(ids)))]
        ids = ids[:MAX_SHOWN]
        shown[me][nid] = {"ids": ids, "version": version, "at": now()}
        store.save("shownSeniors")

        seniors = [{"studentId": h, "nickname": senior_label(me, h), "score": by_id[h]["score"],
                    "requestsFull": by_id[h]["requestsFull"], "reasons": by_id[h]["reasons"]} for h in ids]
        return {"seniors": seniors, "shown": len(seniors), "hasMore": len(ids) < cap, "newCount": new_count}


# ---------- 질문함·내 경험노트·동의·신고 ----------
def add_question(me, text, program=None, section=None, status="hold", note_id=None):
    """askBoo(작업 18)가 부른다. 모양은 사용 로그 질문 행과 같게(PRD 6-3) → 콘솔 집계에 합산."""
    with store.lock():
        qid = store.next_id("Q")
        s = student(me)
        store.load("questions", []).append({
            "id": qid, "at": now(), "colreg_no": me, "crs_nm": s.get("crs_nm"), "regst_grad": s.get("regst_grad"),
            "프로그램명": program, "칸": section, "status": status, "질문": text, "noteId": note_id,
            "운영부서코드": None,   # 작업 66에서 programs.json으로 채움
        })
        store.save("questions")
        return qid


def save_my_note(me, program, draft_id, my_note, public_draft, answered=0):
    """summarizeInterview(작업 21)가 부른다. 같은 사람·같은 프로그램이면 같은 myNoteId를 갱신.
    answered = 이번 인터뷰의 유효 답변 수(demand.count_interview_answers) — 이어 쓰면 큰 값을 남긴다(추천 열림)."""
    with store.lock():
        notes = store.load("myNotes", {})
        mid = next((k for k, v in notes.items() if v["owner"] == me and v["program"] == program), None)
        mid = mid or store.next_id("M")
        old = notes.get(mid, {})
        notes[mid] = {"owner": me, "program": program, "draftId": draft_id, "myNote": my_note,
                      "publicDraft": public_draft, "share": old.get("share", "private"), "updatedAt": now(),
                      "answered": max(int(old.get("answered", 0)), int(answered))}
        store.save("myNotes")
        return mid


def saveConsent(me, p):
    if not p.get("consent"):
        return {"error": "공개 동의가 필요해요"}
    draft_id = p.get("draftId")
    edits = p.get("edits") or {}
    removed = set(edits.get("removed") or [])
    # 선배가 고친 문장은 해봤노트에 실리기 전에 다시 검사한다(msg_check.check_public_text, 작업 27).
    # 걸린 문장만 공개에서 빼고(removed에 더함) 나머지는 그대로 저장한다. 내 경험노트에는 남는다.
    changed, rejected = [], []
    for ch in edits.get("changed") or []:
        r = check_public_text(ch.get("text", ""))
        if r["ok"]:
            changed.append({"lineId": ch.get("lineId"), "text": ch.get("text", ""),
                            "identifying": r["identifying"], "official": r["official"]})
        else:
            removed.add(ch.get("lineId"))
            rejected.append({"lineId": ch.get("lineId"), "reason": r["reasons"][0], "message": r["message"]})
    ready_before = demand.recommend_status(me)["ready"]
    with store.lock():
        mid, note = next(((k, v) for k, v in store.load("myNotes", {}).items()
                          if v["owner"] == me and v["draftId"] == draft_id), (None, None))
        if note is None:   # 남의 초안이거나 없는 초안(spec 2-1)
            return {"error": "볼 수 없는 기록이에요"}
        new_text = {c["lineId"]: c for c in changed}
        passing = []
        for sec in note.get("publicDraft", {}).get("sections", []):
            for ln in sec.get("lines", []):
                if ln.get("lineId") in removed:
                    continue
                c = new_text.get(ln.get("lineId"))
                passing.append({"section": sec.get("name"), "draftLineId": ln.get("lineId"),
                                "text": c["text"] if c else ln.get("text", ""),
                                "official": c["official"] if c else bool(ln.get("official")),
                                **{k: ln[k] for k in ("answersQuestionId", "asked") if ln.get(k)}})
        added = len(passing)
        store.load("consents", {})[draft_id] = {"owner": me, "at": now(), "removed": sorted(removed),
                                                "changed": changed, "rejected": rejected, "added": added}
        store.save("consents")
        nid, answered = publish_lines(me, note["program"], mid, passing)
        note["share"] = "partial" if removed else "shared"
        note["noteId"] = nid
        store.save("myNotes")
        _alert(me, "해봤노트에 내 이야기가 반영됐어요", noteId=nid)   # 바로 반영되므로 완료 알림(디자인 규칙 7-②, 11/22)
        out = {"ok": True, "noteId": nid, "added": added, "answered": answered}
        st = demand.recommend_status(me)          # [11/22] 이번 공유로 선배 추천이 열렸으면 unlocked
        out["recommend"], out["unlocked"] = st, st["ready"] and not ready_before
        if rejected:
            out["rejected"] = rejected     # 화면은 걸린 문장마다 message를 보여 준다
        return out


def publish_lines(me, program, my_note_id, passing):
    """동의 통과 문장을 runtime/noteLines.json에 쌓는다(작업 26·74, spec 4장 saveConsent).
    같은 내 경험노트로 다시 동의하면 그 노트의 문장을 이번 범위로 바꾼다(sourceId는 문장마다 유지).
    answersQuestionId가 붙은 문장이 통과했을 때만 그 질문을 answered로 바꾸고 질문자에게 알린다.
    칸 이름이 「후배 질문」이라는 이유만으로는 알리지 않는다. 돌려주는 값: (noteId, 이번에 알린 질문 id 목록)"""
    nid = notes.note_id(program)
    semester = notes.experience_semester(me, program)
    with store.lock():
        questions = {q.get("id"): q for q in store.load("questions", [])}

        def real_question(qid):
            # 같은 프로그램·남이 한·질문함(hold/answered) 질문만. 화면이 보낸 questionId를 그대로 믿지 않는다.
            q = questions.get(qid)
            return bool(q) and q.get("프로그램명") == program and q.get("colreg_no") != me \
                and q.get("status") in ("hold", "answered")

        rows = store.load("noteLines", [])
        prev = [r for r in rows if r.get("myNoteId") == my_note_id]
        prev_sid = {r.get("draftLineId"): r["sourceId"] for r in prev}
        prev_q = {r.get("answersQuestionId") for r in prev if r.get("answersQuestionId")}
        at = now()
        fresh = []
        for ln in passing:
            row = {"noteId": nid, "program": program, "section": ln["section"], "text": ln["text"],
                   "sourceId": prev_sid.get(ln["draftLineId"]) or store.next_id("I"), "semester": semester,
                   "official": ln["official"], "owner": me, "myNoteId": my_note_id, "draftLineId": ln["draftLineId"], "at": at}
            if ln.get("asked"):
                row["asked"] = ln["asked"]
            if ln.get("answersQuestionId") and real_question(ln["answersQuestionId"]):
                row["answersQuestionId"] = ln["answersQuestionId"]
            fresh.append(row)
        rows[:] = [r for r in rows if r.get("myNoteId") != my_note_id] + fresh
        store.save("noteLines")
        versions = store.load("noteVersions", {})       # 노트 버전 +1 → recommendSeniors가 목록을 다시 계산
        versions[nid] = versions.get(nid, 0) + 1
        store.save("noteVersions")

        answered = []
        for qid in dict.fromkeys(r["answersQuestionId"] for r in fresh if r.get("answersQuestionId")):
            q = questions[qid]
            if q["status"] == "hold":
                q.update(status="answered", noteId=nid, answeredAt=at)
            if qid not in prev_q:   # 같은 선배가 다시 동의해도 알림은 한 번. 다른 선배가 답하면 또 알린다(A가 쌓임)
                _alert(q["colreg_no"], f"내 질문에 선배가 답했어요 · {program} 해봤노트", questionId=qid, noteId=nid)
                answered.append(qid)
        store.save("questions")
        return nid, answered


def reportStatement(me, p):
    line_id = p.get("lineId")
    if not line_id:
        return {"error": "신고할 문장이 없어요"}
    with store.lock():
        store.load("reported", {})[line_id] = {"by": me, "reason": p.get("reason"), "at": now(), "status": "숨김 중"}
        store.save("reported")
    return {"ok": True, "hidden": True}


# ---------- 내 경험노트 [11/22, 작업 23 민지 요청] ----------
# 카드(getInbox.myNotes)와 상세(getMyNote)가 같은 계산을 쓴다.
# 공유 상태는 share(private | partial | shared) 셋뿐 — saveConsent가 바로 반영하므로 「반영 중」은 없다(11/22 미리 결정).
def _my_note_view(mid, v, detail=False):
    program = v["program"]
    kind = notes._kind(program)
    frame = list((notes.FRAMES.get(kind) or {}).get("칸", []))
    hidden = set(store.load("reported", {}))
    shared_ids = {r.get("draftLineId") for r in store.load("noteLines", [])
                  if r.get("myNoteId") == mid and "L-" + r.get("sourceId", "") not in hidden}
    mine = {s["name"]: s.get("lines", []) for s in (v.get("myNote") or {}).get("sections", [])}
    pub = {s["name"]: s.get("lines", []) for s in (v.get("publicDraft") or {}).get("sections", [])}
    names = frame + [n for n in mine if n not in frame]          # 틀에 없는 칸(틀이 바뀐 경우)은 뒤에
    view = {"id": mid, "program": program, "type": kind, "noteId": notes.note_id(program),
            "share": v.get("share", "private"),
            "filled": sum(1 for n in frame if mine.get(n)), "total": len(frame),
            "sharedLines": len(shared_ids & {ln.get("lineId") for ls in pub.values() for ln in ls}),
            "updatedAt": v.get("updatedAt")}
    if not detail:
        return view
    sections = []
    for name in names:
        lines = []
        for i, ln in enumerate(mine.get(name, [])):
            p_ln = (pub.get(name) or [])[i] if i < len(pub.get(name) or []) else {}   # 요약 때 같은 순서로 만들어짐
            row = {"text": ln.get("text", ""), "publicText": p_ln.get("text"), "lineId": p_ln.get("lineId"),
                   "shared": p_ln.get("lineId") in shared_ids}
            for k in ("asked", "answersQuestionId"):
                if ln.get(k):
                    row[k] = ln[k]
            lines.append(row)
        sections.append({"name": name, "lines": lines})
    return {**view, "draftId": v.get("draftId"), "sections": sections, "publicDraft": v.get("publicDraft")}


def getMyNote(me, p):
    """내 경험노트 상세(디자인 규칙 8절). 본인 것만. publicDraft·draftId는 공개 동의 시트를 다시 열 때 쓴다."""
    mid = (p.get("id") or "").strip()
    with store.lock():
        v = store.load("myNotes", {}).get(mid)
        if not v or v.get("owner") != me:
            return {"error": "볼 수 없는 기록이에요"}
        return _my_note_view(mid, v, detail=True)


def getInbox(me, p):
    with store.lock():
        my_notes = [_my_note_view(k, v) for k, v in store.load("myNotes", {}).items() if v["owner"] == me]
        my_notes.sort(key=lambda n: n.get("updatedAt") or "", reverse=True)   # 최근에 요약한 것이 위
        questions = [{"questionId": q["id"], "text": q["질문"], "askedAt": q["at"],
                      # spec 4장 getInbox [11/19]: hold(미답변) | answered. 규정 질문은 official 그대로
                      "status": q["status"] if q["status"] in ("answered", "official") else "hold",
                      **({"noteId": q["noteId"]} if q.get("noteId") else {}),
                      **({"answeredAt": q["answeredAt"]} if q.get("answeredAt") else {})}
                     for q in store.load("questions", []) if q["colreg_no"] == me]
        questions.sort(key=lambda q: (q["status"] != "answered", q["askedAt"]))   # 답변 도착이 맨 위
        alerts = sorted(store.load("alerts", {}).get(me, []), key=lambda a: a["at"], reverse=True)
    return {"myNotes": my_notes, "questions": questions, "scraps": notes.inbox_scraps(me), "alerts": alerts}


ROUTES = {
    "checkMessage": checkMessage,
    "previewNickname": previewNickname,
    "sendMessage": sendMessage,
    "getMessages": getMessages,
    "respondRequest": respondRequest,
    "reportThread": reportThread,           # [11/23] 쪽지 신고·차단 (AI 없음)
    "recommendSeniors": recommendSeniors,   # AI 없음 → 호출 한도와 무관(작업 85)
    "saveConsent": saveConsent,
    "getMyNote": getMyNote,   # [11/22] 내 경험노트 상세
    "reportStatement": reportStatement,
    "getInbox": getInbox,
    **demand.ROUTES,     # [11/22] demandNext·saveDemand (궁금한 것 정리하기, AI 없음)
    **notes.ROUTES,      # getNote·listNotes (AI 없음, 작업 26·74)
}

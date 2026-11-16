# runtime_fns.py — 쓰기 저장소를 쓰는 서버 함수 (작업 51)
# 응답 모양은 docs/spec-v1.md 4장. 저장은 store.py만 거친다. AI 없음.
#
# 모든 함수 모양: 함수(me, payload) -> dict
#   me = 요청 헤더 X-User의 colreg_no (local_fn.py가 넣어 준다)
#
# 다른 작업에서 쓰라고 열어 둔 도우미:
#   add_question(me, text, ...)    — askBoo가 hold일 때 질문함에 넣기(작업 18)
#   save_my_note(me, ...)          — summarizeInterview가 내 경험노트를 저장할 때(작업 21)
#   senior_label(viewer, senior)   — recommendSeniors 카드 이름(작업 22). 쪽지창과 같은 값
import json
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import store

KST = timezone(timedelta(hours=9))
DATA = Path(__file__).resolve().parent.parent / "data"

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
    for tid, t in store.load("messages", {}).items():
        if t["asker"] == asker and t["senior"] == senior:
            return tid, t
    return None, None


def _alert(to, text, **extra):
    alerts = store.load("alerts", {})
    alerts.setdefault(to, []).append({"text": text, "at": now(), **extra})
    store.save("alerts")


# ---------- 쪽지 ----------
def checkMessage(me, p):
    """연락처·학번은 코드가 막는다. 비방 판정(AI)은 작업 27에서 더한다."""
    text = p.get("text", "")
    if re.search(r"\b(H\d{4}|staff\d+)\b", text, re.I):
        return {"ok": False, "reason": "학번", "message": "학번은 보낼 수 없어요."}
    if re.search(r"\d{8,}", re.sub(r"[\s\-.]", "", text)):
        return {"ok": False, "reason": "연락처", "message": "전화번호나 학번은 보낼 수 없어요. 이메일은 괜찮아요."}
    return {"ok": True}


def previewNickname(me, p):
    to = p.get("to")
    if not to:
        return {"error": "받는 선배가 없어요"}
    with store.lock():
        _, t = _find_thread(me, to)
        if t:
            return {"myNickname": t["askerNickname"]}
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
        threads = store.load("messages", {})
        # 받은 선배가 답하는 경우가 먼저, 아니면 내가 보낸 대화
        tid, t = _find_thread(to, me)
        if not t:
            tid, t = _find_thread(me, to)
        if t is None:                                   # 첫 메시지 = 쪽지 요청
            nickname = previewNickname(me, {"to": to})["myNickname"]
            store.load("pendingNicknames", {}).pop(f"{to}|{me}", None)
            store.save("pendingNicknames")
            tid = store.next_id("T")
            t = threads[tid] = {"asker": me, "senior": to, "askerNickname": nickname,
                                "status": "requested", "createdAt": now(), "messages": [], "lastRead": {}}
            _alert(to, "쪽지 요청이 왔어요", threadId=tid)
        elif t["status"] == "declined":
            return {"ok": False, "message": "선배가 이 요청을 받지 않았어요"}
        elif t["status"] == "requested":
            return {"ok": False, "message": "선배가 수락하면 대화를 이어갈 수 있어요"}

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
        threads = store.load("messages", {})
        for tid, t in sorted(threads.items(), key=lambda kv: kv[1]["createdAt"], reverse=True):
            if me not in (t["asker"], t["senior"]):
                continue
            role = "asker" if t["asker"] == me else "senior"
            other = t["senior"] if role == "asker" else t["asker"]
            last = t["lastRead"].get(me, "")
            item = {
                "threadId": tid, "role": role, "withId": other,
                "nickname": senior_label(me, other) if role == "asker" else t["askerNickname"],
                "accepted": t["status"] == "accepted",
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
            t["lastRead"][me] = now()
            out.append(item)
        store.save("messages")
        return {"threads": out}


def _asker_info(asker):
    """선배에게 보여 줄 보낸 사람 정보: 학년 + 관심 경험(질문함의 프로그램). 학과는 넣지 않는다."""
    grade = student(asker).get("regst_grad")
    interests = []
    for q in store.load("questions", []):
        name = q.get("프로그램명")
        if q.get("colreg_no") == asker and name and name not in interests:
            interests.append(name)
    return {"학년": grade, "관심": interests[:2]}


def respondRequest(me, p):
    tid = p.get("threadId")
    with store.lock():
        t = store.load("messages", {}).get(tid)
        if not t or t["senior"] != me:
            return {"error": "이 요청에 답할 수 없어요"}
        if t["status"] != "requested":
            return {"ok": True, "accepted": t["status"] == "accepted"}
        accept = bool(p.get("accept"))
        t["status"] = "accepted" if accept else "declined"
        store.save("messages")
        label = senior_label(t["asker"], me)
        _alert(t["asker"], f"쪽지 요청이 수락됐어요 · {label}" if accept else f"이번 쪽지 요청은 연결되지 않았어요 · {label}",
               threadId=tid)
        return {"ok": True, "accepted": accept}


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


def save_my_note(me, program, draft_id, my_note, public_draft):
    """summarizeInterview(작업 21)가 부른다. 같은 사람·같은 프로그램이면 같은 myNoteId를 갱신."""
    with store.lock():
        notes = store.load("myNotes", {})
        mid = next((k for k, v in notes.items() if v["owner"] == me and v["program"] == program), None)
        mid = mid or store.next_id("M")
        old = notes.get(mid, {})
        notes[mid] = {"owner": me, "program": program, "draftId": draft_id, "myNote": my_note,
                      "publicDraft": public_draft, "share": old.get("share", "private"), "updatedAt": now()}
        store.save("myNotes")
        return mid


def saveConsent(me, p):
    if not p.get("consent"):
        return {"error": "공개 동의가 필요해요"}
    draft_id = p.get("draftId")
    edits = p.get("edits") or {}
    removed = set(edits.get("removed") or [])
    with store.lock():
        note = next((v for v in store.load("myNotes", {}).values()
                     if v["owner"] == me and v["draftId"] == draft_id), None)
        lines = [ln for sec in (note or {}).get("publicDraft", {}).get("sections", []) for ln in sec.get("lines", [])]
        added = sum(1 for ln in lines if ln.get("lineId") not in removed)
        store.load("consents", {})[draft_id] = {"owner": me, "at": now(), "removed": sorted(removed),
                                                "changed": edits.get("changed") or [], "added": added}
        store.save("consents")
        if note:
            note["share"] = "partial" if removed else "shared"
            store.save("myNotes")
        _alert(me, "해봤노트에 반영하고 있어요")
        # 해봤노트 합성(작업 26)이 noteId를 정한다. 그 전까지는 프로그램 이름으로 돌려준다.
        return {"ok": True, "noteId": (note or {}).get("program"), "added": added}


def reportStatement(me, p):
    line_id = p.get("lineId")
    if not line_id:
        return {"error": "신고할 문장이 없어요"}
    with store.lock():
        store.load("reported", {})[line_id] = {"by": me, "reason": p.get("reason"), "at": now(), "status": "숨김 중"}
        store.save("reported")
    return {"ok": True, "hidden": True}


def getInbox(me, p):
    with store.lock():
        my_notes = [{"id": k, "program": v["program"], "share": v["share"]}
                    for k, v in store.load("myNotes", {}).items() if v["owner"] == me]
        questions = [{"questionId": q["id"], "text": q["질문"], "askedAt": q["at"],
                      "status": "answered" if q["status"] == "answered" else
                                ("official" if q["status"] == "official" else "waiting"),
                      **({"noteId": q["noteId"]} if q.get("noteId") else {})}
                     for q in store.load("questions", []) if q["colreg_no"] == me]
        questions.sort(key=lambda q: (q["status"] != "answered", q["askedAt"]))   # 답변 도착이 맨 위
        alerts = sorted(store.load("alerts", {}).get(me, []), key=lambda a: a["at"], reverse=True)
        return {"myNotes": my_notes, "questions": questions, "scraps": [], "alerts": alerts}


ROUTES = {
    "checkMessage": checkMessage,
    "previewNickname": previewNickname,
    "sendMessage": sendMessage,
    "getMessages": getMessages,
    "respondRequest": respondRequest,
    "saveConsent": saveConsent,
    "reportStatement": reportStatement,
    "getInbox": getInbox,
}

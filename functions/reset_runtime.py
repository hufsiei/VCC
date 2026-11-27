# reset_runtime.py — 리허설 전에 쓰기 기록을 시연 시작 상태로 되돌린다 (작업 51, spec 2-1)
# 실행: cd C:\dev\VCC\functions
#   python reset_runtime.py         로컬(data/runtime). 서버(local_fn.py)가 켜져 있으면 먼저 끄고 실행한 뒤 다시 켠다.
#   python reset_runtime.py --ncp   공개 주소(Cloud Functions)의 기록 — Object Storage 버킷의 runtime/ 객체를 지운다(작업 58).
#                                   .env의 NCP_OS_BUCKET·NCP_OS_ACCESS_KEY·NCP_OS_SECRET_KEY를 쓴다. 액션은 요청마다 새로 읽으므로 재배포 필요 없음.
#   --dry                           (전부 지우기) 지울 파일 이름만 보여 주고 지우지 않는다.
#
# [작업 39, 11/25] 시연 계정만 초기화(12/3·12/8은 시연 계정 + 시험 계정 H0002·H0004 — 11/26 결정 A):
#   python reset_runtime.py --ncp --only H0143,H0469,H0241,staff01,staff02,H0002,H0004          보기만(기본)
#   python reset_runtime.py --ncp --only H0143,H0469,H0241,staff01,staff02,H0002,H0004 --yes    실제로 지운다
#   새 runtime 기록을 만들면 HANDLED(plan에 규칙) 아니면 UNTOUCHED에 넣는다 — test_reset_runtime.py가 대조한다.
#   그 계정이 들어간 기록만 지우고 다른 계정(미리 시험 인터뷰 등)의 기록은 남긴다. 파일별 규칙은 아래 RULES.
#   · 쪽지 대화는 한쪽이라도 시연 계정이면 대화째 지운다(섞인 대화) — 시연 계정이 처음 상태에서 다시 요청할 수 있게.
#     그 대화의 알림·대화 신고·미리 정한 닉네임도 함께 지운다. 상대(다른 계정)의 다른 기록은 남는다.
#   · 시연 계정이 공개 동의한 해봤노트 문장(noteLines)만 빼고, 그 노트의 noteVersions를 +1 → 추천 목록이 다시 계산된다.
#   · 사람 칸이 없는 askLog, 번호 counters(되돌리면 번호가 겹침), 관리자 파일(reportSettings·issuedReports·reportHtml·
#     suggestionStatus)은 건드리지 않는다. 규칙에 없는 파일도 건드리지 않고 이름만 알린다.
#   AI 호출 없음. 서버를 끄지 않아도 되지만(ncp는 저장할 때 다시 읽어 합침), 시연 중에는 돌리지 않는다.
import copy
import os
import sys

import paths

# 건드리지 않는 파일과 이유
UNTOUCHED = {
    "askLog": "사람 칸 없음(학번을 남기지 않는 BOO 답 기록)",
    "counters": "번호 — 되돌리면 T-·Q-·M- 번호가 겹침",
    "reportSettings": "관리자 파일",
    "issuedReports": "관리자 파일",
    "reportHtml": "관리자 파일",
    "suggestionStatus": "관리자 파일",
}


def _drop_keys(data, ids, key_of=lambda k, v: k):
    """dict에서 key_of(k, v)가 ids에 든 항목을 뺀 새 dict와 뺀 수."""
    out = {k: v for k, v in data.items() if key_of(k, v) not in ids}
    return out, len(data) - len(out)


def plan(ids, load):
    """시연 계정 ids의 기록을 뺀 새 모습을 계산한다. load(name, default)는 store.load.
    돌려주는 값: [(이름, 새 값, 지운 수, 설명)] — 바뀐 파일만. 저장은 부르는 쪽이 한다."""
    ids = set(ids)
    out = []

    def add(name, new, n, what):
        if n:
            out.append((name, new, n, what))

    # 쪽지 대화 {threadId: {asker, senior, …}} — 한쪽이라도 시연 계정이면 대화째
    threads = load("messages", {})
    gone_threads = {tid for tid, t in threads.items() if t.get("asker") in ids or t.get("senior") in ids}
    mixed = sum(1 for tid in gone_threads
                if not ({threads[tid].get("asker"), threads[tid].get("senior")} <= ids))
    add("messages", {k: v for k, v in threads.items() if k not in gone_threads}, len(gone_threads),
        f"쪽지 대화(다른 계정과 섞인 대화 {mixed}건 포함)")

    # 질문함 [ {colreg_no, …} ]
    questions = load("questions", [])
    kept_q = [q for q in questions if q.get("colreg_no") not in ids]
    gone_q = {q.get("id") for q in questions if q.get("colreg_no") in ids}
    add("questions", kept_q, len(questions) - len(kept_q), "질문")

    # 해봤노트 공개 문장 [ {owner, noteId, …} ] → 그 노트 버전 +1
    lines = load("noteLines", [])
    kept_l = [r for r in lines if r.get("owner") not in ids]
    touched = sorted({r.get("noteId") for r in lines if r.get("owner") in ids and r.get("noteId")})
    add("noteLines", kept_l, len(lines) - len(kept_l), "공개 동의 문장")
    if touched:
        versions = copy.deepcopy(load("noteVersions", {}))
        for nid in touched:
            versions[nid] = versions.get(nid, 0) + 1
        add("noteVersions", versions, len(touched), "노트 버전 +1(추천 다시 계산): " + ", ".join(touched))

    # 알림 {colreg_no: [ {threadId?, questionId?} ]} — 시연 계정 것 통째 + 다른 계정이 받은 지워진 대화·질문 알림
    alerts = load("alerts", {})
    new_alerts, n_alerts = {}, 0
    for who, rows in alerts.items():
        if who in ids:
            n_alerts += len(rows)
            continue
        keep = [a for a in rows if a.get("threadId") not in gone_threads and a.get("questionId") not in gone_q]
        n_alerts += len(rows) - len(keep)
        new_alerts[who] = keep
    add("alerts", new_alerts, n_alerts, "알림")

    # 대화 신고 [ {threadId, by} ]
    reports = load("threadReports", [])
    kept_r = [r for r in reports if r.get("by") not in ids and r.get("threadId") not in gone_threads]
    add("threadReports", kept_r, len(reports) - len(kept_r), "대화 신고")

    # 미리 정한 닉네임 {"선배|보낸사람": 이름}
    pend = load("pendingNicknames", {})
    new = {k: v for k, v in pend.items() if not (set(k.split("|")) & ids)}
    add("pendingNicknames", new, len(pend) - len(new), "미리 정한 동물 닉네임")

    # 보는 사람 기준 dict — 시연 계정 키만
    for name, what in (("nicknames", "보는 사람별 선배 글자"), ("shownSeniors", "추천 목록"),
                       ("recommendOptOut", "추천받기 끔"), ("aiUsage", "AI 호출 수"), ("scraps", "스크랩"),
                       ("loginFails", "로그인 실패 횟수·잠금")):
        new, n = _drop_keys(load(name, {}), ids)
        add(name, new, n, what)

    # owner 칸이 있는 dict
    for name, what in (("myNotes", "내 경험노트"), ("consents", "공개 동의"), ("interviewDrafts", "인터뷰 초안"),
                       ("tellChat", "대화형 인터뷰 판정(작업 110)")):
        new, n = _drop_keys(load(name, {}), ids, lambda k, v: v.get("owner"))
        add(name, new, n, what)

    new, n = _drop_keys(load("sessions", {}), ids, lambda k, v: v.get("me"))
    add("sessions", new, n, "로그인(다시 로그인해야 함)")

    new, n = _drop_keys(load("reported", {}), ids, lambda k, v: v.get("by"))
    add("reported", new, n, "문장 신고")

    demands = load("demands", [])
    kept_d = [d for d in demands if d.get("owner") not in ids]
    add("demands", kept_d, len(demands) - len(kept_d), "궁금한 것 정리")
    return out


HANDLED = {"messages", "questions", "noteLines", "noteVersions", "alerts", "threadReports", "pendingNicknames",
           "nicknames", "shownSeniors", "recommendOptOut", "aiUsage", "scraps", "myNotes", "consents",
           "interviewDrafts", "tellChat", "sessions", "reported", "demands", "loginFails"}


def apply(store, changes):
    """plan 결과를 저장한다. 메모리의 기록을 그 자리에서 바꾼 뒤 save(ncp는 저장 직전 다시 읽어 합침)."""
    with store.lock():
        for name, new, _, _ in changes:
            cur = store.load(name, type(new)())
            if isinstance(cur, dict):
                cur.clear()
                cur.update(new)
            else:
                cur[:] = new
            store.save(name)


def report(store, ids, changes):
    names = set(store.list_names())
    print(f"대상 계정 {len(ids)}개: {', '.join(sorted(ids))}")
    for name, _, n, what in changes:
        print(f"  {name}.json  {n}건 — {what}")
    if not changes:
        print("  지울 기록 없음")
    for name in sorted(names - HANDLED):
        why = UNTOUCHED.get(name, "규칙에 없는 파일")
        print(f"  {name}.json  건드리지 않음 — {why}")


def _arg(flag):
    argv = sys.argv[1:]
    return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) else None


if __name__ == "__main__":
    argv = sys.argv[1:]
    ncp = "--ncp" in argv
    if ncp:
        paths.load_env()
        os.environ["STORE_BACKEND"] = "ncp"
        os.environ.setdefault("NCP_OS_PREFIX", "runtime/")
    import store

    where = (f"Object Storage {os.environ.get('NCP_OS_BUCKET', '?')}/{os.environ['NCP_OS_PREFIX']}" if ncp
             else str(store.RUNTIME))
    if "--only" in argv:
        only = [x.strip() for x in (_arg("--only") or "").split(",") if x.strip()]
        if not only:
            sys.exit("--only 뒤에 계정을 쉼표로 적어 주세요(예: --only H0143,H0469)")
        changes = plan(only, store.load)
        report(store, only, changes)
        if "--yes" not in argv or "--dry" in argv:
            print(f"보기만 했어요({where}). 지우려면 --yes를 붙여 다시 실행하세요.")
        else:
            apply(store, changes)
            print(f"시연 계정 기록만 지웠어요: {where}")
    elif "--dry" in argv:
        names = store.list_names()
        print(f"전부 지우면 사라질 파일 {len(names)}개({where}): {', '.join(names) or '없음'}")
    else:
        store.clear_all()
        # 시연 시작 상태: 지금은 빈 상태. 미리 넣어 둘 기록이 생기면 여기에 store.load/save로 추가한다.
        print(f"초기화했어요: {where}")

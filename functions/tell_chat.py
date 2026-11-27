# tell_chat.py — 들려주기 대화형 인터뷰 [작업 110 초안, 작성: 미리]
#
# 플래그 VCC_TELL_CHAT=1일 때만 interview.py가 부른다. 기본(0)은 지금 그대로 — 이 파일의 어떤 함수도 불리지 않는다.
# 왜: 들려주기가 고정 질문만 내고, 선배의 되묻는 말·딴 얘기도 답으로 저장했다(11/26 진단). 팀 결정(11/27) 전 초안.
#
# 한 턴(interviewNext 한 번) — 선배가 새 말을 보냈을 때:
#   ① AI(말판정, HCX): 방금 말 → 종류 6종(답·부족·되물음·딴얘기·모름·그만) + 궁금(경험·프로그램에 대해 알고 싶은 것).
#   ② 코드: 무엇을 물을지는 지금 코드(interview._next_step, 충분판정·꼬리질문은 끔)가 정한다 — 후배 질문 먼저·칸 진행·끝 조건 그대로.
#        「답」만 answers로 센다(다른 칸 이야기면 ③의 칸으로 옮김 — [Q-116] 옮겨서 방금 칸의 질문이 원문 그대로
#        다음 질문이 되면 그 칸은 넘긴다: 같은 질문 되풀이 0). 부족·되물음·딴얘기는 없던 말로 치고 같은 질문을 다시 묻는다
#        (같은 질문에 MAX_REASK번 넘게 이어지면 넘긴다). 모름은 그 질문을 넘긴다(후배 질문은 건너뛰기와 같게 hold로 남음).
#        그만이면 done(stopped).
#   ③ AI(대화쓰기, Sonnet): 이번 대화 전체 + 지난 노트 문장 + 남은 칸·후배 질문·깊이 질문 후보 + ②의 다음 질문
#        → {반응, 칸, 더묻기, 질문}. 더묻기는 그 칸(후배 질문은 그 질문)의 첫 답일 때 한 번만 받는다(지금 꼬리 질문과 같은 횟수).
#   ④ 코드 검증: 대화·후보에 없는 숫자·영문·고유명사, 길이, 해요체, 이미 물은 질문. askboo.verify의 「수량」「새 낱말」은
#        보지 않는다(11/26 시험에서 「한 장면」을 수량으로 잘못 잡음 — 반응·질문은 새 말을 써야 하는 글). 걸린 값만 버린다:
#        반응 → 고정 문구(FALLBACK_REACTION), 질문 → ②의 질문 원문, 칸 → 질문의 칸, 더묻기 → ②의 다음 질문.
#   ⑤ 판정은 서버에 남긴다(store tellChat). 화면은 answers를 통째로 다시 보내므로 다음 턴·요약에서 같은 말을 같은 종류로 본다.
#        말·질문 원문은 남기지 않고 해시만 키로 쓴다(마지막 응답 하나만 그대로 — 같은 answers로 다시 부를 때 AI를 다시 안 부르게).
#        다듬은 질문 → 원래 질문(깊이 질문 번호·예시 칩·요약 맥락이 그대로 맞게).
#        7일 지나면 지우고, 요약(summarizeInterview)이 끝나면 지운다. 화면이 heard.kind를 answers의 kind로 돌려보내면 그 값이 먼저다(제안).
#   ⑥ 궁금 → askboo._save(#369 관문: 연락처·학번·메일·비방)를 지나 내 질문함(hold, 지금 들려주는 프로그램)에 담는다.
#        질문의 뜻·왜 묻는지 되묻는 말은 담지 않는다(말판정이 궁금 null). 궁금 글이 선배 말 그대로가 아니면 말 전체(짧을 때만).
#        [Q-114] 궁금 글이 지시어뿐이면(「나도 그게 궁금했는데」) 「(BOO 질문) 선배 말」로 담는다. 담은 턴이 부족·되물음이면
#        반응 없이 HELD_TEXT + 다시 묻는 질문만. 부족·되물음·딴얘기 반응에 평가 말(_EVAL)이 들면 버린다.
#   [Q-131] ① 뒤 코드 바로잡기(fix_kind): 부호뿐 → 되물음, 「다 말했어요」·「남들도 궁금해할 것」 → 부족, 짧은 「모르겠어요」 → 모름,
#        「네?」 → 되물음(궁금 버림), 숫자 든 부족·딴얘기 → 답. 종류가 6종 밖이어도 궁금 글이 있으면 되물음(parse_judge). 「누가 보낸 질문이냐」는 담지 않는다(_META).
# 실패: 말판정이 실패하면 지금처럼 답으로 보고 고정 질문(반응 없음). 대화쓰기가 실패하면 고정 질문 + 고정 반응.
# 응답(제안 — spec·화면 미반영): 지금 필드 그대로 + reaction(반응 글) · heard {kind, section}(방금 말을 어떻게 봤는지)
#        · heldQuestionId(질문함에 담은 질문) · stopped(그만). 화면이 reaction을 질문 말풍선 앞에 그리면 된다.
import hashlib
import os
import re

import askboo
import store

FLAG = "VCC_TELL_CHAT"
STORE = "tellChat"
KINDS = ("답", "부족", "되물음", "딴얘기", "모름", "그만")
REASK_KINDS = {"부족", "되물음", "딴얘기"}   # 없던 말로 치고 같은 질문을 다시
MAX_REASK = 2          # 같은 질문을 다시 묻는 횟수 상한. 넘으면 모름처럼 넘긴다(인터뷰가 한 질문에 갇히지 않게)
MAX_REACTION = 120     # 반응 글자 수
MAX_SENTENCES = 3      # 반응 문장 수(프롬프트는 1~2, 검증은 느슨하게)
MAX_QUESTION = 60      # 질문 글자 수(꼬리질문 검증과 같음)
MAX_CURIOUS = 120      # 궁금 글이 말 그대로가 아닐 때 말 전체를 담는 상한
MAX_MEMORY = 80        # 사람·프로그램마다 남기는 판정 수
KEEP_DAYS = 7          # 인터뷰 초안(runtime_fns.DRAFT_DAYS)과 같은 보관기간
HISTORY_TURNS = 12     # 대화쓰기에 넘기는 지난 턴 수
MAX_TURN_CHARS = 300   # 대화쓰기에 넘기는 말 하나 글자 수
PRIOR_LINES = 8        # 대화쓰기에 넘기는 지난 노트 문장 수
ALLOW = "해봤노트 후배 선배 BOO 인터뷰 노트 경험 질문 이야기"   # 반응·질문에 써도 되는 말(검증 원문에 더함)

STOP_TEXT = "알겠어요. 들려주셔서 고마워요. 아래 AI 요약을 누르면 지금까지 이야기가 정리돼요."
HELD_TEXT = "궁금하신 점은 내 질문함에 담아 두었어요."
FALLBACK_REACTION = {   # 대화쓰기가 실패하거나 반응이 검증에 걸렸을 때. 답은 반응 없이 다음 질문만
    "부족": "괜찮아요. 떠오르는 장면 하나만 들려주셔도 돼요.",
    "되물음": "다시 여쭤볼게요.",   # [Q-114] 평가·설명 없이 중립(풀어 묻기는 질문이 맡음)
    "딴얘기": "인터뷰로 돌아와서 이어서 여쭤볼게요.",
    "모름": "괜찮아요. 다음 질문으로 넘어갈게요.",
}
_END = re.compile(r"(요|죠|까)[.!?~]*$")
_ASK_END = re.compile(r"(요|까)\?$|주세요\.?$")   # 「…들려주세요.」도 질문으로(기본 질문 「배운 점을 … 들려주세요.」와 같은 끝맺음)
_FEATURE = re.compile(r"질문함|요약|저장")   # 화면 기능을 말하는 반응은 버린다(담았는지·정리되는지는 코드가 붙인다)
# [Q-114] 부족·되물음·딴얘기 반응에 선배의 이해·질문 난이도·말의 부족함을 평가하는 말이 들면 버린다
# (11/27 시험: 「나도 그게 궁금했는데」 → 「질문이 조금 어려웠을 수 있어요. …여쭤본 거예요.」 — 무시당하는 느낌)
# [Q-131] 「(제가) 써 드리기 어려워요」처럼 BOO 자신이 못 하는 일을 말하는 「~기 어려워요」는 평가 말이 아니다(S08 반응 버림 3건)
_EVAL = re.compile(r"어려[웠우]|(?<!기)(?<!기\s)어려워|어렵|헷갈|이해|쉽게\s*말(하면|씀)|다시\s*말(해|하면|씀드리)|무슨\s*말인지|부족|모호|애매"
                   r"|질문이\s*(조금|좀|너무)?\s*(길|막연|추상)")
NO_REACTION_HELD = {"부족", "되물음"}   # [Q-114] 질문함에 담은 턴은 반응 없이 HELD_TEXT + 다시 묻는 질문만(말풍선 겹침)
# [Q-114] 궁금 글이 지시어뿐인지 볼 때 빼는 말(지시어·궁금 표현·맞장구). 남는 낱말이 없으면 BOO 질문을 함께 담는다
_DEICTIC = re.compile(r"^(그|이|저)(게|거|것|건|걸)")
_FILLER = re.compile(r"^(나|저|저희|우리)(도|는|가)?$|궁금|알(려|고|면)|싶|모르|^(했|해|하)"
                     r"|^(진짜|정말|사실|근데|그런데|그래서|음+|아+|어+|오+|ㅋ+|ㅎ+|네|예)$")
MAX_HELD_ASK = 60      # 지시어 궁금에 함께 담는 BOO 질문 글자 수(넘으면 말줄임)
# ⑥ 질문의 뜻·왜 묻는지·예를 들어 달라는 말은 궁금으로 담지 않는다 — 말판정이 궁금을 붙여도 코드가 한 번 더 거른다
# (실제 호출 11/26: 「각오라는 게 무슨 뜻이에요? 예를 들어 주세요.」를 HCX가 궁금으로 냄)
# [Q-131] 후배 질문을 누가 보냈는지 묻는 말도 서비스에 대한 되물음이라 담지 않는다(S22 「이 질문은 누가 보낸 거예요?」)
_META = re.compile(r"뜻|무슨\s*(말|의미)|의미(가|를|예요|에요)|왜\s*(물어|묻|여쭤)|어디에\s*(쓰|써)|예를\s*들|예시"
                   r"|누가\s*(보낸|보냈|물어|물은|물었|남긴|남겼|올린|올렸|쓴|썼)")
# [Q-131] 말판정이 「답」이라 해도 코드가 바로잡는 말(11/27 측정 S20·S23·S26·S28). 말 전체가 이 모양일 때만 —
# 숫자가 있거나 뒤에 내용이 이어지면(「전에 말했듯이 비쌌어요」「주 5일이요」) 그대로 둔다. 판정은 _qn(띄어쓰기·부호 뺌) 글로 본다.
_PUNCT_ONLY = re.compile(r"[\s?？!.~…·]+")
_NO_CONTENT = re.compile(
    r"(제가|저는?)?(지난번에?|저번에?|전에|아까|이미|앞에서|예전에)(다|전부|모두|거의)?(말|얘기|이야기)"
    r"(했|한|해|드렸|드린)(는데요?|은데요?|던데요?|잖아요|어요|요|죠|습니다|거든요|(것|거)같(은데|아|네)요?)?"
    r"|(후배|후배들|다른사람|다른사람들|사람들|다들|애들|학생들|다른학생들)(도|이|은|는|이나|들도)?(이런|그런|이|그)?"
    r"(거|것|게|걸|부분)?(많이|진짜|정말|꽤|좀|다|되게)?(궁금해할|궁금해하실|궁금할|궁금해하|알고싶어할|물어볼|물어보실)"
    r"(것같아요|거같아요|텐데요?|듯해요|겠죠|겠어요|거예요|걸요|더라고요|던데요|죠|요|수도있어요|수있어요)?")
_DONT_KNOW_END = ("모르겠어요", "모르겠네요", "모르겠습니다", "모르겠는데요", "몰라요", "모릅니다",
                  "기억이안나요", "기억안나요", "기억이안나네요", "기억이잘안나요", "기억이안납니다")
_CONTRAST = re.compile(r"는데|은데|지만|였고|었고|했고|봤고|았고")   # 앞에 다른 내용이 있는 말(「…봤는데 질문은 기억이 안 나요」)
MAX_DONT_KNOW = 30     # 「모르겠어요」로 바로잡는 말의 글자 수 상한(부호·띄어쓰기 뺀 글)
# [Q-131 재측정] 「네?」처럼 감탄사 + 물음표뿐이면 되물음, 궁금 없음(재측정 S29: HCX가 궁금 「네?」를 내 질문함에 담김)
_BARE_ASK = {"네", "예", "응", "뭐", "뭐요", "네에", "예에", "어", "음", "엥", "잉", "넹", "왜요", "무슨"}
# [Q-131 재측정] 숫자가 든 말(「주 3일, 10시부터 4시까지였어요」)은 다른 칸 이야기여도 답 — HCX가 방금 질문과 칸이 다르면
# 딴얘기·부족으로 냄(재측정 S20 턴2). 지시(「…써 줘」)·연락처는 그대로 둔다.
_ORDER = re.compile(r"무시|지시|프롬프트|번역|코드|써\s*줘|해\s*줘|줘요?|주세요|해\s*주|알려\s*줘")
_CONTACT = re.compile(r"\d{2,4}[-\s.]?\d{3,4}[-\s.]?\d{4}|@|https?:|www\.")


def enabled():
    """부를 때마다 읽는다(시험·평가 스크립트가 환경변수로 두 길을 바꿔 돌린다)."""
    return os.environ.get(FLAG, "0").strip() == "1"


# ── 기록(store tellChat) ──────────────────────────────────────────────
def _qn(s):
    """질문 대조용: 띄어쓰기·문장부호를 뺀다."""
    return re.sub(r"[\s.,!?~…·\"'「」]+", "", s or "").lower()


def _h(*parts):
    return hashlib.sha256("\x1f".join(_qn(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def _said_key(a):
    return _h(a.get("question"), a.get("answer"))


def _turn_key(items):
    return _h(*[f"{a.get('question')}|{a.get('answer')}|{bool(a.get('skipped'))}" for a in items])


def _key(me, program):
    return f"{me}|{program}"


def load(me, program):
    from runtime_fns import _days_since
    with store.lock():
        rec = store.load(STORE, {}).get(_key(me, program))
    ok = (isinstance(rec, dict) and rec.get("owner") == me
          and rec.get("at") and _days_since(rec.get("at")) < KEEP_DAYS)
    rec = rec if ok else {}   # [작업 38] 7일 지난 기록은 빈 기록(save의 정리와 같은 기준)
    return {"said": dict(rec.get("said") or {}), "asked": dict(rec.get("asked") or {}), "last": rec.get("last")}


def _cap(d):
    return dict(list(d.items())[-MAX_MEMORY:])


def save(me, program, mem):
    from runtime_fns import _days_since, now
    with store.lock():
        rows = store.load(STORE, {})
        for k in [k for k, v in rows.items() if _days_since(v.get("at")) >= KEEP_DAYS or not v.get("at")]:
            del rows[k]
        rows[_key(me, program)] = {"owner": me, "program": program, "at": now(),
                                   "said": _cap(mem["said"]), "asked": _cap(mem["asked"]), "last": mem.get("last")}
        store.save(STORE)


def drop(me, program):
    with store.lock():
        rows = store.load(STORE, {})
        if rows.pop(_key(me, program), None) is not None:
            store.save(STORE)


def _resolve(items, mem):
    """화면이 보낸 answers → (센 answers, 넘긴 칸, 질문별 다시 물은 수).
    답만 남기고(다른 칸 이야기면 그 칸으로), 모름은 건너뛴 것으로, 부족·되물음·딴얘기·그만은 뺀다. 다듬은 질문은 원래 질문으로."""
    import interview as iv
    out, passed, reask = [], set(), {}
    for a in items:
        a = dict(a)
        said = mem["said"].get(_said_key(a)) if a.get("answer") and not a.get("skipped") else None
        kind = a.pop("kind", None)
        kind = kind if kind in KINDS else (said or {}).get("k")
        orig = mem["asked"].get(_h(a.get("question")))
        if orig:
            a["question"] = orig["q"]
        if kind in REASK_KINDS:
            reask[_h(a.get("question"))] = reask.get(_h(a.get("question")), 0) + 1
            continue
        if kind == "그만":
            continue
        if kind == "모름":
            a.pop("answer", None)
            a["skipped"] = True
            if not iv.is_junior(a) and not iv.depth_id(a.get("question")) and a.get("section"):
                passed.add(a["section"])   # 기본 질문·배운점은 건너뛰기가 없어 칸으로 넘긴다(깊이·후배 질문은 skipped로 넘어감)
        elif said and said.get("s"):
            a["section"] = said["s"]
            if said.get("p"):
                passed.add(said["p"])   # [Q-116] 옮기면서 넘긴 칸(next_step의 left)
        out.append(a)
    return out, passed, reask


def for_summary(me, program, items):
    """summarizeInterview 입력에서 답만(다른 칸 이야기는 그 칸, 다듬은 질문은 원래 질문)."""
    out, _, _ = _resolve(items, load(me, program))
    return [a for a in out if not a.get("skipped")]


# ── 한 턴 ─────────────────────────────────────────────────────────────
def next_step(me, program, payload, prior, mine=None):
    import interview as iv
    items = iv._clean_answers(payload.get("answers"))
    mem = load(me, program)
    last = items[-1] if items else None
    fresh = bool(last and last.get("answer") and not last.get("skipped") and not iv.bare_stem(last["answer"]))
    turn = _turn_key(items)
    cached = mem.get("last") or {}
    if fresh and cached.get("key") == turn and isinstance(cached.get("step"), dict):
        return cached["step"]   # 같은 answers로 다시 부름(재시도·이어 하기) — AI를 다시 부르지 않는다

    if not fresh or _said_key(last) in mem["said"] or last.get("kind") in KINDS:
        answers, passed, _ = _resolve(items, mem)
        return iv._next_step(me, program, {**payload, "answers": answers}, prior, follow=False, passed=passed)

    prev, passed, reask = _resolve(items[:-1], mem)
    orig = mem["asked"].get(_h(last.get("question")))
    cur = {**last, "question": orig["q"]} if orig else dict(last)
    placed = iv._place_all(program, iv._clean_answers(prev + [cur]))[-1]
    junior = iv.is_junior(placed)
    section = placed.get("section")
    before = items[-2] if len(items) > 1 else None

    def plan_with(answers, passed_):
        return iv._next_step(me, program, {**payload, "answers": answers}, prior, follow=False, passed=passed_)

    judged = judge(section, last.get("question") or "", last["answer"], before)
    if not judged:   # 판정 실패 — 지금처럼 답으로 보고 고정 질문(기록하지 않음: 다음 턴에도 답으로 센다)
        return plan_with(prev + [cur], passed)
    kind, curious = judged
    held = hold_question(me, program, curious, last["answer"], last.get("question")) if curious else None
    eff = kind
    if kind in REASK_KINDS and reask.get(_h(cur.get("question")), 0) + 1 > MAX_REASK:
        eff = "모름"

    if eff == "그만":
        plan = plan_with(prev, passed)
        step = {"done": True, "stopped": True, "progress": plan.get("progress"), "covered": plan.get("covered", []),
                "reaction": " ".join(x for x in (STOP_TEXT, HELD_TEXT if held else None) if x),
                "heard": {"kind": "그만", "section": None}}
        return _remember(me, program, mem, last, turn, {"k": "그만"}, step, held)

    skipped = {**{k: v for k, v in cur.items() if k != "answer"}, "skipped": True}
    answers = prev + ([cur] if eff == "답" else [skipped] if eff == "모름" else [])
    if eff == "모름" and not junior and not iv.depth_id(cur.get("question")) and section:
        passed = passed | {section}
    plan = plan_with(answers, passed)

    content = _write_input(me, program, items, prev, cur, section, eff, _can_follow(program, answers, eff, cur), plan,
                           prior, mine)
    w = write(content)
    source = content + " " + ALLOW
    asked = {_qn(a.get("question")) for a in items} | {_qn(cur.get("question"))}

    moved = left = None
    if w and eff == "답" and not junior and w.get("칸") in iv.sections_of(program) and w.get("칸") != section:
        moved = w["칸"]
        answers = prev + [{**cur, "section": moved}]
        plan2 = plan_with(answers, passed)
        if _repeats(plan2, asked):
            # [Q-116] 옮겨서 방금 칸이 다시 비면 코드가 방금 질문을 원문 그대로 다시 고른다(S05) — 그 칸은 넘기고 다음 차례로.
            # 넘긴 칸은 판정 기록(p)에 남겨 다음 턴에도 기본 질문으로 다시 묻지 않는다(깊이 질문 차례는 그대로)
            left = plan2.get("section")
            plan2 = plan_with(answers, passed | {left})
        if (plan2.get("section"), plan2.get("question")) != (plan.get("section"), plan.get("question")) \
                and w.get("더묻기") is not True:
            w = {**w, "질문": None}   # 다음 질문이 바뀌었으면 다듬은 글은 버리고 새 질문 원문(꼬리 질문은 방금 답에 대한 것이라 그대로)
        plan = plan2
    final_sec = moved or section

    raw = w.get("반응") if w else None
    reaction = check_reaction(raw, source, eff) if w else None
    if not reaction and not (eff in REASK_KINDS and raw in ("", None) and w):   # 빈 반응(프롬프트가 허용)은 그대로 없음
        reaction = FALLBACK_REACTION.get(eff)
    if held and eff in NO_REACTION_HELD:
        reaction = None   # [Q-114] 담았다는 문구 + 다시 묻는 질문만
    q = check_question(w.get("질문"), source, asked) if w else None

    if w and w.get("더묻기") is True and q and _can_follow(program, answers, eff, {**cur, "section": final_sec}):
        step = _follow_step(plan, placed, final_sec, q, junior)
    else:
        step = dict(plan)
        if q and w.get("더묻기") is not True and not step.get("done") and not step.get("junior") \
                and not step.get("retry") and _qn(q) != _qn(step.get("question")):   # 꼬리 질문 글을 다른 질문 자리에 쓰지 않는다
            mem["asked"][_h(q)] = {"q": step["question"]}
            step["question"] = q
    text = " ".join(x for x in (reaction, HELD_TEXT if held else None) if x)
    if text:
        step["reaction"] = text
    step["heard"] = {"kind": eff, "section": final_sec if eff == "답" else None}
    rec = {"k": eff, **({"s": moved} if moved else {}), **({"p": left} if left else {})}
    return _remember(me, program, mem, last, turn, rec, step, held)


def _repeats(step, asked):
    """[Q-116] 다음 질문이 이번 대화에서 이미 물은 질문(원문·화면 글)과 같은가. 끝·후배 질문·말머리 다시묻기는 아님."""
    import interview as iv
    if step.get("done") or step.get("junior") or step.get("retry"):
        return False
    q = step.get("question") or ""
    return bool(q) and (_qn(q) in asked or _qn(iv._unwrap(q)) in asked)


def _remember(me, program, mem, last, turn, rec, step, held):
    if held:
        step["heldQuestionId"] = held
    mem["said"][_said_key(last)] = rec
    mem["last"] = {"key": turn, "step": step}
    try:
        save(me, program, mem)
    except (OSError, RuntimeError) as e:   # 기록 실패가 인터뷰를 막지 않게(다음 턴은 그 말을 답으로 센다)
        print(f"[vcc] tellChat 기록 실패: {type(e).__name__}")
    return step


def _can_follow(program, answers, eff, cur):
    """한 번 더 물어도 되나: 답이고, 그 칸(후배 질문은 그 질문)의 첫 답이고, 방금 질문이 꼬리 질문이 아닐 때."""
    import interview as iv
    if eff != "답" or (cur.get("question") or "").startswith(iv.JUNIOR_FOLLOW):
        return False
    placed = iv._place_all(program, iv._clean_answers(answers))
    me_ = placed[-1] if placed else {}
    live = [a for a in placed if a.get("answer") and not a.get("skipped")]
    if iv.is_junior(me_):
        return len([a for a in live if iv.is_junior(a) and iv._junior_key(a) == iv._junior_key(me_)]) == 1
    sec = cur.get("section")
    return len([a for a in live if a.get("section") == sec and not iv.is_junior(a)]) == 1


def _follow_step(plan, placed, section, q, junior):
    import interview as iv
    step = {"done": False, "section": section, "question": q, "followUp": True, "progress": plan.get("progress"),
            "pendingQuestions": plan.get("pendingQuestions", 0), "covered": plan.get("covered", [])}
    if junior:   # 지금 후배 질문 꼬리와 같은 모양(머리말 + questionId·asked) — _place_all이 같은 묶음으로 잇는다
        step["question"] = iv.JUNIOR_FOLLOW + q
        step["asked"] = placed.get("asked", "")
        if placed.get("questionId"):
            step["questionId"] = placed["questionId"]
    return step


# ── AI ①: 말판정(HCX) ────────────────────────────────────────────────
def judge(section, question, said, before=None):
    """(종류, 궁금 글 또는 None) 또는 None(호출 실패·형식 오류)."""
    import interview as iv
    ctx = f"BOO: {before.get('question') or ''} / 선배: {before.get('answer') or '(건너뜀)'}" if before else "(없음)"
    r = iv._call("말판정", f"칸: {section or '–'}\n질문: {question}\n앞 대화: {ctx}\n선배가 방금 한 말: {said}\n출력:")
    got = parse_judge(r.get("json") if r.get("ok") else None)
    return fix_kind(*got, said) if got else None


def parse_judge(j):
    """말판정 JSON → (종류, 궁금 또는 None) 또는 None(형식 오류).
    [Q-131] 종류가 6종 밖인데 궁금 글이 있으면(S25 {"종류":"궁금",…}) 되물음으로 받는다 — 폴백하면 질문함을 놓친다."""
    if not isinstance(j, dict):
        return None
    c = j.get("궁금")
    c = c.strip() if isinstance(c, str) else ""
    c = c if c and c.lower() != "null" else None
    kind = j.get("종류")
    if kind not in KINDS:
        if not c:
            return None
        kind = "되물음"
    return kind, c


def fix_kind(kind, curious, said):
    """[Q-131] 말판정 결과를 코드가 바로잡는다 — 말 전체가 정해진 모양일 때만(정상 답을 덮지 않게).
    부호뿐(「?」) → 되물음(물음표가 없으면 부족), 「지난번에 다 말했어요」·「후배들도 궁금해할 것 같아요」 → 부족,
    짧은 「…모르겠어요」(앞에 다른 내용·숫자 없음) → 모름. 「네?」 → 되물음(궁금 없음).
    부족·딴얘기인데 숫자가 든 말(지시·연락처 아님) → 답(다른 칸 이야기는 대화쓰기 칸으로 옮겨짐)."""
    s = (said or "").strip()
    if s and _PUNCT_ONLY.fullmatch(s):
        return ("되물음" if ("?" in s or "？" in s) else "부족"), None
    n = _qn(s)
    if ("?" in s or "？" in s) and n in _BARE_ASK:
        return "되물음", None
    if kind in ("부족", "딴얘기") and re.search(r"\d", s) and not _ORDER.search(s) and not _CONTACT.search(s):
        return "답", curious
    if kind != "답":
        return kind, curious
    if not n or re.search(r"\d", n):
        return kind, curious
    if _NO_CONTENT.fullmatch(n):
        return "부족", curious
    end = next((e for e in _DONT_KNOW_END if n.endswith(e)), None)
    if end and len(n) <= MAX_DONT_KNOW and not _CONTRAST.search(n[:-len(end)]):
        return "모름", curious
    return kind, curious


def bare_deictic(text):
    """[Q-114] 궁금 글이 지시어뿐인가(「나도 그게 궁금했는데」): 지시어가 있고, 지시어·궁금 표현·맞장구를 빼면 남는 낱말이 없음."""
    words = [w for w in re.split(r"[\s.,!?~…·\"'「」]+", text or "") if w]
    if not any(_DEICTIC.search(w) for w in words):
        return False
    return not [w for w in words if not _DEICTIC.search(w) and not _FILLER.search(w)]


def _clip(s, n):
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def hold_question(me, program, curious, said, asked=None):
    """⑥ 궁금 → 내 질문함(hold). #369 관문(askboo._save)에 걸리거나 담을 글이 없으면 None.
    [Q-114] 궁금 글이 지시어뿐이면 무엇이 궁금한지 알 수 있게 「(BOO 질문) 선배 말」로 담는다(BOO 질문 60자 말줄임)."""
    text = curious.strip()
    if _META.search(text):
        return None
    if askboo._norm(text) not in askboo._norm(said):   # 선배 말 그대로가 아니면(AI가 바꿔 씀) 말 전체 — 짧을 때만
        text = said.strip() if len(said.strip()) <= MAX_CURIOUS else ""
    if not text:
        return None
    if bare_deictic(text) and (asked or "").strip():
        from interview import JUNIOR_FOLLOW
        ask = (asked or "").strip()
        ask = ask[len(JUNIOR_FOLLOW):].strip() if ask.startswith(JUNIOR_FOLLOW) else ask
        text = f"({_clip(ask, MAX_HELD_ASK)}) {text}"
    from demand import guess_section
    qid, blocked = askboo._save(me, text, program, guess_section(text, program), "hold", True)
    return None if blocked else qid


# ── AI ②: 대화쓰기(Sonnet) ───────────────────────────────────────────
def _turn_text(a):
    q = (a.get("question") or "").strip()
    sec = a.get("section")
    said = "(건너뜀)" if a.get("skipped") else (a.get("answer") or "")[:MAX_TURN_CHARS]
    return f"BOO: {f'[{sec}] ' if sec else ''}{q}\n선배: {said}"


def _write_input(me, program, items, prev, cur, section, eff, can_follow, plan, prior, mine):
    import interview as iv
    sections = iv.sections_of(program)
    placed = iv._place_all(program, iv._clean_answers(prev + ([cur] if eff == "답" else [])))
    answered = {a.get("section") for a in placed if a.get("answer") and not a.get("skipped")} | set(prior["sections"])
    lines = [f"[{s.get('name')}] {ln.get('text')}" for s in ((mine or {}).get("myNote") or {}).get("sections", [])
             for ln in s.get("lines") or [] if ln.get("text")][:PRIOR_LINES]
    asked_now = {iv.depth_id(a.get("question")) for a in prev + [cur]}
    cands = [f"[{s}] {q}" for i, s, q, _ in iv.depth_questions(program, sections, before=prior["depth"]) if i not in asked_now]
    seen = {a.get("questionId") for a in placed if a.get("questionId")} | set(prior["questionIds"])
    cands += [f"후배 질문 — \"{q['질문']}\"" for q in iv.junior_questions(me, program) if q["id"] not in seen]
    if plan.get("done"):
        nxt = "(끝)"
    elif plan.get("junior"):
        nxt = f"후배 질문 — \"{plan.get('asked', '')}\""
    else:
        nxt = f"[{plan.get('section')}] {plan.get('question')}"
    history = [_turn_text(a) for a in items[:-1]][-HISTORY_TURNS:]
    return (f"프로그램: {iv.short_name(program)} ({iv.kind_of(program)})\n"
            f"노트 칸: {', '.join(sections)}\n"
            f"아직 안 채운 칸: {', '.join(s for s in sections if s not in answered) or '(없음)'}\n"
            "지난 노트 문장:" + ("\n" + "\n".join("- " + x for x in lines) if lines else " (없음)") + "\n"
            "남은 질문 후보:" + ("\n" + "\n".join("- " + x for x in cands) if cands else " (없음)") + "\n"
            "지금까지의 대화:" + ("\n" + "\n".join(history) if history else " (없음)") + "\n"
            f"방금 BOO의 질문: {f'[{section}] ' if section else ''}{items[-1].get('question') or ''}\n"
            f"선배가 방금 한 말: {items[-1].get('answer', '')[:MAX_TURN_CHARS * 2]}\n"
            f"방금 말의 종류: {eff}\n"
            f"더 물을 수 있음: {'예' if can_follow else '아니오'}\n"
            f"다음 질문: {nxt}\n출력:")


def write(content):
    import interview as iv
    r = iv._call("대화쓰기", content)
    j = r.get("json") if r.get("ok") else None
    return j if isinstance(j, dict) else None


# ── 코드 검증 ─────────────────────────────────────────────────────────
def facts_outside(text, source):
    """대화·후보에 없는 숫자·영문·고유명사. 수량(「한 장면」)·새 낱말은 보지 않는다."""
    return [p for p in askboo.verify(text, source) if p.split(" ")[0] in ("숫자", "영문", "고유명사")]


def check_reaction(text, source, kind=None):
    """해요체 1~3문장, 120자 안, 근거 밖 사실 없음, 화면 기능 말 없음. 통과하면 다듬은 글, 아니면 None.
    [Q-114] 부족·되물음·딴얘기면 평가하는 말(_EVAL)도 없어야 한다(답의 반응은 선배 말을 받는 글이라 보지 않음)."""
    if not isinstance(text, str):
        return None
    t = " ".join(text.split())
    if not t or len(t) > MAX_REACTION or _FEATURE.search(t) or (kind in REASK_KINDS and _EVAL.search(t)):
        return None
    parts = [x for x in re.split(r"(?<=[.!?~])\s+", t) if x]
    if len(parts) > MAX_SENTENCES or not all(_END.search(x) for x in parts) or facts_outside(t, source):
        return None
    return t


def check_question(text, source, asked=()):
    """60자 안, 「요?/까?」로 끝남, 근거 밖 사실 없음, 이번 인터뷰에서 물은 질문이 아님. 통과하면 다듬은 글, 아니면 None."""
    if not isinstance(text, str):
        return None
    t = " ".join(text.split())
    if t and not _ASK_END.search(t):
        # [Q-131 재측정] 「…들려주세요. 어떤 일이든 괜찮아요.」 — 질문 뒤 덧붙인 문장은 떼고 질문까지만(S25 질문 버림 → 원문 되풀이)
        parts = [x for x in re.split(r"(?<=[.!?~])\s+", t) if x]
        while parts and not _ASK_END.search(parts[-1]):
            parts.pop()
        t = " ".join(parts)
    if not t or len(t) > MAX_QUESTION or not _ASK_END.search(t) or facts_outside(t, source) or _qn(t) in asked:
        return None
    return t

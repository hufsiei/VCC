# 정답률·보류율 측정 + 모델 비교 (원우 담당, 작업 30·36)
#
# 사용 (저장소 폴더에서):
#   python tools/run_eval.py                              # 개발 질문 70개, PROVIDER 표 그대로
#   python tools/run_eval.py --model hcx,sonnet,opus      # askBoo의 고르기·변환 모델만 바꿔 차례로 측정
#   python tools/run_eval.py --questions <봉인 xlsx> --out <저장소 밖 폴더> --model hcx,sonnet
#   python tools/run_eval.py --all90 --model hcx,sonnet --pause 4 # [11/25 작업 88] 개발 70 + 다중 턴·탐색·대화 20 = 90개
#   python tools/run_eval.py --dry                        # AI 없이 흐름만 시험(고르기=1·2번, 답쓰기=1번 근거 옮기기(cites 2개), 변환=폴백)
#   python tools/run_eval.py --merge <질문별 csv 여러 개>         # 나눠 돌린 결과를 합쳐 요약(같은 모델끼리)
#   python tools/run_eval.py --model hcx --only 1-15 --pause 4   # 번호 범위 + 문항 사이 4초(HCX 테스트 키 분당 60요청 ≈ 분당 15문항, HCX 원칙 8절)
#   python tools/run_eval.py --model hcx --why                   # [11/23] 폴백 줄마다 원인(호출 실패·JSON 형식·말투·검증 종류)과 AI 원래 출력을 따로 저장
#
# - askBoo를 그대로 부른다(save=False, 질문함에 저장 안 함). 모델 비교는 실행 중에만 ai.PROVIDER의
#   '고르기'·'변환'을 바꾼다 — functions/ 파일은 고치지 않는다. 키는 ai.py가 .env에서 읽는다.
# - 봉인 질문은 저장소에 두지 않는다: 질문 파일에 '봉인' 값이 있으면 --out이 저장소 밖이어야 실행한다.
#   봉인 세트는 1차(30)·최종(36) 측정 때만 돌리고, 결과를 보고 프롬프트를 고치지 않는다.
# - 지표(PRD 1-2): 근거 없는 답변 0건 · 범위밖·함정 100% 보류 · 동의어 80% 이상 답변 · 규정오해 100% 공식 안내.
#   근거 없는 답변 = 답한 줄 중 askboo.verify에 걸린 줄(숫자·고유명사·새 낱말)이 하나라도 있는 답, 또는 보류·공식안내여야 하는데 답한 것.
#   보류·답변·공식안내 비율은 '유형'이 아니라 '기대결과'로 센다(함정 중에도 답해야 하는 질문이 있음).
#   [11/23] askBoo의 notes(해봤노트 카드 안내)는 '답하지 않음' — 기대 보류면 맞음, 근거 없는 답 아님(위 NOT_ANSWER).
#   근거 적중 = 답변 기대 질문에서 답한 줄의 출처 중 하나라도 '기대 근거ID'에 들어 있음(참고 지표).
#   [11/25 작업 88] v2: 답쓰기 줄은 cites 전체를 이은 원문과 대조(askboo.verify_facts — 뜻 일치는 서버의 답검사가 이미 봄),
#   폴백 줄은 예전처럼 verify(새 낱말까지). cites가 없거나 근거에 없는 ID면 「cites없음」(S10: 답 문장 전부 cites).
#   기대결과 대화(chat)·노트안내(notes)는 그 상태여야 맞음. 대화·노트안내 기대인데 hold·official이면 「질문함저장」(S10: 0건).
#   제외 프로그램이 답 근거나 카드에 나오면 「제외위반」, 관련 프로그램 밖이 나오거나 카드가 비면 「프로그램」 X(둘 다 틀림으로 센다).
#   --model은 예전처럼 고르기·변환만 바꾼다(질문정리·답쓰기·답검사는 PROVIDER 표 그대로).
# 결과: <out>/eval_<질문파일>_<모델>_<시각>.csv (질문별) + eval_요약_<시각>.csv (모델별)
#   --why면 + eval_폴백_<질문파일>_<모델>_<시각>.csv (폴백 줄별: 번호·원문·AI출력·원인). askBoo 동작은 바꾸지 않고,
#   변환 호출의 응답을 옆에서 받아 askboo.convert와 같은 순서(응답 실패 → JSON → 해요체 끝 → verify)로 원인만 붙인다.
#   사후 검증 규칙(askboo.verify)은 그대로 쓴다 — 약하게 만들지 않는다.
import argparse, csv, json, re, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "functions"))
import paths  # noqa: E402

EXPECT = {"답변": "ok", "보류": "hold", "공식안내": "official", "대화": "chat", "노트안내": "notes"}
STATUS = {"답함": "ok", "보류": "hold", "공식 안내": "official", "노트 안내": "notes", "대화": "chat"}   # 이전대화 열
NO_CARD = "(카드 없음)"
# [11/23] askBoo 새 상태 notes(spec 4장 [11/23 노트]): 사람·나라만 묻고 주제가 없으면 답 대신 해봤노트 카드로 안내.
#   답을 만들지 않으므로 근거 없는 답이 아니고, '답하지 않음' 쪽이라 기대가 보류면 맞은 것으로 센다(보류율에도 넣음).
#   기대가 답변·공식안내면 틀림(답하거나 공식 안내로 보내야 했음). notes 건수는 요약에 따로 적는다.
NOT_ANSWER = ("hold", "notes")


def matches(want, got):
    return got == want or (want == "hold" and got in NOT_ANSWER)


def read_history(text):
    """이전대화 열: 「질문 → 상태 → 프로그램」을 ' // '로 이음 → askBoo history(화면이 보내는 모양)."""
    out = []
    for turn in (text or "").split(" // "):
        if not turn.strip():
            continue
        part = [x.strip() for x in turn.split("→")]
        if len(part) < 2 or part[1] not in STATUS:
            sys.exit(f"이전대화 형식을 확인해 주세요: {turn}")
        h = {"question": part[0], "status": STATUS[part[1]]}
        if len(part) > 2 and part[2]:
            h["program"] = part[2]
        out.append(h)
    return out


def evidence_pool(askboo):
    """{id: {"text"}} — evidence.json + 동의 통과 인터뷰 문장(runtime/noteLines). askBoo가 둘 다 근거로 쓰므로
    인터뷰 문장을 빼면 맞는 답을 「근거 없음」으로 센다(11/25). 같은 인터뷰 id에 문장이 여럿이면 이어 붙인다."""
    pool = {e["id"]: {"text": e["text"]} for rs in askboo.EVIDENCE.values() for e in rs}
    n = 0
    for name in askboo.PROGRAMS:
        for r in askboo.notes.interview_lines(name):
            old = pool.get(r["id"], {}).get("text", "")
            pool[r["id"]] = {"text": f"{old} {r['text']}".strip()}
            n += 1
    if n:
        print(f"동의 통과 인터뷰 문장 {n}개도 근거로 함께 봄(이 PC의 runtime — 봉인 측정 전 동결 상태인지 확인)")
    return pool


def check_lines(lines, evid, askboo):
    """돌려주는 값: (근거 밖 줄 목록, cites가 없거나 모르는 ID인 줄 수)"""
    bad, no_cites = [], 0
    for ln in lines:
        cites = ln.get("cites") or []
        if not cites or any(c not in evid for c in cites):
            no_cites += 1
        src = " ".join(evid.get(c, {}).get("text", "") for c in cites or [ln["sourceId"]])
        probs = askboo.verify(ln["text"], src) if ln.get("fallback") else askboo.verify_facts(ln["text"], src)
        if probs:
            bad.append(f"{ln['text']} ← {probs}")
    return bad, no_cites


def check_programs(r, res):
    """다중 턴 질문: (제외 위반 목록, 프로그램 칸 O/X/빈칸). 제외·관련 프로그램은 ' / '로 이음."""
    if "이전대화" not in r:
        return [], ""
    split = lambda k: {x.strip() for x in (r.get(k) or "").split(" / ") if x.strip()}
    got = {s.get("program") for s in (res.get("sources") or {}).values()} | {c.get("program") for c in res.get("notes") or []}
    excl, want = sorted(split("제외 프로그램") & got), split("관련 프로그램")
    if res.get("status") not in ("ok", "notes"):
        return excl, ""
    if NO_CARD in want:
        return excl, "X" if got else "O"
    return excl, "O" if got and (not want or got <= want) else "X"


TASKS = ("고르기", "변환")   # askBoo가 부르는 AI 작업


def read_questions(path):
    if path.suffix.lower() == ".xlsx":
        import openpyxl
        ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
        head = [str(h or "").strip() for h in rows[0]]
        out = [{h: ("" if v is None else str(v).strip()) for h, v in zip(head, r)} for r in rows[1:]]
    else:
        with open(path, encoding="utf-8-sig") as f:
            out = list(csv.DictReader(f))
    return [r for r in out if r.get("질문") and r.get("기대결과") in EXPECT]


def inside(p, root):
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def dry_call(작업명, messages, system=None, **_):
    """AI 없이 흐름만. 답쓰기는 1번 근거의 한 문장을 그대로 옮기고 근거 번호를 있는 만큼(최대 2개) 단다 — cites 여러 개 대조 시험용.
    1번 근거에 존댓말 문장이 없으면 실패로 두어 폴백 줄도 함께 지나간다."""
    if 작업명 == "답쓰기":
        rows = re.findall(r"^\[(\d+)\] [^:\n]*: (.+)$", messages[-1]["content"], re.M)
        ends = [x for x in re.split(r"(?<=[.!?])\s+", rows[0][1]) if re.search(r"(요|니다)[.!?~]*$", x)] if rows else []
        if ends:
            j = {"답": [{"text": ends[0], "근거": [int(n) for n, _t in rows[:2]]}]}
            return {"ok": True, "text": json.dumps(j, ensure_ascii=False), "json": j, "model": "dry"}
    if 작업명 == "답검사":
        return {"ok": True, "text": '{"일치":true}', "json": {"일치": True}, "model": "dry"}
    if 작업명 == "고르기":
        return {"ok": True, "text": '{"관련":[1,2]}', "json": {"관련": [1, 2]}, "model": "dry"}
    return {"ok": False, "text": "", "json": None, "model": "dry", "error": "dry"}


class WhyLog:
    """[11/23] 폴백 원인 기록. askboo._call·convert를 감싸 응답과 결과만 엿본다(동작은 그대로)."""

    def __init__(self, askboo):
        self.a, self.items, self.last = askboo, [], None
        orig_call, orig_convert = askboo._call, askboo.convert
        self._orig = (orig_call, orig_convert)

        def call(작업명, content):
            r = orig_call(작업명, content)
            if 작업명 == "변환":
                self.last = r
            return r

        def convert(source):
            self.last = None
            text, fb = orig_convert(source)
            if fb:
                self.items.append({"원문": source, "AI출력": self.raw(), "원인": self.reason(source)})
            return text, fb

        askboo._call, askboo.convert = call, convert

    def restore(self):
        self.a._call, self.a.convert = self._orig

    def raw(self):
        r = self.last or {}
        return (r.get("text") or r.get("error") or "")[:300]

    def reason(self, source):
        r, a = self.last, self.a
        if not r or not r.get("ok"):
            return "호출 실패"
        j = r.get("json")
        v = None
        if isinstance(j, dict) and len(j) >= 1:
            v = j.get("1", next(iter(j.values())))
        if not isinstance(v, str) or not v.strip():
            return "JSON 형식"
        v = v.strip()
        if not a.POLITE_END.search(v):
            return "말투(해요체 끝 아님)"
        probs = a.verify(v, source)
        return "검증: " + " / ".join(probs) if probs else "알 수 없음"

    @staticmethod
    def kind(reason):
        """원인 분류(요약용): 검증은 종류 이름만(숫자·영문·수량·고유명사·새 낱말·원문보다 많이 김)."""
        if not reason.startswith("검증: "):
            return [reason]
        return sorted({p.split(" ")[0] if not p.startswith(("새 낱말", "원문보다")) else
                       ("새 낱말" if p.startswith("새 낱말") else "원문보다 김") for p in reason[4:].split(" / ")})


def run(rows, model, askboo, pause=0.0, why=None):
    import ai
    saved = {t: ai.PROVIDER[t] for t in TASKS}
    if model not in ("표", "dry"):
        for t in TASKS:
            ai.PROVIDER[t] = model
    evid = evidence_pool(askboo)
    out = []
    try:
        for r in rows:
            t0 = time.time()
            n_why = len(why.items) if why else 0
            res = askboo.askBoo("eval", {"question": r["질문"], "history": read_history(r.get("이전대화"))}, save=False)
            sec = round(time.time() - t0, 1)
            got = res.get("status", "error")
            lines = res.get("lines", [])
            bad, no_cites = check_lines(lines, evid, askboo)
            excl, prog = check_programs(r, res)
            want = EXPECT[r["기대결과"]]
            expect_ids = {s.strip() for s in (r.get("기대 근거ID") or "").split(",") if s.strip()}
            used = {c for ln in lines for c in (ln.get("cites") or [ln["sourceId"]])}
            out.append({
                "번호": r["번호"], "모델": model, "유형": r.get("유형", ""), "기대결과": r["기대결과"], "결과": got,
                "일치": "O" if matches(want, got) and not excl and prog != "X" else "X",
                "근거없는답": "O" if got == "ok" and (bad or no_cites or want in ("hold", "official")) else "",
                "근거적중": ("O" if used & expect_ids else "X") if want == "ok" and got == "ok" and expect_ids else "",
                "줄수": len(lines), "폴백줄": sum(bool(ln.get("fallback")) for ln in lines),
                "cites2개이상": sum(len(ln.get("cites") or []) >= 2 for ln in lines), "cites없음": no_cites, "질문함저장": "O" if want in ("chat", "notes") and got in ("hold", "official") else "",
                "제외위반": ", ".join(excl), "프로그램": prog,
                "근거밖줄": " / ".join(bad), "초": sec,
                "질문": r["질문"], "답": " / ".join(ln["text"] for ln in lines),
                "출처": ", ".join(sorted(used)), "보류이유": res.get("_why", ""),
            })
            if why:
                for it in why.items[n_why:]:
                    it["번호"] = r["번호"]
                out[-1]["폴백원인"] = " / ".join(it["원인"] for it in why.items[n_why:])
            print(f"  {out[-1]['일치']} {r['번호']:>3} [{r['기대결과']}/{r.get('유형','')}] → {got} ({sec}초)"
                  + (f"  cites≥2 {out[-1]['cites2개이상']}줄" if out[-1]["cites2개이상"] else "")
                  + (f"  ⚠ 근거밖 {len(bad)}줄" if bad else "") + (f"  ⚠ cites 없음 {no_cites}줄" if no_cites else ""))
            if pause:
                time.sleep(pause)
    finally:
        for t, v in saved.items():
            ai.PROVIDER[t] = v
    return out


def rate(rows, cond, ok):
    sel = [r for r in rows if cond(r)]
    return (sum(ok(r) for r in sel), len(sel))


def summary(model, out):
    f = lambda pair: f"{pair[0]}/{pair[1]}" + (f" ({pair[0] / pair[1]:.0%})" if pair[1] else "")
    s = {
        "모델": model, "질문수": len(out),
        "정답률": f(rate(out, lambda r: True, lambda r: r["일치"] == "O")),
        "보류율": f(rate(out, lambda r: True, lambda r: r["결과"] in NOT_ANSWER)),   # notes(노트 안내) 포함
        "대화·노트안내 일치": f(rate(out, lambda r: r["기대결과"] in ("대화", "노트안내"), lambda r: r["일치"] == "O")),
        "대화·탐색 질문함저장(0건)": sum(r.get("질문함저장") == "O" for r in out),
        "cites2개이상줄": sum(int(r.get("cites2개이상") or 0) for r in out),
        "cites없는줄(0건)": sum(int(r.get("cites없음") or 0) for r in out),
        "제외위반": sum(bool(r.get("제외위반")) for r in out),
        "오류": sum(r["결과"] == "error" for r in out),
        "노트안내": sum(r["결과"] == "notes" for r in out),
        "근거없는답(0건)": sum(r["근거없는답"] == "O" for r in out),
        # 유형이 아니라 기대결과로 센다 — 함정 중에도 답해야 하는 별칭 질문이 있다(개발 35 '파리 제7대학교')
        "범위밖·함정 보류(100%)": f(rate(out, lambda r: r["기대결과"] == "보류", lambda r: r["결과"] in NOT_ANSWER)),
        "동의어 답변(80%)": f(rate(out, lambda r: r["기대결과"] == "답변", lambda r: r["결과"] == "ok")),
        "규정오해 공식안내(100%)": f(rate(out, lambda r: r["기대결과"] == "공식안내", lambda r: r["결과"] == "official")),
        "근거적중(참고)": f(rate(out, lambda r: r["근거적중"], lambda r: r["근거적중"] == "O")),
        "폴백줄/전체줄": f"{sum(r['폴백줄'] for r in out)}/{sum(r['줄수'] for r in out)}",
        "평균초": round(sum(r["초"] for r in out) / max(len(out), 1), 1),
    }
    return s


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(ROOT / "data" / "eval-questions.csv"))
    ap.add_argument("--all90", action="store_true", help="--questions 뒤에 다중 턴·탐색·대화 20개(data/eval-questions-multi.csv)를 이어 90개로")
    ap.add_argument("--model", default="표", help="표(PROVIDER 그대로) 또는 hcx,sonnet,opus 쉼표 구분")
    ap.add_argument("--out", default=str(paths.LOGS))
    ap.add_argument("--only", default="", help="번호만 골라 실행(쉼표·범위: 1-15,23)")
    ap.add_argument("--pause", type=float, default=0.0, help="문항 사이 쉬는 초(호출 한도 대비)")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--why", action="store_true", help="폴백 줄 원인·AI 원래 출력을 eval_폴백_*.csv로 따로 저장")
    ap.add_argument("--merge", nargs="+", help="질문별 결과 csv들을 합쳐 요약만 출력·저장")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # 한글 콘솔(cp949)에서도 출력이 깨지지 않게

    if a.merge:
        rows = []
        for f in a.merge:
            with open(f, encoding="utf-8-sig") as fh:
                part = list(csv.DictReader(fh))
            if part and "모델" not in part[0]:
                sys.exit(f"모델 열이 없는 옛 결과 파일입니다: {f}")
            for r in part:
                for k in ("줄수", "폴백줄"):
                    r[k] = int(r[k] or 0)
                r["초"] = float(r["초"] or 0)
            rows += part
        sums = []
        for m in sorted({r["모델"] for r in rows}):          # 모델이 섞여 있으면 모델별로 따로 요약
            seen = {}
            for r in rows:
                if r["모델"] == m:
                    seen[r["번호"]] = r                        # 같은 번호가 두 번이면 나중 것
            sums.append(summary(m, list(seen.values())))
        out = Path(a.merge[0]).parent / f"eval_요약_합침_{datetime.now().strftime('%Y%m%d-%H%M')}.csv"
        write_csv(out, sums)
        for s_ in sums:
            print(json.dumps(s_, ensure_ascii=False))
        print(f"저장: {out}")
        return

    qpath, out_dir = Path(a.questions), Path(a.out)
    rows = read_questions(qpath)
    stem = qpath.stem
    if a.all90:
        rows += read_questions(ROOT / "data" / "eval-questions-multi.csv")
        stem += "+multi"
    if len({r["번호"] for r in rows}) != len(rows):
        sys.exit("번호가 겹치는 질문이 있습니다(--merge가 같은 번호를 하나로 셉니다).")
    for r in rows:
        read_history(r.get("이전대화"))   # 형식 오류는 AI를 부르기 전에 찾는다
    if a.only:
        keep = set()
        for part in a.only.split(","):
            part = part.strip()
            if "-" in part:
                lo, hi = part.split("-", 1)
                if not (lo.strip().isdigit() and hi.strip().isdigit()):
                    sys.exit(f"--only 범위는 숫자-숫자로 적어 주세요: {part}")
                keep |= {str(n) for n in range(int(lo), int(hi) + 1)}
            elif part:
                keep.add(part)
        rows = [r for r in rows if r["번호"] in keep]
    sealed = "봉인" in qpath.name or any((r.get("봉인") or "").strip() for r in rows)
    if sealed and (inside(out_dir, ROOT) or inside(out_dir, paths.MAIN_ROOT)):
        sys.exit("봉인 질문 결과는 저장소 밖 폴더에만 저장합니다. --out에 저장소 밖 경로를 주세요.")

    import askboo
    if a.dry:
        askboo.callAI = dry_call
    models = ["dry"] if a.dry else [m.strip() for m in a.model.split(",") if m.strip()]
    wrong = [m for m in models if m not in ("표", "dry", "hcx", "sonnet", "opus", "claude")]
    if wrong or not rows:
        sys.exit(f"모델 이름 확인: {wrong}" if wrong else "측정할 질문이 없습니다(질문·기대결과 열 확인).")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M") + (f"_{a.only.replace(',', '+')}" if a.only else "")
    sums = []
    for m in models:
        print(f"[{m}] {stem} {len(rows)}개")
        why = WhyLog(askboo) if a.why else None
        out = run(rows, m, askboo, 0 if a.dry else a.pause, why)
        write_csv(out_dir / f"eval_{stem}_{m}_{stamp}.csv", out)
        s = summary(m, out)
        # 근거 없는 답은 한 건이라도 있으면 화면과 파일에 따로 표시한다(S1·S10: 0건)
        alone = [r for r in out if r["근거없는답"] == "O" or r["근거밖줄"] or r["cites없음"]]
        if alone:
            path = out_dir / f"eval_근거없음_{stem}_{m}_{stamp}.csv"
            write_csv(path, [{k: r[k] for k in ("번호", "모델", "기대결과", "결과", "질문", "답", "출처", "근거밖줄", "cites없음")} for r in alone])
            print(f"⚠ 근거 확인이 필요한 답 {len(alone)}건: {', '.join(r['번호'] for r in alone)} → {path.name}")
        else:
            print("근거 없는 답 0건 · 근거 밖 줄 0 · cites 없는 줄 0")
        if why:
            from collections import Counter
            cnt = Counter(k for it in why.items for k in WhyLog.kind(it["원인"]))
            s["폴백원인"] = " · ".join(f"{k} {n}" for k, n in cnt.most_common())
            write_csv(out_dir / f"eval_폴백_{stem}_{m}_{stamp}.csv",
                      [{"번호": it["번호"], "모델": m, "원인": it["원인"], "원문": it["원문"], "AI출력": it["AI출력"]}
                       for it in why.items])
            why.restore()   # 다음 모델에서 겹쳐 감싸지 않게
        sums.append(s)
    write_csv(out_dir / f"eval_요약_{stem}_{stamp}.csv", sums)
    print()
    for s in sums:
        print(json.dumps(s, ensure_ascii=False))
    print(f"\n저장: {out_dir}")


if __name__ == "__main__":
    main()

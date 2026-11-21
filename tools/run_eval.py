# 정답률·보류율 측정 + 모델 비교 (원우 담당, 작업 30·36)
#
# 사용 (저장소 폴더에서):
#   python tools/run_eval.py                              # 개발 질문 70개, PROVIDER 표 그대로
#   python tools/run_eval.py --model hcx,sonnet,opus      # askBoo의 고르기·변환 모델만 바꿔 차례로 측정
#   python tools/run_eval.py --questions <봉인 xlsx> --out <저장소 밖 폴더> --model hcx,sonnet
#   python tools/run_eval.py --dry                        # AI 없이 흐름만 시험(고르기=1번, 변환=폴백)
#
# - askBoo를 그대로 부른다(save=False, 질문함에 저장 안 함). 모델 비교는 실행 중에만 ai.PROVIDER의
#   '고르기'·'변환'을 바꾼다 — functions/ 파일은 고치지 않는다. 키는 ai.py가 .env에서 읽는다.
# - 봉인 질문은 저장소에 두지 않는다: 질문 파일에 '봉인' 값이 있으면 --out이 저장소 밖이어야 실행한다.
#   봉인 세트는 1차(30)·최종(36) 측정 때만 돌리고, 결과를 보고 프롬프트를 고치지 않는다.
# - 지표(PRD 1-2): 근거 없는 답변 0건 · 범위밖·함정 100% 보류 · 동의어 80% 이상 답변 · 규정오해 100% 공식 안내.
#   근거 없는 답변 = 답한 줄 중 askboo.verify에 걸린 줄(숫자·고유명사·새 낱말)이 하나라도 있는 답, 또는 보류·공식안내여야 하는데 답한 것.
#   근거 적중 = 답변 기대 질문에서 답한 줄의 출처 중 하나라도 '기대 근거ID'에 들어 있음(참고 지표).
# 결과: <out>/eval_<질문파일>_<모델>_<시각>.csv (질문별) + eval_요약_<시각>.csv (모델별)
import argparse, csv, json, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "functions"))
import paths  # noqa: E402

EXPECT = {"답변": "ok", "보류": "hold", "공식안내": "official"}
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
    if 작업명 == "고르기":
        return {"ok": True, "text": '{"관련":[1]}', "json": {"관련": [1]}, "model": "dry"}
    return {"ok": False, "text": "", "json": None, "model": "dry", "error": "dry"}


def run(rows, model, askboo):
    import ai
    saved = {t: ai.PROVIDER[t] for t in TASKS}
    if model not in ("표", "dry"):
        for t in TASKS:
            ai.PROVIDER[t] = model
    evid = {e["id"]: e for rs in askboo.EVIDENCE.values() for e in rs}
    out = []
    try:
        for r in rows:
            t0 = time.time()
            res = askboo.askBoo("eval", {"question": r["질문"]}, save=False)
            sec = round(time.time() - t0, 1)
            got = res.get("status", "error")
            lines = res.get("lines", [])
            bad = []
            for ln in lines:
                probs = askboo.verify(ln["text"], evid.get(ln["sourceId"], {}).get("text", ""))
                if probs:
                    bad.append(f"{ln['text']} ← {probs}")
            want = EXPECT[r["기대결과"]]
            expect_ids = {s.strip() for s in (r.get("기대 근거ID") or "").split(",") if s.strip()}
            used = {ln["sourceId"] for ln in lines}
            out.append({
                "번호": r["번호"], "유형": r.get("유형", ""), "기대결과": r["기대결과"], "결과": got,
                "일치": "O" if got == want else "X",
                "근거없는답": "O" if got == "ok" and (bad or want != "ok") else "",
                "근거적중": ("O" if used & expect_ids else "X") if want == "ok" and got == "ok" and expect_ids else "",
                "줄수": len(lines), "폴백줄": sum(bool(ln.get("fallback")) for ln in lines),
                "근거밖줄": " / ".join(bad), "초": sec,
                "질문": r["질문"], "답": " / ".join(ln["text"] for ln in lines),
                "출처": ", ".join(sorted(used)), "보류이유": res.get("why", "") or res.get("reason", ""),
            })
            print(f"  {out[-1]['일치']} {r['번호']:>3} [{r['기대결과']}/{r.get('유형','')}] → {got} ({sec}초)"
                  + (f"  근거밖 {len(bad)}줄" if bad else ""))
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
        "보류율": f(rate(out, lambda r: True, lambda r: r["결과"] == "hold")),
        "근거없는답(0건)": sum(r["근거없는답"] == "O" for r in out),
        "범위밖·함정 보류(100%)": f(rate(out, lambda r: r["유형"] in ("범위밖", "함정"), lambda r: r["결과"] == "hold")),
        "동의어 답변(80%)": f(rate(out, lambda r: r["유형"] == "동의어", lambda r: r["결과"] == "ok")),
        "규정오해 공식안내(100%)": f(rate(out, lambda r: r["유형"] == "규정오해", lambda r: r["결과"] == "official")),
        "근거적중(참고)": f(rate(out, lambda r: r["근거적중"], lambda r: r["근거적중"] == "O")),
        "폴백줄/전체줄": f"{sum(r['폴백줄'] for r in out)}/{sum(r['줄수'] for r in out)}",
        "평균초": round(sum(r["초"] for r in out) / max(len(out), 1), 1),
    }
    return s


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(ROOT / "data" / "eval-questions.csv"))
    ap.add_argument("--model", default="표", help="표(PROVIDER 그대로) 또는 hcx,sonnet,opus 쉼표 구분")
    ap.add_argument("--out", default=str(paths.LOGS))
    ap.add_argument("--only", default="", help="번호만 골라 실행(쉼표 구분)")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    qpath, out_dir = Path(a.questions), Path(a.out)
    rows = read_questions(qpath)
    if a.only:
        keep = {s.strip() for s in a.only.split(",")}
        rows = [r for r in rows if r["번호"] in keep]
    sealed = "봉인" in qpath.name or any((r.get("봉인") or "").strip() for r in rows)
    if sealed and (inside(out_dir, ROOT) or inside(out_dir, paths.MAIN_ROOT)):
        sys.exit("봉인 질문 결과는 저장소 밖 폴더에만 저장합니다. --out에 저장소 밖 경로를 주세요.")

    import askboo
    if a.dry:
        askboo.callAI = dry_call
    models = ["dry"] if a.dry else [m.strip() for m in a.model.split(",") if m.strip()]
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    sums = []
    for m in models:
        print(f"[{m}] {qpath.name} {len(rows)}개")
        out = run(rows, m, askboo)
        write_csv(out_dir / f"eval_{qpath.stem}_{m}_{stamp}.csv", out)
        sums.append(summary(m, out))
    write_csv(out_dir / f"eval_요약_{qpath.stem}_{stamp}.csv", sums)
    print()
    for s in sums:
        print(json.dumps(s, ensure_ascii=False))
    print(f"\n저장: {out_dir}")


if __name__ == "__main__":
    main()

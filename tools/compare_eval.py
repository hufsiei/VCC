# 옛 길 ↔ 새 길 측정 비교 (원우 담당, 작업 88 · 11/26 A안 결정)
#
# run_eval.py가 만든 「질문별 csv」 두 개를 번호로 맞춰 나란히 본다. AI를 부르지 않는다.
#
# 사용 (저장소 폴더에서):
#   python tools/compare_eval.py <옛 길 csv> <새 길 csv>
#   python tools/compare_eval.py old.csv new.csv --names 옛길,A안 --md        # 일지·PR에 붙일 표
#   python tools/compare_eval.py old.csv new.csv --log functions/logs/ai-calls.jsonl   # 질문당 원가까지
#
# - 비교 칸: 정답률 · 근거 없는 답(0건) · 보류율 · 응답 시간(평균·90%·최대) · 질문당 원가.
# - 질문별: 「좋아짐」(X→O) · 「나빠짐」(O→X) · 「근거없는답 새로」 · 시간 차이가 큰 문항.
# - 원가: ai-calls.jsonl에서 각 측정이 돈 시간대(파일명의 시각 ~ 파일 수정 시각)의 호출을 모아
#   ai_usage의 단가로 계산한다. 같은 시간대에 다른 호출이 섞이면 부정확 — 측정 중에는 다른 AI 작업을 하지 않는다.
#   시간대가 틀리면 --old-window / --new-window "2026-11-28T10:00,2026-11-28T10:40"으로 직접 준다.
#   캐시 쓰기·읽기 토큰은 ai_usage 단가에 들어 있다(#306). 원가 칸 끝의 「캐시적중」은 Claude 입력 중
#   캐시에서 읽은 비율 — A안(VCC_ASK_FULL=1)은 같은 프로그램 질문이 5분 안에 이어질수록 오른다. 옛 길은 0%.
# 결과: <out>/compare_요약_<시각>.csv · compare_질문별_<시각>.csv (기본 out = 새 길 csv가 있는 폴더)
import argparse, csv, re, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "functions"))

NOT_ANSWER = ("hold", "notes")
SLOW_GAP = 3.0   # 이 초보다 더 걸리거나 빨라진 문항을 질문별 표에 표시


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows or "번호" not in rows[0] or "일치" not in rows[0]:
        sys.exit(f"run_eval 질문별 csv가 아닙니다: {path}")
    models = {r.get("모델", "") for r in rows}
    if len(models) > 1:
        sys.exit(f"한 파일에 모델이 여럿입니다({', '.join(sorted(models))}): 모델별 파일을 주세요 — {path}")
    return {r["번호"]: r for r in rows}


def sec(r):
    try:
        return float(r.get("초") or 0)
    except ValueError:
        return 0.0


def pct(vals, q):
    if not vals:
        return 0.0
    v = sorted(vals)
    return v[min(len(v) - 1, int(round(q * (len(v) - 1))))]


def window_of(path, given):
    """측정 시간대: 직접 준 값, 아니면 파일명 시각(YYYYMMDD-HHMM) ~ 파일 수정 시각."""
    if given:
        a, b = [x.strip() for x in given.split(",")]
        return datetime.fromisoformat(a), datetime.fromisoformat(b)
    m = re.search(r"_(\d{8}-\d{4})", Path(path).name)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y%m%d-%H%M"), datetime.fromtimestamp(Path(path).stat().st_mtime)


def cost(log, win, n):
    """질문 1건당 원가 문자열. 로그·시간대가 없으면 '–'."""
    if not log or not win or not n:
        return "–"
    import ai_usage
    calls, failed = ai_usage.load_calls(ai_usage.read_log(log), *win)
    if not calls:
        return "– (그 시간대 호출 없음)"
    cl = [c for c in calls if not ai_usage._is_hcx(c["모델"])]
    hcx = len(calls) - len(cl)
    text = ai_usage.money(ai_usage._avg(calls, n), krw=1400)
    return (f"{text} · 1건 평균 Claude {len(cl) / n:.2f}회·HCX {hcx / n:.2f}회 · 캐시적중 {cache_hit(cl)}"
            + (f" · 실패 {sum(failed.values())}" if failed else ""))


def cache_hit(calls):
    """Claude 입력 토큰(캐시 밖 + 쓰기 + 읽기) 중 캐시 읽기 비율."""
    total = sum(c["tin"] + c.get("cw", 0) + c.get("cr", 0) for c in calls)
    return f"{sum(c.get('cr', 0) for c in calls) / total:.0%}" if total else "–"


def summary(name, rows, cost_text):
    rs = list(rows.values())
    n = len(rs)
    secs = [sec(r) for r in rs]
    ok = sum(r["일치"] == "O" for r in rs)
    return {
        "길": name, "질문수": n,
        "정답률": f"{ok}/{n} ({ok / n:.0%})" if n else "–",
        "근거없는답(0건)": sum(r.get("근거없는답") == "O" for r in rs),
        "보류율": f"{sum(r.get('결과') in NOT_ANSWER for r in rs)}/{n}",
        "오류": sum(r.get("결과") == "error" for r in rs),
        "평균초": round(sum(secs) / n, 1) if n else 0,
        "90%초": pct(secs, 0.9), "최대초": max(secs) if secs else 0,
        "질문당원가": cost_text,
    }


def compare(old, new):
    out = []
    for no in sorted(set(old) | set(new), key=lambda x: (len(x), x)):
        a, b = old.get(no), new.get(no)
        if not a or not b:
            out.append({"번호": no, "변화": "한쪽에만 있음", "옛결과": a and a["결과"] or "", "새결과": b and b["결과"] or "",
                        "옛초": a and sec(a) or "", "새초": b and sec(b) or "", "질문": (a or b)["질문"], "새답": b and b.get("답", "") or ""})
            continue
        tags = []
        if a["일치"] == "X" and b["일치"] == "O":
            tags.append("좋아짐")
        if a["일치"] == "O" and b["일치"] == "X":
            tags.append("나빠짐")
        if b.get("근거없는답") == "O" and a.get("근거없는답") != "O":
            tags.append("근거없는답 새로")
        gap = sec(b) - sec(a)
        if abs(gap) >= SLOW_GAP:
            tags.append(f"{'느려짐' if gap > 0 else '빨라짐'} {gap:+.1f}초")
        out.append({"번호": no, "변화": " · ".join(tags), "옛결과": a["결과"], "새결과": b["결과"],
                    "옛초": sec(a), "새초": sec(b), "질문": b["질문"], "새답": b.get("답", "")})
    return out


def write(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def md_table(rows, keys):
    head = "| " + " | ".join(keys) + " |\n|" + "---|" * len(keys)
    return head + "\n" + "\n".join("| " + " | ".join(str(r[k]) for k in keys) + " |" for r in rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--names", default="옛길,새길", help="두 길의 이름(쉼표)")
    ap.add_argument("--log", default="", help="ai-calls.jsonl — 주면 질문당 원가를 낸다")
    ap.add_argument("--old-window", default="")
    ap.add_argument("--new-window", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--md", action="store_true", help="마크다운 표로 출력")
    a = ap.parse_args()

    n_old, n_new = [x.strip() for x in a.names.split(",")]
    old, new = read(a.old), read(a.new)
    sums = [summary(n_old, old, cost(a.log, window_of(a.old, a.old_window), len(old))),
            summary(n_new, new, cost(a.log, window_of(a.new, a.new_window), len(new)))]
    diff = compare(old, new)
    changed = [r for r in diff if r["변화"]]

    out = Path(a.out) if a.out else Path(a.new).resolve().parent
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    write(out / f"compare_요약_{stamp}.csv", sums)
    write(out / f"compare_질문별_{stamp}.csv", diff)

    keys = list(sums[0])
    if a.md:
        print(md_table(sums, keys))
        if changed:
            print("\n" + md_table(changed, ["번호", "변화", "옛결과", "새결과", "옛초", "새초", "질문"]))
    else:
        for s in sums:
            print("  ".join(f"{k} {s[k]}" for k in keys))
        for r in changed:
            print(f"  {r['번호']:>3} {r['변화']}  ({r['옛결과']}→{r['새결과']}, {r['옛초']}→{r['새초']}초) {r['질문']}")
    cnt = lambda t: sum(t in r["변화"] for r in diff)
    print(f"\n좋아짐 {cnt('좋아짐')} · 나빠짐 {cnt('나빠짐')} · 근거없는답 새로 {cnt('근거없는답 새로')} → {out}")


if __name__ == "__main__":
    main()

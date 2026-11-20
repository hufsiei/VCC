# classify_intern.py — 작업 50 현장실습 후기 문장 자동 분류 (작성: 미리)
#
# data/evidence.json에서 현장실습후기 중 칸이 빈 행을 골라 callAI("문단분류")로 칸 하나를 정해 채운다.
# 모델은 functions/ai.py의 PROVIDER 표가 정한다(11/20: sonnet). 프롬프트: docs/prompts/문단분류.txt
#
# 실행:  cd C:\dev\VCC
#        python -X utf8 tools/classify_intern.py --dry-run     # 대상 수·예상 비용만 (AI 호출 없음)
#        python -X utf8 tools/classify_intern.py --limit 20    # 앞 20건만 시험
#        python -X utf8 tools/classify_intern.py               # 전체
#
# 규칙
#   - 고를 수 있는 칸 = frames.json 인턴 칸 중 '인터뷰로만'이 아닌 것(지원동기·업무내용·배운점)
#   - 목록 밖 응답·JSON 없음은 폐기하고 칸을 빈 채로 둔다(HCX 원칙 v2 4절). 폐기 목록은 끝에 출력
#   - 채운 행에는 "autoClassified": true (노트 화면 「자동 분류」 라벨, spec 9장)
#   - 결과는 functions/logs/classify-cache.json에 id+문장으로 저장한다. sheet_to_json.py를 다시 돌려
#     evidence.json이 새로 만들어지면 이 스크립트를 다시 돌리면 되고, 문장이 같으면 AI를 다시 부르지 않는다.
#   - 채점은 원우의 data/intern-gold.csv와 비교(작업 50, 합격선 85%)
import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "functions"))
from ai import PROVIDER, callAI, load_prompt  # noqa: E402

DATA = ROOT / "data"
CACHE = ROOT / "functions" / "logs" / "classify-cache.json"   # .gitignore 대상
KIND = "문단분류"
# 11/20 Sonnet 측정 기준 1건 평균 입력 ~510·출력 ~60토큰. 단가(100만 토큰당 입력/출력): sonnet $2/$10, opus $4/$20
PRICE = {"sonnet": (2, 10), "opus": (4, 20), "hcx": (0, 0)}
AVG_IN, AVG_OUT = 510, 60


def sections():
    f = json.loads((DATA / "frames.json").read_text(encoding="utf-8"))["인턴"]
    return [c for c in f["칸"] if c not in f.get("인터뷰로만", [])]


def key(e):
    return e["id"] + ":" + hashlib.sha1(e["text"].encode("utf-8")).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    path = DATA / "evidence.json"
    ev = json.loads(path.read_text(encoding="utf-8"))
    cols = sections()
    targets = [e for e in ev if e.get("docType") == "현장실습후기" and not e.get("칸")]
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    todo = [e for e in targets if key(e) not in cache]
    if args.limit:
        todo = todo[: args.limit]

    model = PROVIDER[KIND]
    pin, pout = PRICE.get(model, (0, 0))
    cost = len(todo) * (AVG_IN * pin + AVG_OUT * pout) / 1e6
    print(f"칸 목록: {', '.join(cols)} · 모델: {model}")
    print(f"대상 {len(targets)}건 · 캐시에 있음 {len(targets) - len([e for e in targets if key(e) not in cache])}건 · 이번에 부를 것 {len(todo)}건 · 예상 ${cost:.2f}")
    if args.dry_run:
        return

    system, shots = load_prompt(KIND)

    def one(e):
        user = f"칸 목록: {', '.join(cols)}\n문장: {e['text']}\n출력:"
        r = callAI(KIND, shots + [{"role": "user", "content": user}], system=system)
        v = (r.get("json") or {}).get("칸") if r["ok"] else None
        return e, v if v in cols else None, r.get("error") or r.get("text", "")[:80]

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for e, v, memo in pool.map(one, todo):
            cache[key(e)] = v  # None = 폐기(다음 실행 때 다시 시도하지 않음. 지우려면 캐시에서 그 줄을 뺀다)
            done += 1
            if v is None:
                print(f"  폐기 {e['id']}: {memo}")
            if done % 50 == 0:
                CACHE.parent.mkdir(exist_ok=True)
                CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"  … {done}/{len(todo)}")
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    filled, dropped, count = 0, [], {c: 0 for c in cols}
    for e in targets:
        v = cache.get(key(e))
        if v:
            e["칸"], e["autoClassified"] = v, True
            filled += 1
            count[v] += 1
        elif key(e) in cache:
            dropped.append(e["id"])
    path.write_text(json.dumps(ev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"채움 {filled}/{len(targets)} · 칸별 {count} · 폐기 {len(dropped)}건 {dropped[:10]}")


if __name__ == "__main__":
    main()

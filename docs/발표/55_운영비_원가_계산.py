# 작업 55 운영비 슬라이드 — 단계별 연간 AI 원가 다시 계산 (미리, 11/26)
# 쓰는 법: python -X utf8 docs/발표/55_운영비_원가_계산.py [ai-calls.jsonl 경로]
#   경로를 빼면 C:/dev/VCC/functions/logs/ai-calls.jsonl. AI를 부르지 않는다(로그 집계·산수만).
# 설명·출처는 같은 폴더 55_운영비_원가_미리.md.
import collections
import json
import sys

LOG = sys.argv[1] if len(sys.argv) > 1 else "C:/dev/VCC/functions/logs/ai-calls.jsonl"

# ── 가정 (문서 2절) ─────────────────────────────────────────────
KRW = 1400                 # 원/$
Q_USD = 0.0328             # 질문 1건 Claude 원가, A안 측정(Q-51, 11/26), 캐시 적중 21%
Q_HCX = 0.01               # 질문 1건 HCX 호출 수(A안: 고르기는 거의 안 부름)
Q_PER_JUNIOR = 10          # 후배 1인당 연 질문 수(미리 결정)
IV_PER_SENIOR = (1, 2)     # 선배 1인당 연 인터뷰 수(하한, 상한)
STAGES = [                 # 신청서 「초기 운영 계획」: (이름, 후배 하한·상한, 선배 하한·상한)
    ("도입기(1학기)", (50, 100), (10, 20)),
    ("성숙기(2~3학기)", (1000, 1500), (40, 60)),
    ("확장기(2년차)", (4000, 5000), (100, 150)),
]

# ── 단가 $/1M 토큰 (claude-api 스킬, 2026-11-03 기준) ─────────────
# 입력, 출력, 캐시 쓰기(5분 = 입력 × 1.25), 캐시 읽기
PRICE = {"sonnet": (2.0, 10.0, 2.5, 0.10), "opus": (4.0, 20.0, 5.0, 0.20)}

# ── 인터뷰 1회 호출 수 ──────────────────────────────────────────
IV_TASKS = ("충분판정", "꼬리질문", "요약", "1인칭", "일치검사")   # functions/ai.py PROVIDER 작업명
IV_DAYS = ("2026-11-22", "2026-11-24")   # 요약=Sonnet·일치검사=Opus로 바뀐 뒤(11/22~), 이 PC 로컬 실행
# 상한: 교환·파견 6칸을 다 묻고, 칸마다 꼬리질문은 절반, 요약 문장 3개를 모두 일치검사
IV_HIGH = {"충분판정": 6, "꼬리질문": 3, "요약": 6, "1인칭": 1, "일치검사": 18}


def family(model):
    return "hcx" if "HCX" in model else ("opus" if "opus" in model else "sonnet")


def usd(tok, fam):
    if fam == "hcx":
        return 0.0   # 크레딧 차감, 단가 미확인 — 원에 넣지 않고 호출 수로 따로 센다
    pi, po, pw, pr = PRICE[fam]
    return (tok["in"] * pi + tok["out"] * po + tok.get("cw", 0) * pw + tok.get("cr", 0) * pr) / 1e6


iv = collections.defaultdict(collections.Counter)
full = collections.Counter()
for line in open(LOG, encoding="utf-8"):
    d = json.loads(line)
    day = d["at"][:10]
    if d["작업"] in IV_TASKS and IV_DAYS[0] <= day <= IV_DAYS[1] and d["ok"]:
        c = iv[d["작업"]]
        c["n"] += 1
        c["in"] += d["입력토큰"] or 0
        c["out"] += d["출력토큰"] or 0
        iv[d["작업"]]["fam"] = ("sonnet", "opus", "hcx").index(family(d["모델"]))
    if d["작업"] == "답쓰기-전문" and day == "2026-11-26" and d["ok"]:
        full["n"] += 1
        full["tok"] += (d["입력토큰"] or 0) + (d.get("캐시쓰기토큰") or 0) + (d.get("캐시읽기토큰") or 0)

print("== 1. 인터뷰 작업별 1호출 평균 ==")
per_call = {}
for t in IV_TASKS:
    c = iv[t]
    fam = ("sonnet", "opus", "hcx")[c["fam"]]
    avg = {"in": c["in"] / c["n"], "out": c["out"] / c["n"]}
    per_call[t] = usd(avg, fam)
    print(f"  {t:5} {fam:6} n={c['n']:3}  입력 {avg['in']:5.0f}  출력 {avg['out']:4.0f}  ${per_call[t]:.5f}")

n_iv = iv["1인칭"]["n"]     # 1인칭은 인터뷰 끝에 한 번 → 인터뷰 수
IV_LOW = {t: iv[t]["n"] / n_iv for t in IV_TASKS}
iv_usd, iv_hcx = {}, {}
print(f"== 2. 인터뷰 1회 (로그 인터뷰 {n_iv}회) ==")
for name, cnt in (("하한", IV_LOW), ("상한", IV_HIGH)):
    iv_usd[name] = sum(per_call[t] * cnt[t] for t in IV_TASKS)
    iv_hcx[name] = cnt["충분판정"] + cnt["꼬리질문"]
    print(f"  {name}: ${iv_usd[name]:.4f} = ₩{iv_usd[name] * KRW:.0f}, HCX {iv_hcx[name]:.2f}회  "
          + " · ".join(f"{t} {cnt[t]:.2f}" for t in IV_TASKS))

print("== 3. 단계별 연간 ==")
rows = []
for name, (jl, jh), (sl, sh) in STAGES:
    ql, qh = jl * Q_PER_JUNIOR, jh * Q_PER_JUNIOR
    il, ih = sl * IV_PER_SENIOR[0], sh * IV_PER_SENIOR[1]
    lo = (ql * Q_USD + il * iv_usd["하한"]) * KRW
    hi = (qh * Q_USD + ih * iv_usd["상한"]) * KRW
    hl, hh = ql * Q_HCX + il * iv_hcx["하한"], qh * Q_HCX + ih * iv_hcx["상한"]
    rows.append((name, ql, qh, il, ih, lo, hi))
    print(f"  {name}: 질문 {ql:,}~{qh:,} · 인터뷰 {il}~{ih} · Claude ₩{lo:,.0f}~₩{hi:,.0f} · HCX {hl:,.0f}~{hh:,.0f}회")

print("== 4. 민감도 (확장기) ==")
_, ql, qh, il, ih, lo, hi = rows[-1]
ivl, ivh = il * iv_usd["하한"] * KRW, ih * iv_usd["상한"] * KRW
print(f"  질문 2배: ₩{2 * ql * Q_USD * KRW + ivl:,.0f}~₩{2 * qh * Q_USD * KRW + ivh:,.0f}")
T = full["tok"] / full["n"]                       # 답쓰기-전문 1건 입력(캐시 포함) 토큰
d1 = T * 0.01 * (PRICE["sonnet"][2] - PRICE["sonnet"][3]) / 1e6   # 적중 1%p당 절감 $
q50 = Q_USD - d1 * (50 - 21)
print(f"  캐시 적중 50%: 답쓰기-전문 입력 {T:,.0f}토큰/건 기준 1%p당 -${d1:.5f} → 질문 ${q50:.4f}(₩{q50 * KRW:.0f}), "
      f"₩{ql * q50 * KRW + ivl:,.0f}~₩{qh * q50 * KRW + ivh:,.0f}")
print(f"  단가 1.5배: ₩{lo * 1.5:,.0f}~₩{hi * 1.5:,.0f} · 단가 0.5배: ₩{lo * 0.5:,.0f}~₩{hi * 0.5:,.0f}")

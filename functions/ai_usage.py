# ai_usage.py — 오늘 내 AI 사용액 한 줄 (11/24 미리 결정)
#
# AI 키는 미리 PC와 서버에만 있다(11/25: 팀원별 키 vcc-dev(ww)·vcc-dev(minji)·CLOVA 비활성화). 키별 한도가 없다.
# 그래서 이 PC의 호출 기록(functions/logs/ai-calls.jsonl, ai.py가 씀)으로 오늘 사용액을 본다.
#   python -X utf8 functions/ai_usage.py                → 오늘 내 AI $0.12 (Claude 5회) · HCX 3회 1,234토큰
#   python -X utf8 functions/ai_usage.py --date 2026-11-23
#   python -X utf8 functions/ai_usage.py --journals <일지.md> <일지.md> ...   → 팀 합계
#   python -X utf8 functions/ai_usage.py --live   → 실제 청구(/token, 아래 「실제 청구 조회」)
#   python -X utf8 functions/ai_usage.py --since 2026-11-29 --gap 3 --per "물어보기 1건=질문정리,고르기,답쓰기,답검사" --md
#       → 작업별 1회 평균 + 1건당 원가 표(작업 55, 아래 「질문 1건당 원가」)
# 11/25부터 매 창 표시·일지 줄은 없앴다. 사용량은 /token(--live)으로 필요할 때 본다.
# 로그 줄 금액은 로그 토큰 × 아래 단가로 낸 추정이다.
# AI를 부르지 않는다. .env는 --live일 때만 읽고 값은 출력하지 않는다.
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import paths

LOG_FILE = paths.LOGS / "ai-calls.jsonl"

# Claude 단가: $ per 1M 토큰 (입력, 출력). 로그의 "모델" 값(모델 ID) 기준.
CLAUDE_PRICES = {
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
}
# HCX 단가: 아직 확인 못 함(11/24). NCP 요금표를 확인하면 $ per 1M 토큰 (입력, 출력)으로 환산해 채운다.
# None이면 HCX는 금액에 넣지 않고 회수·토큰만 보여 준다. CLOVA는 11/24부터 대회 크레딧에서 차감.
HCX_PRICE = None


def _is_hcx(model):
    return str(model).lower().startswith("hcx")


def summarize(lines, day):
    """로그 줄(문자열) 중 day(YYYY-MM-DD) 줄만 센다. 깨진 줄·다른 날 줄은 건너뛴다."""
    s = {"date": day, "usd": 0.0, "claude_calls": 0, "hcx_calls": 0, "hcx_tokens": 0,
         "hcx_usd": None, "unpriced": {}}
    hcx_in = hcx_out = 0
    for raw in lines:
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(d, dict) or not str(d.get("at", "")).startswith(day):
            continue
        model = d.get("모델", "")
        tin, tout = int(d.get("입력토큰") or 0), int(d.get("출력토큰") or 0)
        if _is_hcx(model):
            s["hcx_calls"] += 1
            hcx_in += tin
            hcx_out += tout
            continue
        s["claude_calls"] += 1
        price = CLAUDE_PRICES.get(model)
        if price is None:
            s["unpriced"][model] = s["unpriced"].get(model, 0) + 1
            continue
        s["usd"] += (tin * price[0] + tout * price[1]) / 1_000_000
    s["hcx_tokens"] = hcx_in + hcx_out
    if HCX_PRICE is not None:
        s["hcx_usd"] = (hcx_in * HCX_PRICE[0] + hcx_out * HCX_PRICE[1]) / 1_000_000
        s["usd"] += s["hcx_usd"]
    return s


def read_log(path=None):
    path = Path(path) if path else LOG_FILE
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:                       # 로그가 없는 PC(아직 AI를 안 부름)
        return []


def line(s, who="내"):
    """오늘 내 AI $0.12 (Claude 5회) · HCX 3회 1,234토큰"""
    text = f"오늘 {who} AI ${s['usd']:.2f} (Claude {s['claude_calls']}회)"
    text += f" · HCX {s['hcx_calls']}회 {s['hcx_tokens']:,}토큰"
    if s["hcx_usd"] is not None:
        text += f" ${s['hcx_usd']:.2f}"
    if s["unpriced"]:
        n = sum(s["unpriced"].values())
        text += f" · 단가 모름 {n}회({', '.join(sorted(s['unpriced']))})"
    return text


def today_line(day=None, path=None):
    day = day or date.today().isoformat()
    return line(summarize(read_log(path), day))


# ── 팀 합계 (milend) ── 작업일지의 「오늘 AI」 줄(위 line() 모양)을 읽어 더한다.
_LINE = re.compile(r"오늘 \S+ AI \$([\d.]+) \(Claude ([\d,]+)회\) · HCX ([\d,]+)회 ([\d,]+)토큰")


def parse_line(text):
    """글에서 첫 「오늘 … AI $x (Claude n회) · HCX m회 k토큰」을 찾아 dict로. 없으면 None."""
    m = _LINE.search(text)
    if not m:
        return None
    num = lambda g: int(g.replace(",", ""))
    return {"usd": float(m.group(1)), "claude_calls": num(m.group(2)),
            "hcx_calls": num(m.group(3)), "hcx_tokens": num(m.group(4))}


def team_total(texts):
    """[(이름, 일지 글)] → (합계 dict, 줄을 못 찾은 이름 목록)"""
    total = {"usd": 0.0, "claude_calls": 0, "hcx_calls": 0, "hcx_tokens": 0,
             "hcx_usd": None, "unpriced": {}}
    missing = []
    for name, text in texts:
        p = parse_line(text)
        if p is None:
            missing.append(name)
            continue
        for k in ("usd", "claude_calls", "hcx_calls", "hcx_tokens"):
            total[k] += p[k]
    return total, missing


# ── 질문 1건당 원가 (--since, 작업 55) ── 11/25
# 기간 안 호출 기록으로 ① 작업명·모델별 1회 평균 ② 「1건」 묶음의 원가를 낸다.
#   ② 묶음은 명령줄로만 정한다 — 작업 구성을 코드에 박지 않는다(물어보기 구성이 바뀔 수 있음).
#     --per "물어보기 1건=질문정리,고르기,답쓰기,답검사"   작업[*횟수]를 쉼표로. 1건 = Σ 횟수 × 작업 평균
#     --gap 3   기록의 시각 묶음: 앞 호출들이 끝나고 3초 안에 시작한(at − ms) 호출을 한 건으로 묶어
#               기록에 실제로 나타난 구성별로 건수·1건 평균을 낸다.
# 실패 호출(ok가 true가 아님)은 평균·묶음에서 빼고 건수만 보여 준다.
# 금액은 추정(로그 토큰 × 위 단가). HCX_PRICE가 None이면 HCX는 금액에 넣지 않고 토큰만 보여 준다.
from datetime import datetime, timedelta


def parse_when(text, end=False):
    """YYYY-MM-DD 또는 YYYY-MM-DDTHH:MM[:SS] → datetime. end=True면 날짜만 준 경우 그날 23:59:59."""
    t = text.strip().replace(" ", "T")
    d = datetime.fromisoformat(t)
    if len(t) == 10 and end:
        d += timedelta(days=1, seconds=-1)
    return d


def _price(model):
    return HCX_PRICE if _is_hcx(model) else CLAUDE_PRICES.get(model)


def load_calls(lines, since=None, until=None):
    """기간 안 줄 → (성공 호출 목록(시작 순), 실패 수 {작업: n}). 기간은 at(호출이 끝난 시각) 기준."""
    ok, failed = [], {}
    for raw in lines:
        try:
            d = json.loads(raw)
            end = datetime.fromisoformat(str(d["at"]))
        except (ValueError, TypeError, KeyError):
            continue
        if (since and end < since) or (until and end > until):
            continue
        task = str(d.get("작업") or "?")
        if d.get("ok") is not True:
            failed[task] = failed.get(task, 0) + 1
            continue
        ms = int(d.get("ms") or 0)
        ok.append({"작업": task, "모델": str(d.get("모델") or "?"),
                   "tin": int(d.get("입력토큰") or 0), "tout": int(d.get("출력토큰") or 0),
                   "ms": ms, "start": end - timedelta(milliseconds=ms), "end": end})
    ok.sort(key=lambda c: c["start"])
    return ok, failed


def _avg(calls, n):
    """calls 합을 n으로 나눈 1건 평균. usd는 단가 있는 호출만, 단가 없는 호출은 토큰을 따로."""
    s = {"tin": 0.0, "tout": 0.0, "ms": 0.0, "usd": 0.0, "unpriced_tokens": 0.0}
    unpriced = set()
    for c in calls:
        s["tin"] += c["tin"]
        s["tout"] += c["tout"]
        s["ms"] += c["ms"]
        p = _price(c["모델"])
        if p is None:
            s["unpriced_tokens"] += c["tin"] + c["tout"]
            unpriced.add(c["모델"])
        else:
            s["usd"] += (c["tin"] * p[0] + c["tout"] * p[1]) / 1_000_000
    n = n or 1
    return {**{k: v / n for k, v in s.items()}, "unpriced": sorted(unpriced)}


def by_task(calls, failed):
    """작업·모델별 행: 호출 수, 실패 수(작업 단위), 1회 평균."""
    groups = {}
    for c in calls:
        groups.setdefault((c["작업"], c["모델"]), []).append(c)
    rows = [{"작업": t, "모델": m, "호출": len(cs), **_avg(cs, len(cs))} for (t, m), cs in sorted(groups.items())]
    for t in sorted(set(failed) - {t for t, _ in groups}):        # 실패만 있는 작업도 보이게
        rows.append({"작업": t, "모델": "–", "호출": 0, **_avg([], 1)})
    for r in rows:
        r["실패"] = failed.get(r["작업"], 0)
    return rows


def parse_per(text):
    """'이름=작업a,작업b*6' → (이름, [(작업, 횟수)]). 횟수는 *N·:N·×N, 없으면 1."""
    if "=" not in text:
        raise ValueError(f"--per 모양: 이름=작업,작업*N (받은 값: {text})")
    name, body = text.split("=", 1)
    parts = []
    for p in (x.strip() for x in body.split(",")):
        if p:
            m = re.fullmatch(r"(.+?)\s*[*:×]\s*(\d+)", p)
            parts.append((m.group(1).strip(), int(m.group(2))) if m else (p, 1))
    if not name.strip() or not parts:
        raise ValueError(f"--per 모양: 이름=작업,작업*N (받은 값: {text})")
    return name.strip(), parts


def per_bundle(calls, name, parts):
    """정의한 묶음 1건 = Σ 횟수 × (그 작업의 기간 1회 평균). 기록에 없는 작업은 missing(0으로 셈)."""
    total = {"tin": 0.0, "tout": 0.0, "ms": 0.0, "usd": 0.0, "unpriced_tokens": 0.0}
    unpriced, missing, mixed = set(), [], []
    for task, k in parts:
        cs = [c for c in calls if c["작업"] == task]
        if not cs:
            missing.append(task)
            continue
        if len({c["모델"] for c in cs}) > 1:
            mixed.append(task)
        a = _avg(cs, len(cs))
        for key in total:
            total[key] += k * a[key]
        unpriced.update(a["unpriced"])
    return {"이름": name, "구성": " + ".join(f"{t} {k}" for t, k in parts),
            "missing": missing, "mixed": mixed, **total, "unpriced": sorted(unpriced)}


def time_bundles(calls, gap):
    """시각 묶음: 지금 묶음의 마지막 끝 시각 뒤 gap초 안에 시작한 호출은 같은 건.
    구성(작업별 횟수)이 같은 건끼리 모아 건수·1건 평균·1건 소요(첫 시작~마지막 끝)를 낸다."""
    groups = []
    for c in calls:                                   # calls는 시작 순
        if groups and (c["start"] - groups[-1]["end"]).total_seconds() <= gap:
            groups[-1]["calls"].append(c)
            groups[-1]["end"] = max(groups[-1]["end"], c["end"])
        else:
            groups.append({"calls": [c], "end": c["end"]})
    shapes = {}
    for g in groups:
        counts = {}
        for c in g["calls"]:                          # 이름은 처음 나온 순서대로
            counts[c["작업"]] = counts.get(c["작업"], 0) + 1
        e = shapes.setdefault(tuple(sorted(counts.items())),
                              {"구성": " + ".join(f"{t} {k}" for t, k in counts.items()), "건": 0, "wall": 0.0, "calls": []})
        e["건"] += 1
        e["wall"] += (g["end"] - g["calls"][0]["start"]).total_seconds()
        e["calls"] += g["calls"]
    return [{"구성": e["구성"], "건": e["건"], "wall_s": e["wall"] / e["건"], **_avg(e["calls"], e["건"])}
            for e in sorted(shapes.values(), key=lambda e: -e["건"])]


def cost_report(lines, since=None, until=None, pers=(), gap=None):
    calls, failed = load_calls(lines, since, until)
    return {"since": since.isoformat() if since else None, "until": until.isoformat() if until else None,
            "calls": len(calls), "failed": sum(failed.values()), "tasks": by_task(calls, failed),
            "per": [per_bundle(calls, n, p) for n, p in pers],
            "gap": gap, "shapes": time_bundles(calls, gap) if gap is not None else None}


def _w(s):
    """터미널 표시 폭(한글 2칸)."""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in str(s))


def _table(head, rows, md):
    if md:
        return (["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
                + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])
    widths = [max(_w(x) for x in col) for col in zip(head, *rows)]
    return ["  ".join(str(c) + " " * (w - _w(c)) for c, w in zip(r, widths)).rstrip() for r in [head, *rows]]


def money(r, krw=None):
    """금액 칸: 단가 있는 부분의 $(₩). 단가 없는 호출이 있으면 「+ 모델 n토큰(단가 없음)」."""
    if r["usd"] == 0 and r["unpriced_tokens"]:
        text = "–"
    else:
        text = f"${r['usd']:.4f}" + (f" (₩{r['usd'] * krw:,.1f})" if krw else "")
    if r["unpriced_tokens"]:
        text += f" + {'·'.join(r['unpriced'])} {r['unpriced_tokens']:,.0f}토큰(단가 없음)"
    return text


def report_lines(rep, md=False, krw=None):
    h2, h3 = ("## ", "### ") if md else ("", "")
    out = [f"{h2}AI 호출 원가 — {rep['since'] or '처음'} ~ {rep['until'] or '끝'}",
           f"성공 호출 {rep['calls']:,}건 · 실패 {rep['failed']:,}건(평균·묶음에서 뺌)",
           "금액은 추정: 로그 토큰 × 단가(ai_usage.py CLAUDE_PRICES·HCX_PRICE), 실제 청구 아님. "
           + ("HCX 단가 미확인 — HCX는 토큰만." if HCX_PRICE is None else "HCX 단가 반영.")
           + (f" ₩ = $ × {krw:,.0f}." if krw else ""),
           "", f"{h3}작업별 1회 평균"]
    rows = [[r["작업"], r["모델"], f"{r['호출']:,}", f"{r['실패']:,}", f"{r['tin']:,.0f}", f"{r['tout']:,.0f}",
             money(r, krw) if r["호출"] else "–", f"{r['ms']:,.0f}"] for r in rep["tasks"]]
    out += (_table(["작업", "모델", "호출", "실패", "평균 입력", "평균 출력", "평균 금액(추정)", "평균 ms"], rows, md)
            if rows else ["(기간 안 기록 없음)"])
    for b in rep["per"]:
        out += ["", f"{h3}{b['이름']} — 정의: {b['구성']}"]
        out += _table(["1건 입력", "1건 출력", "1건 금액(추정)", "호출 시간 합(ms)"],
                      [[f"{b['tin']:,.0f}", f"{b['tout']:,.0f}", money(b, krw), f"{b['ms']:,.0f}"]], md)
        if b["missing"]:
            out.append(f"주의: 기간 안 성공 기록 없음 — {', '.join(b['missing'])} (0으로 셈)")
        if b["mixed"]:
            out.append(f"주의: 모델이 섞인 작업 — {', '.join(b['mixed'])} (기간 평균으로 셈. --since·--until로 좁힐 수 있음)")
    if rep["shapes"] is not None:
        out += ["", f"{h3}기록의 시각 묶음 — 앞 호출이 끝나고 {rep['gap']:g}초 안에 시작하면 한 건"]
        rows = [[s["구성"], f"{s['건']:,}", f"{s['tin']:,.0f}", f"{s['tout']:,.0f}", money(s, krw), f"{s['wall_s']:.1f}"]
                for s in rep["shapes"]]
        out += (_table(["구성(작업 횟수)", "건", "1건 입력", "1건 출력", "1건 금액(추정)", "1건 소요(초)"], rows, md)
                if rows else ["(기록 없음)"])
    if not rep["per"] and rep["shapes"] is None:
        out += ["", "1건 원가는 --per \"이름=작업,작업*N\" 또는 --gap <초>를 함께 주세요."]
    return out


# ── 실제 청구 조회 (--live, /token) ── 11/25
# Anthropic: .env ANTHROPIC_ADMIN_KEY(sk-ant-admin…)가 있으면 Usage and Cost Analytics API(beta)로
#   오늘·이번 달 $(UTC 날짜 기준, 데이터는 최대 수 시간 늦음) + 키별 토큰. 없으면 이 PC 로그 추정(today_line).
# NCP: .env NCP_OS_ACCESS_KEY·NCP_OS_SECRET_KEY(서브 계정에 NCP_BILLING_VIEWER)로 Billing API —
#   이번 달 CLOVA Studio 이용 금액 + 크레딧 차감(11월부터 누적)과 대회 크레딧 남은 추정.
# 키 값은 출력·로그하지 않는다. 실패는 한 줄 이유로. AI는 부르지 않는다(비용 없음).
ANTHROPIC_API = "https://api.anthropic.com/v1/organizations"
ANALYTICS_BETA = "analytics-usage-cost-2026-08-24"
NCP_BILLING = "https://billingapi.apigw.ntruss.com"
CREDIT_TOTAL = 500_000          # 대회 크레딧(원), 11/24 수령, ~12/31
CREDIT_FROM = "202611"          # 크레딧 차감을 세기 시작하는 달


def _get_json(url, headers, timeout=15):
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(f"연결 실패({type(e).__name__})") from None
    except ValueError:
        raise RuntimeError("응답이 JSON이 아님") from None


# analytics 행 모양(11/25 실제 응답 확인):
#   {"group": {"api_key_id": …, (그 밖 차원은 null)}, "cost": {"amount": "330.6474", …}}   amount는 센트 단위 문자열
#   {"group": {…}, "usage": {"total_tokens": n, "uncached_input_tokens": …, "output_tokens": …, "requests": n}}
def _key_id(row):
    return (row.get("group") or {}).get("api_key_id")


def _cents(row):
    return float((row.get("cost") or {}).get("amount") or 0)


def _tokens(row):
    return int((row.get("usage") or {}).get("total_tokens") or 0)


def anthropic_lines(admin_key, today=None, get=None):
    """Admin 키로 오늘·이번 달 $와 키별 토큰 → 줄 목록."""
    from datetime import datetime, timezone
    from urllib.parse import urlencode
    get = get or _get_json
    now = datetime.now(timezone.utc)
    day = today or now.strftime("%Y-%m-%d")
    h = {"x-api-key": admin_key, "anthropic-version": "2023-06-01", "anthropic-beta": ANALYTICS_BETA}

    def rows(kind, start):
        q = urlencode([("starting_at", f"{start}T00:00:00Z"), ("group_by[]", "api_key_id"), ("limit", "1000")])
        return get(f"{ANTHROPIC_API}/analytics/{kind}?{q}", h).get("data") or []

    def usd(rs):
        return sum(_cents(r) for r in rs) / 100

    try:
        cost_today, cost_month = rows("cost", day), rows("cost", day[:8] + "01")
    except RuntimeError as e:
        return [f"Anthropic: 조회 실패 — {e}"]
    out = [f"Anthropic: 오늘 ${usd(cost_today):.2f} · 이번 달 ${usd(cost_month):.2f} (UTC 날짜, 데이터는 몇 시간 늦을 수 있음)"]
    try:
        names = {k.get("id"): k.get("name") for k in get(f"{ANTHROPIC_API}/api_keys?limit=100", h).get("data") or []}
        cost_by = {}
        for r in cost_today:
            cost_by[_key_id(r)] = cost_by.get(_key_id(r), 0) + _cents(r) / 100
        per = {}
        for r in rows("usage", day):
            per[_key_id(r)] = per.get(_key_id(r), 0) + _tokens(r)
        for kid in sorted(set(per) | set(cost_by), key=lambda k: -cost_by.get(k, 0)):
            name = names.get(kid) or kid or "키 없음(콘솔 등)"
            out.append(f"  {name}: 오늘 ${cost_by.get(kid, 0):.2f} · {per.get(kid, 0):,}토큰")
    except RuntimeError as e:
        out.append(f"  키별 토큰 조회 실패 — {e}")
    return out


def _ncp_headers(uri, access, secret):
    import base64
    import hashlib
    import hmac
    import time
    ts = str(int(time.time() * 1000))
    msg = f"GET {uri}\n{ts}\n{access}".encode("utf-8")
    sig = base64.b64encode(hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()).decode()
    return {"x-ncp-apigw-timestamp": ts, "x-ncp-iam-access-key": access, "x-ncp-apigw-signature-v2": sig}


def ncp_lines(access, secret, month=None, get=None):
    """Billing API로 이번 달 CLOVA Studio 이용 금액·크레딧 차감 → 줄 목록."""
    get = get or _get_json
    month = month or date.today().strftime("%Y%m")

    def call(path, start):
        uri = f"/billing/v1/cost/{path}?startMonth={start}&endMonth={month}&responseFormatType=json"
        return get(NCP_BILLING + uri, _ncp_headers(uri, access, secret))

    try:
        prod = call("getProductDemandCostList", month)["getProductDemandCostListResponse"]["productDemandCostList"]
        demand = call("getDemandCostList", CREDIT_FROM)["getDemandCostListResponse"]["demandCostList"]
    except RuntimeError as e:
        return [f"NCP: 조회 실패 — {e}"]
    except (KeyError, TypeError):
        return ["NCP: 응답 모양이 예상과 다름"]
    clova = sum(int(p.get("useAmount") or 0) for p in prod
                if "clova" in str((p.get("productDemandType") or {}).get("codeName", "")).lower())
    total = sum(int(p.get("useAmount") or 0) for p in prod)
    credit = sum(int(d.get("creditDiscountAmount") or 0) for d in demand)
    return [f"NCP: 이번 달 이용 ₩{total:,} (CLOVA Studio ₩{clova:,}) · 크레딧 차감 ₩{credit:,}({CREDIT_FROM}~) "
            f"→ 대회 크레딧 남은 약 ₩{CREDIT_TOTAL - credit:,} (추정, 청구 반영은 늦을 수 있음)"]


def live_lines(env=None):
    """--live 출력 줄들. env: 환경변수 dict(시험용). 없으면 .env를 읽어 os.environ."""
    import os
    if env is None:
        paths.load_env()
        env = os.environ
    out = []
    admin = env.get("ANTHROPIC_ADMIN_KEY")
    if admin:
        out += anthropic_lines(admin)
    else:
        out.append("Anthropic: Admin 키 없음 — 이 PC 로그 추정: " + today_line())
    ak, sk = env.get("NCP_OS_ACCESS_KEY"), env.get("NCP_OS_SECRET_KEY")
    out += ncp_lines(ak, sk) if ak and sk else ["NCP: NCP 키 없음"]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="오늘 내 AI 사용액 한 줄 (ai-calls.jsonl × 단가)")
    ap.add_argument("--live", action="store_true", help="실제 청구 조회(/token): Anthropic Admin API · NCP Billing API")
    ap.add_argument("--date", help="YYYY-MM-DD (기본: 오늘)")
    ap.add_argument("--log", help="로그 파일 (기본: 본 저장소 functions/logs/ai-calls.jsonl)")
    ap.add_argument("--json", action="store_true", help="숫자를 JSON으로")
    ap.add_argument("--journals", nargs="+", metavar="일지", help="작업일지들의 「오늘 AI」 줄을 더해 팀 합계")
    g = ap.add_argument_group("질문 1건당 원가 (작업 55) — --since를 주면 이 표를 낸다")
    g.add_argument("--since", help="시작 YYYY-MM-DD[THH:MM[:SS]] (호출이 끝난 시각 at 기준)")
    g.add_argument("--until", help="끝(포함). 날짜만 주면 그날 23:59:59 (기본: 끝까지)")
    g.add_argument("--per", action="append", default=[], metavar="이름=작업,작업*N",
                   help='1건의 작업 구성, 여러 번 가능. 예: --per "물어보기 1건=질문정리,고르기,답쓰기,답검사"')
    g.add_argument("--gap", type=float, metavar="초", help="기록의 시각 묶음: 앞 호출 끝 → 이 초 안에 시작하면 한 건")
    g.add_argument("--md", action="store_true", help="마크다운 표로")
    g.add_argument("--krw", type=float, metavar="환율", help="₩도 함께 (₩ = $ × 환율)")
    a = ap.parse_args(argv)
    if a.since or a.until:
        try:
            since = parse_when(a.since) if a.since else None
            until = parse_when(a.until, end=True) if a.until else None
            pers = [parse_per(p) for p in a.per]
        except ValueError as e:
            ap.error(str(e))
        rep = cost_report(read_log(a.log), since, until, pers, a.gap)
        print(json.dumps(rep, ensure_ascii=False, indent=1) if a.json else "\n".join(report_lines(rep, a.md, a.krw)))
        return 0
    if a.live:
        print("\n".join(live_lines()))
        return 0
    if a.journals:
        texts = []
        for f in a.journals:
            try:
                texts.append((Path(f).name, Path(f).read_text(encoding="utf-8-sig")))
            except OSError:
                texts.append((Path(f).name, ""))
        total, missing = team_total(texts)
        out = line(total, who="팀") + f" — 일지 {len(texts) - len(missing)}/{len(texts)}개"
        if missing:
            out += f" (「오늘 AI」 줄 없음: {', '.join(missing)})"
        print(json.dumps({**total, "missing": missing}, ensure_ascii=False) if a.json else out)
        return 0
    s = summarize(read_log(a.log), a.date or date.today().isoformat())
    print(json.dumps(s, ensure_ascii=False) if a.json else line(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())

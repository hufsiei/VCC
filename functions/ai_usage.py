# ai_usage.py — 오늘 내 AI 사용액 한 줄 (11/24 미리 결정)
#
# AI 키는 미리 PC와 서버에만 있다(11/25: 팀원별 키 vcc-dev(ww)·vcc-dev(minji)·CLOVA 비활성화). 키별 한도가 없다.
# 그래서 이 PC의 호출 기록(functions/logs/ai-calls.jsonl, ai.py가 씀)으로 오늘 사용액을 본다.
#   python -X utf8 functions/ai_usage.py                → 오늘 내 AI $0.12 (Claude 5회) · HCX 3회 1,234토큰
#   python -X utf8 functions/ai_usage.py --date 2026-11-23
#   python -X utf8 functions/ai_usage.py --journals <일지.md> <일지.md> ...   → 팀 합계
#   python -X utf8 functions/ai_usage.py --live   → 실제 청구(/token, 아래 「실제 청구 조회」)
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
    a = ap.parse_args(argv)
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

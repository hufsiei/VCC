# ai.py — 모든 AI 호출이 지나가는 단 하나의 관문 (수정: 미리)
#
# 서버 함수(askBoo 등)는 CLOVA나 Claude를 직접 부르지 않고 callAI(작업명, ...)만 부른다.
# 어떤 작업을 어떤 모델이 맡는지는 아래 PROVIDER 표 한 곳에서만 바꾼다.
# 근거: HCX 대응 원칙 v2 4절(작업별 모델·전환 기준), 5절(callAI 관문·키는 서버에만).
#
# 키는 환경변수로만 읽는다(코드·저장소에 적지 않는다).
#   CLOVA_KEY          CLOVA Studio API 키
#   CLOVA_URL          (선택) 플레이그라운드 '코드 보기'의 주소. 없으면 아래 기본값
#   ANTHROPIC_API_KEY  Claude API 키 (또는 `ant auth login` 프로필)
#   CLAUDE_MODEL       (선택) PROVIDER가 "claude"인 작업·측정의 기본 모델. 기본 claude-sonnet-5-5

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from mask import mask, mask_messages  # 작업 72: 외부 AI로 나가는 글은 코드가 먼저 가린다(AI에 맡기지 않음)


def _load_env():
    """저장소 맨 위의 .env(KEY=값 줄)를 환경변수로 읽는다. 이미 있는 환경변수는 덮지 않는다. 값은 출력하지 않는다."""
    path = Path(__file__).resolve().parent.parent / ".env"
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


_load_env()

# ── 1. 작업별 모델 표 ──────────────────────────────────────────────
# "hcx" | "sonnet" | "opus" ("claude"는 CLAUDE_MODEL). 측정 결과(작업 30·53·54)에 따라 이 표만 바꾼다.
# 11/20 작업 53 세 모델 비교(HCX 원칙 v2 8절): HCX가 합격한 판정·질문 3종은 HCX(CLOVA 유지),
# HCX가 미달한 요약·문단분류는 Sonnet, 일치검사는 요약과 다른 모델(Opus)로 검사한다.
PROVIDER = {
    "연습":     "hcx",     # local_fn.py 연결 확인용
    "고르기":   "hcx",     # askBoo ③ 근거 번호 고르기 — 11/20 작업 54 재측정 40/40(100%)으로 확정
    "변환":     "hcx",     # askBoo ④ 근거 → 해요체 한 문장
    "충분판정": "hcx",     # 인터뷰 답이 칸을 채웠나 {"충분":true} — HCX 10/10
    "꼬리질문": "hcx",     # 인터뷰 꼬리 질문 1개 — HCX 9/10
    "요약":     "sonnet",  # 인터뷰 요약 — HCX 0/10(형식 실패), Sonnet 9/10·Opus 9/10
    "1인칭":    "sonnet",  # 작업 21: 검증된 요약 문장 → 내 경험노트용 1인칭 해라체 (일괄 1회). 미측정, 실패하면 해요체 그대로
    "일치검사": "opus",    # 요약 문장 ↔ 원문 일치 — 만드는 모델(요약=Sonnet)과 검사하는 모델을 분리. Opus 10/10
    "쪽지검사": "hcx",     # 비방 판정 (연락처·학번은 코드 정규식이 먼저) — HCX 10/10
    "문단분류": "sonnet",  # 현장실습 후기 문장 → 칸 {"칸":"업무내용"} — HCX 8/10 미달, Sonnet 9/10
    "개선제안": "sonnet",  # 관리자 콘솔 개선 제안 (사전 생성·캐시) — 미측정, 작업 67에서 출력 보고 확정
    "리포트요약": "sonnet", # 관리자 리포트 요약 한 단락 — 미측정, 작업 66에서 확정
}

# ── 2. 작업별 설정 ─────────────────────────────────────────────────
# HCX: temperature·maxTokens 를 출력 크기에 딱 맞게(원칙 v2 5절).
# Claude(Sonnet·Opus 5.5): 생각(thinking)은 끌 수 없고 effort로만 깊이를 조절한다. 생각 토큰도 max_tokens에 들어간다.
SETTINGS = {
    "연습":     {"max_tokens": 256,  "temperature": 0.5},
    "고르기":   {"max_tokens": 30,   "temperature": 0, "top_p": 0.1},
    "변환":     {"max_tokens": 150,  "temperature": 0},
    "충분판정": {"max_tokens": 30,   "temperature": 0},
    "꼬리질문": {"max_tokens": 100,  "temperature": 0.3},
    "요약":     {"max_tokens": 4000, "effort": "medium"},
    "1인칭":    {"max_tokens": 3000, "effort": "low"},
    "일치검사": {"max_tokens": 2000, "effort": "medium"},
    "쪽지검사": {"max_tokens": 30,   "temperature": 0},
    "문단분류": {"max_tokens": 2000, "effort": "low"},   # 11/20 Sonnet 측정 설정 그대로
    "개선제안": {"max_tokens": 2000, "effort": "medium"},
    "리포트요약": {"max_tokens": 2000, "effort": "medium"},
}

CLOVA_URL = os.environ.get("CLOVA_URL", "https://clovastudio.stream.ntruss.com/v3/chat-completions/HCX-005")
CLAUDE_MODELS = {"sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5"}
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", CLAUDE_MODELS["sonnet"])   # PROVIDER·측정모델이 "claude"일 때
LOG_FILE = Path(__file__).parent / "logs" / "ai-calls.jsonl"   # .gitignore 대상


# ── 3. 관문 ───────────────────────────────────────────────────────
def callAI(작업명, messages, system=None, 측정모델=None, 측정설정=None):
    """작업명에 맞는 모델로 한 번 호출한다.

    messages: [{"role": "user"|"assistant", "content": "..."}]
    돌려주는 값: {"ok", "text", "json", "model", "error"?}
      text — 모델이 낸 글 전체 / json — text 안의 첫 번째 {...}를 읽은 것(없으면 None)
    화면에 보여 줄지는 부르는 쪽이 json을 검사해서 정한다(형식이 틀리면 버리고 폴백).
    측정모델·측정설정: 모델 비교 측정 스크립트(eval_*.py) 전용. 서비스 코드는 넘기지 않는다(PROVIDER 표가 기준).
    """
    if 작업명 not in PROVIDER:
        raise ValueError(f"PROVIDER 표에 없는 작업명: {작업명}")
    모델 = 측정모델 or PROVIDER[작업명]
    설정 = 측정설정 or SETTINGS.get(작업명, {})
    messages = mask_messages(messages)  # 연락처·메일·학번·링크·주소 → [연락처] 등
    system = mask(system) if system else system
    시작 = time.time()
    try:
        if 모델 == "hcx":
            text, usage = call_hcx(messages, system, 설정)
        else:
            text, usage = call_claude(messages, system, 설정, claude_model_id(모델))
        out = {"ok": True, "text": text, "json": first_json(text), "model": 모델}
    except Exception as e:  # 실패해도 서버가 죽지 않게. 화면은 폴백 문구를 보여 준다
        usage = {}
        out = {"ok": False, "text": "", "json": None, "model": 모델, "error": f"{type(e).__name__}: {e}"}
    _기록(작업명, 모델, usage, 시작, out["ok"], out.get("error"))
    return out


# ── 4. 모델별 호출 ─────────────────────────────────────────────────
def call_hcx(messages, system, 설정):
    """CLOVA Studio chat-completions v3. 주소·헤더는 플레이그라운드 '코드 보기'와 대조할 것."""
    key = os.environ.get("CLOVA_KEY")
    if not key:
        raise RuntimeError('CLOVA_KEY가 없습니다. PowerShell에서 $env:CLOVA_KEY = "발급받은_키"')
    if not key.isascii():
        raise RuntimeError("CLOVA_KEY에 한글이 들어 있습니다. 예시 문구('발급받은_키') 대신 CLOVA Studio에서 받은 실제 키를 넣으세요.")
    msgs = ([{"role": "system", "content": system}] if system else []) + messages
    body = {"messages": msgs, "maxTokens": 설정.get("max_tokens", 256), "temperature": 설정.get("temperature", 0)}
    if "top_p" in 설정:
        body["topP"] = 설정["top_p"]
    req = urllib.request.Request(
        CLOVA_URL,
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    for attempt in range(4):   # 429(테스트 키 분당 한도)·5xx는 쉬었다가 세 번까지 다시(2·4·8초, Retry-After가 있으면 그 값)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if (e.code == 429 or e.code >= 500) and attempt < 3:
                try:
                    wait = float(e.headers.get("Retry-After") or 0)
                except ValueError:
                    wait = 0
                time.sleep(min(max(wait, 2 ** (attempt + 1)), 15))
                continue
            raise RuntimeError(f"CLOVA {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    result = data.get("result", {})
    text = result.get("message", {}).get("content", "")
    u = result.get("usage", {})
    return text, {"input": u.get("promptTokens"), "output": u.get("completionTokens")}


def claude_model_id(모델):
    """PROVIDER 값 → Claude 모델 ID. "claude"는 CLAUDE_MODEL(환경변수), 표에 없는 값은 오류."""
    if 모델 == "claude":
        return CLAUDE_MODEL
    if 모델 not in CLAUDE_MODELS:
        raise ValueError(f"알 수 없는 모델: {모델} (hcx | sonnet | opus | claude)")
    return CLAUDE_MODELS[모델]


def call_claude(messages, system, 설정, model_id):
    """Claude API(공식 anthropic SDK). 정책상 거절되면 서버가 다른 모델로 이어서 답한다(fallbacks)."""
    import anthropic  # pip install anthropic — Claude를 쓰는 작업이 있을 때만 필요

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 또는 ant 로그인 프로필
    kwargs = dict(
        model=model_id,
        max_tokens=설정.get("max_tokens", 4000),
        messages=messages,
        output_config={"effort": 설정.get("effort", "medium")},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if system:
        kwargs["system"] = system
    response = client.beta.messages.create(**kwargs)
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude가 요청을 거절했습니다(refusal)")
    if response.stop_reason == "max_tokens":  # 생각 토큰까지 max_tokens에 들어가므로 잘리면 이유를 남긴다
        raise RuntimeError(f"max_tokens({kwargs['max_tokens']})에 걸려 답이 잘렸습니다")
    text = "".join(b.text for b in response.content if b.type == "text")
    return text, {"input": response.usage.input_tokens, "output": response.usage.output_tokens}


# ── 5. 도우미 ─────────────────────────────────────────────────────
PROMPT_DIR = Path(__file__).resolve().parent.parent / "docs" / "prompts"
_prompts = {}


def load_prompt(name):
    """docs/prompts/{name}.txt → (system, 예시 대화 messages).
    파일 모양: 지시문 다음에 '### 예시 입력' / '### 예시 출력' 블록을 번갈아 적는다(HCX는 예시 대화를 더 잘 따른다)."""
    if name not in _prompts:
        import re
        raw = (PROMPT_DIR / f"{name}.txt").read_text(encoding="utf-8")
        parts = re.split(r"^### 예시 (입력|출력)\s*$", raw, flags=re.M)
        shots = [{"role": "user" if kind == "입력" else "assistant", "content": body.strip()}
                 for kind, body in zip(parts[1::2], parts[2::2])]
        _prompts[name] = (parts[0].strip(), shots)
    return _prompts[name]


def first_json(text):
    """글 안의 첫 번째 {...}만 읽는다. HCX가 JSON 뒤에 말을 덧붙여도 앞의 JSON만 쓴다(원칙 v2 5절)."""
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def _모델ID(모델):
    try:
        return claude_model_id(모델)
    except ValueError:
        return 모델


def _기록(작업명, 모델, usage, 시작, ok, error=None):
    """호출 한 건마다 한 줄. 작업 55(질문 1건당 원가·운영비)와 작업 30(모델 비교)의 재료. 실패면 이유도(키는 담기지 않음)."""
    try:
        LOG_FILE.parent.mkdir(exist_ok=True)
        row = {
            "at": datetime.now().isoformat(timespec="seconds"),
            "작업": 작업명, "모델": "HCX-005" if 모델 == "hcx" else _모델ID(모델),
            "입력토큰": usage.get("input"), "출력토큰": usage.get("output"),
            "ms": int((time.time() - 시작) * 1000), "ok": ok,
        }
        if error:
            row["error"] = mask(error)[:200]  # 오류 문구에 요청 내용이 섞일 수 있어 가린 뒤 자른다
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass  # 기록 실패가 응답을 막지 않게

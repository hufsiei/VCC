# clova_once.py — 작업 47 ⑤ 함수 안에서 CLOVA(HCX-005) 1회 호출 (작성: 미리)
#
# NCP Cloud Functions · Python 3 · 웹 액션. 콘솔에 이 파일 전체를 붙여 넣는다(표준 라이브러리만 사용).
# 외부(CLOVA Studio)로 나가야 하므로 VPC에 NAT Gateway와 0.0.0.0/0 → NAT 라우트가 있어야 한다.
# NAT가 없으면 {"ok": false, "error": "네트워크: ..."}가 돌아온다(키 문제와 구분하려고 따로 표시).
#
# 기본 파라미터(콘솔 > 액션 > 기본 파라미터)
#   CLOVA_KEY     CLOVA Studio API 키 — 콘솔에만 넣는다. 코드·저장소·채팅·캡처에 쓰지 않는다.
#   ALLOW_ORIGIN  (선택) 예: https://hufsiei.github.io (없으면 "*")
#   CLOVA_URL     (선택) 없으면 아래 기본값(HCX-005)
#
# 설정 근거: HCX 대응 원칙 v2 5절 — Temperature 0, Thinking 끔, Max tokens는 출력 크기에 맞게(30),
# 출력은 JSON, 코드는 첫 번째 {...}만 읽고 형식이 틀리면 버린다.
#
# 참고: 서비스 코드는 functions/ai.py의 callAI()로만 부른다. 이 파일은 배포 경로(VPC·NAT·키 파라미터)를
# 확인하는 1회용 점검 함수라서 콘솔에 붙여 넣을 수 있게 파일 하나로 만들었다.

import json
import time
import urllib.error
import urllib.request

DEFAULT_URL = "https://clovastudio.stream.ntruss.com/v3/chat-completions/HCX-005"

SYSTEM = '너는 JSON만 출력한다. 다른 말은 쓰지 않는다. 형식: {"ok":true,"msg":"hello"}'
USER = '형식 그대로 {"ok":true,"msg":"hello"} 만 출력해.'


def _cors(args):
    return {
        "Access-Control-Allow-Origin": args.get("ALLOW_ORIGIN") or "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-User",
        "Access-Control-Max-Age": "600",
    }


def _reply(args, status, data):
    headers = _cors(args)
    headers["Content-Type"] = "application/json; charset=utf-8"
    return {"statusCode": status, "headers": headers, "body": json.dumps(data, ensure_ascii=False)}


def first_json(text):
    """글 안의 첫 번째 {...}만 읽는다(functions/ai.py와 같은 규칙). 없으면 None."""
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


def main(args):
    if str(args.get("__ow_method", "")).lower() == "options":
        return {"statusCode": 204, "headers": _cors(args), "body": ""}

    key = args.get("CLOVA_KEY") or ""
    if not key:
        return _reply(args, 500, {"ok": False, "error": "CLOVA_KEY 기본 파라미터가 없습니다"})
    if not key.isascii():
        return _reply(args, 500, {"ok": False, "error": "CLOVA_KEY 값이 올바르지 않습니다(한글 포함)"})

    body = {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER},
        ],
        "temperature": 0,
        "topP": 0.1,
        "maxTokens": 30,
        # Thinking 끔: HCX-005는 추론(thinking) 기능이 없는 모델이라 thinking 필드를 보내지 않는다.
        # HCX-007로 바꿀 때는 "thinking": {"effort": "none"}을 추가하고 maxTokens 대신
        # maxCompletionTokens를 쓴다(플레이그라운드 '코드 보기'와 대조).
    }
    req = urllib.request.Request(
        args.get("CLOVA_URL") or DEFAULT_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        # 응답 본문만 일부 돌려준다(요청 헤더·키는 넣지 않는다). 401이면 키, 403이면 권한 문제.
        detail = e.read().decode("utf-8", "replace")[:200]
        return _reply(args, 502, {"ok": False, "error": f"CLOVA {e.code}", "detail": detail})
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", e)
        return _reply(args, 504, {"ok": False, "error": f"네트워크: {type(reason).__name__}",
                                  "hint": "VPC의 NAT Gateway·0.0.0.0/0 라우트를 확인"})

    result = data.get("result") or {}
    text = (result.get("message") or {}).get("content", "")
    usage = result.get("usage") or {}
    parsed = first_json(text)
    return _reply(args, 200, {
        "ok": parsed is not None,          # JSON을 못 읽으면 실패로 본다(원칙 v2 5절)
        "json": parsed,
        "text": text[:200],
        "model": "HCX-005",
        "ms": int((time.time() - t0) * 1000),
        "tokens": {"input": usage.get("promptTokens"), "output": usage.get("completionTokens")},
    })

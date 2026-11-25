---
description: AI 사용량 보기 — Anthropic(Admin API)·NCP(Billing API) 실제 청구, 키가 없으면 이 PC 로그 추정
allowed-tools: Bash(python:*), PowerShell
---

`python -X utf8 C:/dev/VCC/functions/ai_usage.py --live`를 한 번 돌리고 출력 줄을 그대로 보여 준다(설명 붙이지 않음).

- Anthropic: `.env`에 `ANTHROPIC_ADMIN_KEY`(sk-ant-admin…)가 있으면 오늘·이번 달 $와 키별 토큰(UTC 날짜, 몇 시간 늦을 수 있음). 없으면 「Admin 키 없음 — 이 PC 로그 추정」.
- NCP: `NCP_OS_ACCESS_KEY`·`NCP_OS_SECRET_KEY`로 이번 달 이용 금액(CLOVA Studio)·크레딧 차감과 대회 크레딧 남은 추정. 없으면 「NCP 키 없음」.
- 키 값은 읽어서 보여 주지 않는다. AI 호출 비용은 없다.
- 실패 줄이 있으면 그 이유 한 줄만 덧붙인다(예: HTTP 401 → 키 권한 확인).

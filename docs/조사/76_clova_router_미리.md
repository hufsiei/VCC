# 작업 76 — CLOVA Studio 라우터 조사 (2026-11-26, 미리)

## 결론

- **추천: 로드맵.** 12/3 프리즈 전에는 넣지 않는다.
- 붙인다면 한 곳: **쪽지 검사**(`runtime_fns.checkMessage`)의 세이프티 필터. 질문 입력은 askBoo 경로라 제외.
- 지금 키: 문서상 가능해 보임, **실제 동작은 미확인**(라우터를 만들지 않음).
- 넣으면: **약 3~4시간**(추정).
- 비용: **단가 미확인**. 크레딧에서 빠지는지도 확인 전.

## 1. 라우터가 하는 일

- 입력을 **도메인으로 분류**하고 **필터**에 걸리는지 판별한다. 답을 만들지 않는다. [가이드](https://guide.ncloud-docs.com/docs/clovastudio-router.md)
- 필터 두 종류 [도메인 가이드](https://guide.ncloud-docs.com/docs/clovastudio-domain.md)
  - 콘텐츠 필터: 도메인에서 처리하지 않을 주제를 직접 정의(도메인당 최대 7개, 설명 200자)
  - 세이프티 필터: `Unethical`(욕설·범죄 등), `Contentious`(정치·사회 민감 이슈의 편향 주장)
- 준비: 콘솔에서 라우터 생성 → 도메인 생성(설명·필터) → 버전 확인 → [코드 보기]. [코드 보기 가이드](https://guide.ncloud-docs.com/docs/clovastudio-router-viewsource)
- API: `POST https://clovastudio.stream.ntruss.com/v1/routers/{router-id}/versions/{version}/route`, `Authorization: Bearer`, 본문 `query`(+`chatHistory`). 응답 `result.domain` · `result.blockedContent` · `result.safety` · `result.usage`. [API](https://api.ncloud-docs.com/docs/clovastudio-router.md)
- 한도: 테스트 키 분당 60회, 서비스 앱 180회(2025-07-17 기준). [이용량 제어](https://guide.ncloud-docs.com/docs/clovastudio-ratelimiting)
- 출시 2025-04-17. 라우터 지원 종료 공지는 읽은 문서에 없음. [릴리스 노트](https://api.ncloud-docs.com/docs/clovastudio-releasenote.md)

## 2. 지금 키로 쓸 수 있나

- 테스트 앱 없이 발급한 API 키로 모든 기능을 쓸 수 있다고 안내됨(2025-07-17 이후). [API 개요](https://api.ncloud-docs.com/docs/ai-naver-clovastudio-summary)
- 실호출 **1회**: 지금 `CLOVA_KEY`로 없는 라우터 ID(`0`)에 요청 → `404 Not found`. 사용 토큰 없음.
  - 401·403은 나오지 않았지만, 없는 ID라 **키 권한이 확인된 것은 아니다.**
- 확정하려면: 콘솔에서 라우터를 하나 만들고 1회 호출(미리, 약 20분).

## 3. 붙일 곳

| 후보 | 판단 |
|---|---|
| **쪽지 검사** | **추천.** askBoo 밖이고, 짧은 글 하나를 통과/차단으로 가르는 자리라 모양이 맞음 |
| 질문 입력 | 제외. askBoo 경로(11/30~12/1 동결), 응답 시간이 늘고 측정(작업 95)을 다시 해야 함 |
| 인터뷰 답 입력 | 제외. 이미 충분판정·동의 절차가 있고 시연 흐름에 지연이 생김 |

쪽지 검사의 지금 순서: 코드 규칙(`msg_check.py`) → HCX 판정(`callAI("쪽지검사")`, 측정 10/10).

- 라우터로 **바꾸지 않는 이유**: 우리 기준(강한 감정 표현·제도 불만은 통과)을 `Unethical` 필터에 가르칠 수 있는지 문서에 없다. 인신공격이 이 필터에 잡히는지도 재 봐야 안다.
- 넣는다면: 코드 규칙 → 라우터 세이프티(`Unethical`만) → 걸리지 않으면 HCX 판정. 라우터 실패는 지금처럼 통과 처리.

## 4. 측정에 미치는 영향

- askBoo를 건드리지 않으므로 작업 95 측정(옛 길 ↔ 새 길)에는 영향이 없다.
- 쪽지 검사의 HCX 10/10은 **라우터를 앞에 두면 그대로 쓸 수 없다.** 같은 사례(`eval53_cases.json` 「쪽지검사」 10건)로 합친 결과를 다시 재야 한다.
- 한도: 문서는 라우터 한도를 스킬 트레이너와 묶어 계산한다고만 한다. HCX-005 호출 한도와 별개로 보인다(추정).
- 재배포가 필요하다. 서버는 통째로 올라가므로 11/30~12/1 동결 중에는 피한다.

## 5. 비용

- CLOVA Studio는 모델·용도·토큰 수로 과금. [사용 준비](https://guide.ncloud-docs.com/docs/clovastudio-spec)
- **라우터 단가는 읽은 공식 페이지에서 찾지 못했다**(요금표가 스크립트로 그려져 가져오지 못함). 확인: 콘솔 또는 [상품 페이지](https://www.ncloud.com/v2/product/aiService/clovaStudio) 요금 탭.
- 크기: 공식 응답 예시는 1회 487토큰. 시연·시험 수백 회면 20만 토큰 안팎(추정)으로, 크레딧 50만 원에 비해 작을 것으로 보인다. 단가 확인 전에는 금액으로 말할 수 없다.

## 6. 넣을 때 할 일 (합 3~4시간, 추정)

| 할 일 | 시간 |
|---|---|
| 콘솔: 라우터·도메인·필터 생성, 1회 호출 확인 | 0.5h |
| `ai.py`에 라우터 호출(마스킹·로그·사용량 포함 — `callAI` 관문 유지), `runtime_fns.py` 연결, 시험 | 1.5h |
| 쪽지 사례 측정, 필요하면 필터 조정 | 1h |
| 기본 파라미터(라우터 ID·버전) 추가, 재배포·점검 | 0.5h |

## 7. 로드맵으로 두는 이유

- 지금 쪽지 검사는 이미 HCX(CLOVA)로 돌고 측정을 통과했다. 라우터를 더해도 사용자에게 달라지는 것이 확인되지 않았다.
- 남는 이득은 「CLOVA 기능 1종 추가」 증빙인데, 측정 없이 넣으면 발표에서 방어하기 어렵다.
- 발표 문구: 「CLOVA Studio 라우터(세이프티 필터)를 쪽지 검사 앞단에 두는 것을 검토했고, 우리 기준으로 측정한 뒤 확장기에 적용」.

**다시 볼 조건**: 11/29 점검 때 NCP 활용 증빙이 부족하다고 판단되고, 12/2까지 4시간을 낼 수 있으면 위 6장대로 넣는다. 측정에서 정상 쪽지를 하나라도 막으면 뺀다.

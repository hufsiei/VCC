# 외대人사이드 함수·응답 명세 v1 (2026-11-14)

이 문서대로 `common/data.js`, `common/mock-data.json`, `data/README.md`를 채운다.
화면은 `common/data.js`의 함수만 부르고, 응답 모양은 이 문서를 따른다.
명세를 바꿔야 하면 코드보다 이 문서를 먼저 고치고 팀에 알린다.

> 11/14 개정: 데이터 키를 시트 헤더 그대로(0장·9장), 선배·후배 고정 없음(0장), login·getMe 모양 변경(4장), 인턴 노트 5칸(6장).
> 11/16 개정 ②(데이터 기준 확정): **최종 데이터 원본 = `@VCC/가상데이터/가상데이터_1000명.xlsx`**. 9장을 그 파일의 시트·헤더로 다시 썼다. 시연 인물을 그 파일의 실제 행(H0143·H0469·H0745)으로 바꾸고, 시연 프로그램을 데이터에 있는 `마르부르크필립스대학교`로, 공통 비교과를 `합격 면접 취업특강(커리어랩)`으로 바꿨다(1·3·4·6장 예시 포함). 후배1은 2학년(1학년은 이중전공 없음).
> **11/19 개정(PRD v1.2, FDE 피드백)**: 노트 틀 네 종류에 **`후배 질문`**(인터뷰로만) 칸 추가(교환·파견 7칸, 인턴 6칸, 비교과 3칸). `interviewNext`가 같은 프로그램의 질문함 `hold` 질문을 먼저 묻고 `questionId`를 돌려준다. `summarizeInterview` 문장에 `answersQuestionId`, `saveConsent`가 질문을 `answered`로 바꾸고 질문자에게 알림. `getNote`·`listNotes`는 **사전 생성 `data/notes.json`(원문 인용) + `runtime/noteLines.json`(동의 통과 인터뷰 문장)** 합집합. askBoo 1단계에 인턴 직군·기관유형 사전 매칭. 모든 AI 호출은 `callAI` 입구에서 **마스킹 + 사용자별 호출 한도**(0장). 출처 칩은 **연도만** 표시. 현장실습후기 근거는 **문장 단위**(9장). 운영 보관기간(0장). 바뀐 곳은 **[11/19]** 표시.
> 11/16 개정(PRD 4-1): 교환·파견 노트 틀에 `배운점`(인터뷰로만) 추가 → 6칸. `summarizeInterview`가 끝나면 myNote를 서버가 바로 저장(저장은 기본, 공유는 선택). `saveConsent`의 `edits.removed`가 문장 단위 비공개를 뜻함. 공개 초안 문장에 `identifying` 표시 추가. 사람 이름: 추천 선배는 `독일어과 선배 A`, 쪽지 보낸 사람은 `형용사 + 동물`(대화마다 새로) — `previewNickname`·`respondRequest` 신설, `sendMessage`·`getMessages`에 `myNickname`·`role`·`askerInfo` 추가.
> **11/19 개정 ②(작업 18·22)**: askBoo 응답에 **`status: "official"`**(규정 질문 → 공식 안내 연결) 추가(3·4·6·8장). 닮은 선배 점수는 서버가 Python이므로 `common/score.js`를 없애고 **`functions/score.py`(원우)** 한 벌로 계산한다.
> **11/19 개정 ③(작업 18)**: askBoo `lines[]`에 **`fallback`**(사후 검증에 걸려 근거 원문을 보여 준 줄) 추가(4장). `noteId`는 `data/notes.json`이 생기기 전까지 프로그램 이름으로 나간다.
> **11/22 개정(작업 23, 민지 요청)**: `listNotes`·`getNote`에 **`country`**(국제교류 = `programs.json` `세부` 국가, 인턴·비교과 `null`, 카드 띠 「교환학생 · 독일」)와 **`scrapped`**(내가 스크랩했는지) 추가. 새 함수 **`scrapNote(noteId, scrap)`**(켜기·끄기, 멱등) → `getInbox.scraps`가 실제로 채워진다(최근이 위). **[11/22 오후]** `getNote` 배운점 문장에 **`senior`**(「선배 A」, 노트 안에서만 쓰는 글자, 학과 없음 — PRD 9-1), 새 함수 **`saveQuestion(noteId, section)`**(「질문함에 담기」). **[11/22 저녁]** `getInbox.myNotes` 카드 값(`share`·`filled`/`total`·`sharedLines` 등), 새 함수 **`getMyNote(id)`**(내 경험노트 상세), 공유 상태는 셋뿐(「반영 중」 없음). 바뀐 곳은 **[11/22]** 표시.
> **11/22 개정 ③(선배 추천 열림, 미리 결정)**: 닮은선배 추천은 **경험 나눔**(들려주기 유효 답변 3개 + 해봤노트 1문장 이상 공유) 또는 **수요 제공**(새 함수 **`demandNext`·`saveDemand`** — 「궁금한 것 정리하기」, 유효 답변 3개 + 전달 동의)을 한 뒤에 열린다. 한 번 열리면 모든 프로그램. `getMe.recommend`, 잠겼을 때 `recommendSeniors`·`previewNickname`의 `locked`와 `sendMessage`의 `reason: "잠김"`, `summarizeInterview`의 `answered`·`need`, `saveConsent`의 `recommend`·`unlocked`, `askerInfo.관심`을 「교환학생·독일」 형식으로 + `시기`. 서버 `functions/demand.py`. 바뀐 곳은 **[11/22 열림]** 표시.
> **11/23 개정 ③(선배가 요약 문장 고치기, 미리 결정)**: 내 경험노트와 해봤노트 공개 문장은 **따로** 고친다(읽는 사람이 달라 표현이 다를 수 있음). 공개 문장은 공개 동의 시트의 「문장 고치기」(`saveConsent` `changed`, **[11/23 고치기]**), 내 경험노트 문장은 새 함수 **`updateMyNote(id, changed)`**. `getMyNote` 문장에 `edited`. 바뀐 곳은 **[11/23 고치기]** 표시.
> **11/23 개정 ②(작업 29 실사용, 미리 결정)**: ① `askBoo`에 새 `status: "notes"` — 사람을 찾는 질문(「네덜란드 교환 다녀온 선배?」)이나 나라만 말한 질문에 주제어가 없으면 답 대신 해봤노트 카드(`notes[]`)로 안내한다. 프로그램명이 없으면 **나라 이름**(`programs.json` `세부`)으로 그 나라 프로그램을 찾는다. `hold` 문구를 이유별로 나누고(노트가 있는데 「경험한 선배가 없어요」라고 하지 않음), 노트가 있으면 `hold`에도 `noteId`. ② 닮은선배 **추천받기 끄기** — 새 함수 **`setRecommendable(on)`**, `getMe.recommendable`, `sendMessage`의 `reason: "추천 제외"`. 경험자는 기본으로 후보이고, 끈 선배는 추천·새 쪽지 요청에서 빠진다. 바뀐 곳은 **[11/23 노트]**·**[11/23 추천]** 표시.
> **11/23 개정(작업 28, 민지 요청)**: 쪽지 대화 ⋮ 메뉴용 새 함수 **`reportThread(threadId, reason, block)`** — 신고(`threadReports.json`)·차단(`status: "blocked"`, 양쪽 다 더 못 보냄). `sendMessage`에 `reason: "차단"`, `getMessages`에 `blockedByMe`. 바뀐 곳은 **[11/23 차단]** 표시.
> **11/23 개정 ⑤(askBoo v2 검토안, 팀 합의 — `docs/askBoo-v2 반영 검토안 (2026-11-23, 상의용).md`)**: ① `askBoo`에 **`history`**(최근 대화 4턴)와 서버의 **질문 정리**(의도·프로그램·제외·칸, Sonnet) → 의도가 `대화`면 새 **`status: "chat"`**(질문함 저장 없음), `탐색`이면 `notes`(카드에 `oneLine`, 현장실습은 `kinds`). `ok` 답은 **답 쓰기**(Sonnet, 2~4문장)로 만들고 문장마다 **`cites`**(인용한 sourceId)가 붙는다 — 근거 번호 없는 문장·근거에 없는 숫자·이름은 코드가 버리고, 다 버려지면 지금 방식(원문 인용) 폴백. 고르기는 HCX 그대로(상한 8). ② **노트 틀에서 「후배 질문」 칸 삭제**(교환·파견 6칸, 인턴 5칸, 비교과 2칸). 후배 질문은 `interviewNext`가 여전히 먼저 묻되(`junior: true`) 답은 **질문이 속한 칸**에 들어간다. 해봤노트 문장의 `answersQuestionId`는 유지(화면 라벨 「후배 질문에 답한 문장」), Q·A 쌍은 질문자의 내 보관함 질문 상세에서만. ③ **이어 쓰기**: `interviewNext`가 내 경험노트의 칸을 답한 것으로 치고, `summarizeInterview`에 `append`. ④ 새 함수 **`deleteQuestion`·`updateQuestion`**(hold만, 소프트 삭제), **`saveInterviewDraft`·`getInterviewDraft`**(미완성 초안 7일, P1-여건 79). ⑤ (**[11/23] P0**, 작업 78 — 전체 노트 적용) `getNote` 칸별 **`summary`**(사전 생성 요약 문단, 문장마다 `sources`). 바뀐 곳은 **[v2]** 표시. 화면 반영은 민지, 데이터(frames.json)는 원우, 서버는 미리.
> **11/23 개정 ④(쪽지 읽음, 미리 결정)**: `getMessages()`는 목록만 돌려주고 **읽음으로 바꾸지 않는다**(닮은선배 화면이 버튼 상태를 볼 때 안 읽음이 사라지던 것). 대화창을 열 때 `getMessages(threadId)`(payload `{read: threadId}`)로 부르면 그 대화만 읽음. 바뀐 곳은 **[11/23 읽음]** 표시.
> **11/22 개정 ②(작업 21, 미리)**: `interviewNext`가 보고서가 이미 답한 칸은 묻지 않고(빈 칸·오래된 칸만), **깊이 질문**(`depth`, 교환·파견 3개·인턴·비교과 2개)을 묻는다. 묻지 않은 칸은 **`covered`**로 알린다(4장).
> **11/20 개정(닮은 선배 실제 데이터 기준)**: 시연 인물을 `가상데이터_1000명.xlsx` 실제 값에 맞췄다. 선배2를 H0745 → **H0241**(독일어과 3학년·경영학, 마르부르크 2026-1, 12점 2위)로 바꾸고, 선배1과 후배1의 공통 비교과를 `합격 면접 취업특강(커리어랩)` → **`한국외국어대학교 직무탐색 집중교육`**으로 바꿨다. H0241은 공통 비교과가 없다(12점 = 학과 5 + 이중전공 4 + 단과대 3). 후배1은 현장실습 이수가 없다. 선배1 보고서 학기 2024-1 → 2025-1(1·4·6장 예시 포함).

## 0. 공통 규칙

- 모든 함수는 `async`이고 JSON 객체를 돌려준다.
- 실패 시 공통 모양: `{ "error": "사람이 읽을 메시지" }`. 화면은 `res.error`가 있으면 안내 문구를 보여 준다.
- 학기 표기는 `"2025-1"`, `"2025-2"`, `"2025-여름"`, `"2025-겨울"`.
- 화면에는 학번을 보여 주지 않는다. 다른 사람은 서버가 자동 생성한 닉네임(`nickname`)으로만 표시한다(닮은 선배 카드, 익명 쪽지창). 닉네임은 시트·프로필에 두지 않는다. 형식은 **`학과 + " 선배 " + 영문 대문자`**(예: `"독일어과 선배 A"`)이고 학번·입학년도는 넣지 않는다. 글자는 보는 사람 기준으로 처음 만난 순서대로 A, B, C…를 주고, 그 사람에게는 카드·프로필·쪽지창에서 계속 같은 값을 쓴다.
- **쪽지를 보낸 사람**은 다른 이름 체계를 쓴다: `"형용사 + 동물"`(예: `"용감한 수달"`). 쪽지 요청을 여는 순간 서버가 만들고 **대화(thread) 하나마다 새로** 정한다(같은 후배가 다른 선배에게 보내면 다른 이름). 선배 화면에서 보낸 사람은 이 이름 + 학년 + 관심 경험만 보이고 학과는 보이지 않는다. 보낸 사람 화면에서 선배는 계속 `"독일어과 선배 A"`다. 즉 **보는 사람 입장에서 상대 이름은 늘 하나**다.
- 로그인한 사용자 정보는 `sessionStorage`의 `"me"`에 저장한다(탭마다 따로 — 두 창 시연). **저장은 `data.js`의 `login()`이 성공 응답의 `user`를 그대로 넣는다**(화면이 따로 저장하지 않음). 함수는 사용자를 payload로 받지 않고, `data.js`가 모든 서버 요청에 헤더 `X-Token: <토큰>`(`me.token`)을 붙인다(작업 51·73).
- **데이터 열 이름은 `가상데이터_1000명.xlsx`의 헤더를 그대로 쓴다.** 가상학생 시트는 종합정보시스템 학적 영문 코드(`colreg_no`, `crs_nm`, `dbl_mjr_nm` 등), 나머지 시트는 한글 헤더(`학번`, `학년도`, `프로그램명` 등)가 JSON 키가 된다. 시트에 없는 값만 영어 이름을 붙인다(예: `docType`, 자동 생성 `nickname`). 자세한 대응은 9장.
- **변환에서 빼는 열**: `studt_na_kr`(가상 성명)·`sex`·`나이(만)`은 시트에만 두고 `students.json`에 넣지 않는다(저장소가 공개돼도 명단처럼 보이지 않게). 사람을 구분하는 열쇠는 `colreg_no` 하나로 충분하다(1,001개 모두 고유, 다른 시트 학번과 100% 연결 확인).
- **응답에 넣지 않는 열**: `번호`. 로그인 비번은 `data/`에 없고 서버 환경변수 `VCC_LOGIN_PW`에만 둔다(작업 73).
- **[11/19] 외부 AI로 나가는 글은 서버가 먼저 마스킹한다.** `functions/mask.py`(작업 72, 원우 27 정규식 공용화)가 전화(지역번호·휴대폰 전부)·이메일·학번(`H`+숫자 4자리, 9자리 숫자)·URL·주소 패턴을 `[연락처]` `[메일]` `[학번]` `[링크]` `[주소]`로 바꾼다. **[11/20]** 주소는 넓은 단위(시·도·시군구·읍면동·도로명)는 남기고 건물번호·지번·동·층·호만 `[주소]`로 가린다(예: `동대문구 이문로 107, 101동 1203호` → `동대문구 이문로 [주소], [주소]`, 붙여 쓴 주소도 같다). 가리는 곳은 `callAI` 입구(messages·system)이고, 로그의 오류 문구도 가린 뒤 남긴다. 로그 `ai-calls.jsonl`도 마스킹 뒤 값만 남긴다. AI에게 마스킹 판단을 맡기지 않는다.
- **[11/19] 사용자별 AI 호출 한도.** `X-Token`으로 확인한 사용자 기준 분당 10회·일 100회(`runtime/aiUsage.json`). **[작업 86] 전역 일일 상한 2,000건**(`aiUsage.json`의 `"_global"`, 시연 계정도 센다. 초과 시 `{ "error": "오늘 사용량을 다 썼어요. 내일 다시 시도해 주세요" }`). 초과 시 `{ "error": "잠시 뒤에 다시 시도해 주세요" }`. 시연 계정(H0143·H0469·H0241·H0745·staff01·staff02)은 제외 목록. 닮은선배·집계·노트 조회는 AI를 안 부르므로 한도와 무관. **세는 단위는 AI를 쓰는 함수 요청 1건**이다(askBoo 질문 1개 = 1회. 안에서 AI를 몇 번 부르는지는 세지 않음). 구현: `functions/limits.py`, 대상 함수는 `local_fn.py`의 `AI_ROUTES`(작업 72).
- **[11/19] 출처 표기는 연도만.** 응답의 `semester`는 그대로 두되, 화면의 출처 칩은 `"2024"`처럼 연도만 보여 준다(학과+파견교+학기가 함께 보이면 소수 학과에서 사람이 특정됨 — PRD 9-1). 노트 커버의 `lastSemester`는 학기까지 표시해도 된다(프로그램 단위 집계값).
- **[11/19] 보관기간(운영 규칙, PRD 9-3).** 쪽지 원문 90일, 인터뷰 답변 원문은 요약·동의 처리 뒤 30일, **[v2] 인터뷰 미완성 초안(`interviewDrafts.json`)은 7일**(요약하면 삭제, 지나면 삭제 — 마스킹 전 원문이라 쪽지·요약 후 원문보다 짧게), 질문 로그는 학번 제거 후 통계만(삭제한 질문도 `status: "deleted"`로 남아 통계에만 쓰임), 대회 종료(12/9) 후 runtime 전체 삭제(`reset_runtime.py`). 시연 기간에는 삭제 스케줄러를 만들지 않고 규칙만 문서화한다.
- **선배·후배를 사람에게 고정하지 않는다.** 같은 사람이 어떤 프로그램에서는 묻고, 다른 프로그램에서는 답한다. 그 프로그램을 이수한 기록(가상비교과·가상학생의 파견·인턴 열·귀국보고서·현장실습후기)이 있으면 그 프로그램에 대해 답할 수 있다. 학년과 상관없다. "닮은 선배"의 선배는 "그 경험을 먼저 해 본 사람"이라는 뜻이다.

## 1. 시연 인물과 가상 계정 (README.md에도 적을 것)

후배1·선배1·선배2는 문서·대화에서만 쓰는 호칭이다. 화면 표시명(`독일어과 선배 A/B`)과 헷갈리지 않게 숫자로 부른다.

| 역할 | 아이디 | 설명 |
|---|---|---|
| 후배1 | H0143 | 서양어대학 독일어과 2학년, 이중전공 경영학, 해외경험·현장실습 없음. 비교과 3개 이수: `Jump Start 프로그램(1:1 학습컨설팅)`·`ISO 국제학생회 BUDDY 프로그램 수료자`(2025-2), `한국외국어대학교 직무탐색 집중교육`(2026-1). 질문하는 사람 |
| 선배1 | H0469 | 독일어과 4학년, 이중전공 경영학, 학과 파견학생 독일 `마르부르크필립스대학교`(2025-1, 귀국보고서 있음), 후배1과 같은 비교과 `한국외국어대학교 직무탐색 집중교육` 이수. 닮은 선배 1위(14점) |
| 선배2 | H0241 | 독일어과 3학년, 이중전공 경영학, 학과 파견학생 같은 대학(2026-1, 귀국보고서 있음). 공통 비교과 없음. 닮은 선배 2위(12점: 단과대·학과·이중전공) |
| 직원 1 (총괄 관리자) | staff01 | 가상학생 시트 맨 위 행: `crs_nm`=`전체`. 관리자 콘솔에서 전 부서를 드롭다운으로 보고, 리포트 발행 설정·발행을 한다 |
| 직원 2 (부서 담당자) | staff02 | 가상학생 시트 둘째 행: `crs_nm`=`혁신지원팀`. 관리자 콘솔에서 **자기 부서만** 보고(드롭다운 고정), 발행된 리포트를 받는다 |

모두 `가상데이터_1000명.xlsx`의 실제 행이다(성명 열은 화면에 쓰지 않음). 마르부르크필립스대학교 귀국보고서는 5편(H0469·H0241·H0745·H0751·H0995)이라 노트 근거로 충분하다. 학생 데이터(`data/students.json`)는 원우가 이 파일에서 변환한다. mock은 위 인물로 만든다.

## 2. 접속 주소 (README.md)

- 로컬: 저장소 폴더에서 `python -m http.server 8000` → `http://localhost:8000/screens/login/`
- 미리 개발 서버(미리 PC만): `functions/local_fn.py` → `http://localhost:8787`
- 공개 주소(GitHub Pages, 11/20 작업 80): https://hufsiei.github.io/VCC/screens/login/

### 2-1. 쓰기 저장소 (작업 51, 11/16 결정)

쪽지·질문함·공개 동의·신고·내 경험노트·알림처럼 **사용자가 만들어 내는 기록**은 mock으로는 두 창 시연(후배1 창의 쪽지 → 선배1 창 알림)이 안 되므로 서버가 저장한다.

- **지금(로컬):** `functions/local_fn.py`가 시작할 때 `data/runtime/*.json`을 읽어 메모리에 두고, 기록이 바뀔 때마다 그 파일을 다시 쓴다(임시 파일에 쓴 뒤 바꿔 끼워 반쯤 쓰인 파일이 남지 않게). 서버를 껐다 켜도 남는다.
- **Cloud Functions 이사 후:** 같은 파일 이름을 NCP **Object Storage**의 객체로 둔다. 바꾸는 곳은 `functions/store.py`의 저장 방식 한 곳뿐이다(`STORE_BACKEND=file|ncp`). 다른 코드는 `store.load(이름)`·`store.save(이름)`만 쓰고 파일을 직접 열지 않는다.
- **파일(기록 종류마다 하나):** `messages.json`(쪽지 대화) · `nicknames.json`(보는 사람별 선배 글자 A·B·C) · `questions.json`(질문함, 사용 로그와 같은 모양) · `demands.json`(**[11/22 열림]** 궁금한 것 정리하기 — 분야·세부·프로그램·칸·시기·상황·바라는 것, 선배 추천 열림 근거) · `consents.json`(공개 동의) · `myNotes.json`(내 경험노트) · `reported.json`(신고 문장) · **[11/23 차단]** `threadReports.json`(쪽지 대화 신고) · **[11/23 추천]** `recommendOptOut.json`(닮은선배 추천받기를 끈 사람) · `alerts.json`(알림) · `pendingNicknames.json`(요청 시트에서 미리 정한 동물 닉네임) · `shownSeniors.json`(보는 사람·노트별 지금 추천 목록 최대 9명과 노트 버전) · `counters.json`(번호 매기기) · **[작업 85]** `noteVersions.json`(노트별 버전 — saveConsent가 +1, recommendSeniors가 비교) · **[11/19]** `noteLines.json`(공개 동의를 통과한 인터뷰 문장, 노트별 — 사전 생성 `data/notes.json`과 합쳐 노트가 된다) · `aiUsage.json`(사용자별 AI 호출 수) · (P1-여건) `sessions.json`(로그인 토큰, 작업 73) · `interviewDrafts.json`(**[v2]** 인터뷰 미완성 초안 — 사람·프로그램별 `answers`와 `savedAt`, 7일, 작업 79). 코드: `functions/store.py`(저장) · `functions/runtime_fns.py`(쓰기 함수: checkMessage·previewNickname·sendMessage·getMessages·respondRequest·reportThread·recommendSeniors·setRecommendable·saveConsent·updateMyNote·reportStatement·getInbox, **[v2]** deleteQuestion·updateQuestion·saveInterviewDraft·getInterviewDraft, 그리고 askBoo·summarizeInterview·recommendSeniors가 쓸 도우미 `add_question`·`save_my_note`·`senior_label`). **[작업 66]** 관리자 콘솔용 `reportSettings.json`(부서코드별 발행 설정) · `issuedReports.json`(발행 이력) · `reportHtml.json`(리포트 id → HTML, PRD 6-4의 `reports/{id}.html` 대신 한 파일) · `suggestionStatus.json`(제안 id → 상태). 코드: `functions/admin.py`.
- **누가 부르는지:** 서버는 헤더 `X-Token`을 `sessions.json`(`functions/sessions.py`, 토큰 24시간, 같은 계정 동시 로그인 허용)으로 풀어 사용자를 안다. 토큰이 없거나 만료·폐기면 `{ "error": "로그인이 필요해요" }`(`checkMessage`·`login`만 예외). `login`이 난수 토큰을 발급해 `user.token`으로 주고, `logout`이 폐기한다. 로그인 비번은 `data/`가 아니라 환경변수 `VCC_LOGIN_PW`(.env·NCP 기본 파라미터)에만 둔다. 표의 `"*"`는 가상학생 전원의 공용 비번(청중 체험용, 개별 항목이 우선, 직원에는 적용 안 됨). 순서: 토큰 확인 → 전역 상한 → 사용자별 한도 → 함수. **[11/19] 남의 기록은 서버가 막는다**: `getMessages`·`respondRequest`는 `me`가 그 대화의 asker·senior일 때만, 내 경험노트·`saveConsent`는 `owner == me`일 때만, 관리자 함수는 `권한`이 있을 때만 응답하고 그 외는 `{ "error": "볼 수 없는 기록이에요" }`. (작업 73)
- **초기화:** 리허설 전 `python functions/reset_runtime.py` → runtime 파일을 비우고 시연 시작 상태로 돌린다.
- `data/runtime/`은 커밋하지 않는다(`.gitignore`). 시연 중 쌓인 기록이 저장소에 섞이지 않게.
- 화면은 아무것도 바꿀 필요가 없다. `data.js`에서 `USE_MOCK = false`로 바꾸면 같은 함수가 서버로 간다. 원우·민지는 mock으로 계속 작업하고, 두 창 확인은 미리 PC에서 한다.

## 3. data.js 동작

```js
export const USE_MOCK = true;
const FN_BASE = "http://localhost:8787";
// call(name, payload): USE_MOCK이면 pickMock, 아니면 POST `${FN_BASE}/${name}` (JSON body)
// mock-data.json은 import.meta.url 기준 상대경로로 한 번만 fetch해서 캐시
```

### pickMock 규칙 (입력에 따라 다른 mock을 고르는 곳은 여기 한 곳)

| 함수 | 규칙 |
|---|---|
| login | 비밀번호가 비어 있으면 `login.fail`. 아니면 `id`가 `"staff01"`이면 `login.staff`, `"staff02"`이면 `login.staffDept`, 학번 모양(`H` + 숫자 4자리)이면 `login.student`, 그 외 `login.fail`(비번은 대조하지 않는다 — 공개 코드에 비번을 두지 않음) |
| askBoo | **[v2]** 대화 표현(`아까|말고|그 말이 아니|데이터 없|그게 아니`)이 있으면 `askBoo.chat`. 4장의 규정 질문 표현이 있으면 `askBoo.official`, **[11/23 노트]** 사람을 찾는 표현(`다녀온 선배`·`선배 있어요?` 등)이나 탐색 표현(`어디 있|추천해|어떤 게 있`)이 있고 주제어(기숙사·비용·수업·서류·학점·팁·조언·어땠)가 없으면 `askBoo.notes`, 아니면 질문에 `교환\|파견\|독일\|마르부르크`가 있으면 `askBoo.exchange`(문장마다 `cites`), 그 외 `askBoo.hold`. `history`는 무시한다 |
| setRecommendable [11/23 추천] | 이 탭에서만 기억(sessionStorage `mockRecommendable`). `getMe.recommendable`도 그 값 |
| interviewNext | **[11/20]** `program`이 `interviewNext.byProgram`에 있으면(마르부르크 시연 대본) `answers.length`번째 `steps`, 다 쓰면 `done`(steps[0]은 후배 질문 — **[v2]** `junior: true`, `section`은 그 질문의 칸). 그 밖의 프로그램은 서버(`interview.py`)처럼 `data/programs.json`의 `분야` → `data/frames.json` 노트 틀을 고르고, 아직 답하지 않은 칸을 틀 순서대로(「배운점」은 마지막) `interviewNext.questions[칸]` 문장으로 묻는다(`{p}` = 별칭 첫째 또는 프로그램명). 꼬리 질문·후배 질문은 없다(`pendingQuestions: 0`) |
| getNote | `getNote[id]`가 있으면 그것, 없으면 `getNote["N-marburg"]` |
| getMyNote [11/22] | `getMyNote` 하나(M-0001, 일부 공유 예시). 받은 `id`를 그대로 넣어 돌려준다 |
| updateMyNote [11/23 고치기] | `getMyNote`에 `changed`를 적용해 `ok: true`와 함께 돌려준다(기억하지 않음). 빈 문장·없는 문장은 서버와 같은 `error` |
| 선배 추천 열림 [11/22 열림] | mock 기본은 **열림**. 주소에 `?locked=1`이면 잠김: `getMe.recommend.ready: false`, `recommendSeniors`·`previewNickname` → `locked`, `sendMessage` → `reason: "잠김"`. mock `saveDemand`·`saveConsent`를 부르면 그 탭은 열린다(sessionStorage `mockUnlocked`) |
| demandNext·saveDemand [11/22 열림] | `data.js`의 `mockDemand`가 서버(`demand.py`)와 같은 순서로 `programs.json`·`frames.json`에서 칩을 만든다. `fromQuestionId`는 마르부르크·생활 보류 질문으로 채운다 |
| summarizeInterview [11/22 열림] | `summarizeInterview` + transcript로 센 `answered`, `need: 3`. **[v2]** `append: true`면 `getMyNote` 문장 뒤에 새 문장을 붙인 모양 |
| deleteQuestion·updateQuestion [v2] | 받은 값으로 `ok: true`를 돌려준다(기억하지 않음). `getInbox.questions`의 `answered`·`official` id면 서버와 같은 `error` |
| saveInterviewDraft·getInterviewDraft [v2] | 이 탭에서만 기억(sessionStorage `mockDraft:<program>`) |
| checkMessage | 숫자가 8자리 이상 연속(전화·학번)이면 `checkMessage.blocked`, 그 외 `checkMessage.ok` |
| 나머지 | `m[name]` 그대로 |

## 4. 함수 15개

### login(id, pw)
payload `{id, pw}`
`status`는 시트 열이 아니라 서버가 정한다: `colreg_no`가 `staff`로 시작하면 `"직원"`, 그 외는 `"학생"`. 직원은 그 행의 `crs_nm`을 `부서명`으로 주고, `권한`을 정한다: `crs_nm`이 `"전체"`면 `"총괄"`(전 부서 조회, 리포트 설정·발행), 부서명이면 `"부서"`(자기 부서만 조회, 받은 리포트 확인 — 관리자 콘솔 함수는 `dept`를 무시하고 이 부서로 고정). 직원 행은 학생 집계·닮은 선배 후보·사용 로그 생성에서 뺀다.
```json
{ "ok": true, "user": { "colreg_no": "H0143", "status": "학생", "token": "…" } }
{ "ok": true, "user": { "colreg_no": "staff01", "status": "직원", "부서명": "전체", "권한": "총괄", "token": "…" } }
{ "ok": true, "user": { "colreg_no": "staff02", "status": "직원", "부서명": "혁신지원팀", "부서코드": "D04", "권한": "부서", "token": "…" } }
{ "ok": false, "reason": "아이디 또는 비밀번호가 맞지 않아요." }
```
**[작업 85]** 서버 응답의 `user`에는 `token`(작업 73)이 있고, `data.js`가 이것을 `me.token`으로 저장해 `X-Token`에 쓴다. mock 응답에는 `token`이 없다(mock은 헤더를 쓰지 않음). `부서코드`는 부서 직원만(`전체`에는 없음).

### getMe()
가상학생 한 줄(시트 헤더 그대로, `번호`·`비번` 제외) + 이수 기록. 이수 기록도 각 시트 헤더 그대로이고, 귀국보고서·현장실습후기는 본문 칸을 빼고 기본 정보만 담는다.
```json
{ "colreg_no": "H0143", "univ_nm": "서양어대학", "crs_nm": "독일어과", "dbl_mjr_nm": "경영학",
  "regst_grad": 2, "입학년도": 2025, "해외경험": "없음", "현장실습·인턴십": "없음",
  "인턴 유형": null, "기관 유형(가상)": null, "기관명(가상)": null,
  "인턴 시기": null, "비교과 이수 건수": 3, "경험 조합": "없음",
  "비교과이수내역": [ { "이수학년도": 2025, "이수학기(1~4)": 3, "학기구분": "2학기",
                       "프로그램명": "Jump Start 프로그램(1:1 학습컨설팅)", "비교과 유형": "학습공동체·튜터링·멘토링", "이수 당시 학년": 1 }, … ],
  "귀국보고서": [],
  "현장실습후기": [] }
```
**[11/22 열림]** `recommend` = 선배 추천 열림 상태(`demand.recommend_status`). 닮은선배 화면은 `ready: false`면 잠김(디자인 규칙 6-6) + 두 길(경험 들려주기 / 궁금한 것 정리하기)을 보여 준다.
```json
"recommend": { "ready": false, "by": null, "need": 3, "talk": { "answered": 2, "shared": 0 }, "ask": false }
```
**[11/23 추천]** `recommendable` = 닮은선배로 추천받기(기본 `true`). `setRecommendable(false)`로 끈 사람만 `false`. 내 보관함 화면에 스위치 「닮은선배로 추천받기」를 둔다.

### setRecommendable(on) [11/23 추천]
payload `{on: true|false}`(불리언이 아니면 `{error}`). 켜기·끄기, 멱등. 기록은 `runtime/recommendOptOut.json`(`{colreg_no: {at}}`, 끈 사람만). AI 없음.
- 끄면 `recommendSeniors` 후보에서 빠진다(이미 본 목록에서도 다음 호출부터 빠짐). **새 요청·다시 요청**은 `sendMessage`가 `{ "ok": false, "reason": "추천 제외", "message": "이 선배는 지금 쪽지 요청을 받지 않아요." }`.
- 이미 수락한 대화는 그대로 이어진다(양쪽 모두 보낼 수 있음).
- 귀국보고서·현장실습후기 문장은 계속 해봤노트 근거로 쓰인다(학교에 낸 자료 — 쪽지를 받는 것과는 다른 동의, PRD 4절 닮은선배 행 [11/23]).
```json
{ "ok": true, "recommendable": false }
```
`by` = `"talk"`(경험 나눔으로 열림) | `"ask"`(수요 제공으로 열림) | `null`. `talk`는 내 경험노트 중 가장 많이 한 것(유효 답변 수·지금 공유된 문장 수).

귀국보고서 항목 예: `{ "학년도": 2024, "학기": 1, "국가": "독일", "대학명": "마르부르크필립스대학교" }` · 현장실습후기 항목 예: `{ "학년도": 2025, "학기": 2, "업체명": "KOTRA 해외무역관(유럽 권역)", "직군": "전시·행사 지원" }`(학기 2 = 여름방학). 학기 숫자를 화면에 낼 때는 9장의 학기 코드표로 바꾼다.

### askBoo(question, history?)
payload `{question, history?: [{question, status, program?}]}`. 규정 질문이면 `official`, 근거가 있으면 `ok`, 없으면 `hold`(`hold`·`official` 질문은 자동으로 질문함에 저장되고 `questionId`가 옴). **[v2]** 대화·탐색은 `chat`·`notes`(질문함에 저장하지 않음).

**[v2] askBoo v2 — 질문 정리·답 쓰기(검토안 2장, 팀 합의 11/23).** 지금 4+1단계 위에 두 단계를 더한다. 가드레일(프로그램 범위 안 근거·사후 검증·보류→질문함)은 그대로다.

| 단계 | 누가 | 하는 일 |
|---|---|---|
| ①′ | 코드 | 규정 판별(아래 [11/19]·[11/23] 표현). 걸리면 `official`, 질문 정리보다 먼저 |
| ① | Sonnet | **질문 정리**: `history`(화면이 sessionStorage에서 최근 4턴을 보냄 — 서버는 기억하지 않음) + 이번 질문 → `{의도: 경험질문|탐색|대화|규정|사람찾기, 분야, 나라, 프로그램후보[], 제외[], 칸, 정리된질문}`. 코드가 프로그램 이름을 `programs.json`과 대조해 없는 이름은 버린다. 별칭 대조·인턴 사전·나라 대조·사람 찾기 정규식은 **정리 결과를 보정하는 2차 수단**(AI 실패 시 지금 경로 그대로) |
| ② | 코드 | **의도별 분기**: `대화` → `chat`(고정 문구 + 칩, AI 없음, 저장 없음) / `탐색`·`사람찾기` → `notes` / `규정` → `official` / `경험질문` → ③ |
| ③ | 코드 | 근거 추출: 프로그램 최대 3개에서 `제외`를 뺀 뒤 후보 30개. 주제어가 있으면 문항으로 좁히고, 없으면 겹치는 근거를 넘긴다(#156) |
| ④ | HCX | 고르기 `{"관련":[…]}` 상한 **8**. 관련 없으면 빈 목록 → `hold` |
| ⑤ | Sonnet | **답 쓰기**: 정리된 질문 + 고른 문장(번호·프로그램·연도·몇 명의 경험인지) → `{"답":[{"text":"…","근거":[2,5]}, …]}` 2~4문장 해요체. 규칙: 문장마다 근거 번호 1개 이상 / 근거에 없는 숫자·이름·조언·맺음말 금지 / 근거가 한 사람뿐이면 코드가 라벨로 알림 |
| ⑥ | 코드 + Opus | 문장마다 **인용한 근거 원문**과 대조: `verify`의 숫자·영문·고유명사·수량 검사 + **답검사**(Opus, `docs/prompts/askBoo-답검사.txt` — 인터뷰 일치검사와 달리 BOO가 전하는 말투 「~라는 선배도 있었어요」·숫자 묶음 「270~380유로」는 일치, 문장별로 동시에 호출). 「새 낱말」 규칙은 답 쓰기에는 쓰지 않는다. 걸린 문장·근거 번호 없는 문장은 버린다. **다 버려지면 ④에서 고른 문장을 원문 인용(지금 방식, `fallback: true`)으로 돌려준다** |

- 모델: 고르기 = HCX(CLOVA 유지), 질문 정리·답 쓰기 = Sonnet, 답검사 = Opus(HCX 원칙 v3 4절). 변환(끝맺음만)은 폴백 줄에만. 11/24 실측: ok 답 1건 5~6초(질문정리 1초 · 고르기 0.7초 · 답쓰기 low 5초 · 답검사 문장별 1~2초 동시).
- 호출 수: 질문 1건 = AI 한도 1회(0장)이고 안에서 Claude 2~3회가 더 붙는다. 측정은 개발 70 + 다중 턴·탐색·대화 20개(원우 기대답), 근거 없는 답 0건 유지.
- `history` 항목: `{question: 사용자 말, status: 그때 응답 status, program?: 그때 답한 프로그램}`. 화면은 물어보기 대화를 sessionStorage에 두고(3-6) 보낼 때 최근 4개만 자른다. 마스킹은 0장과 같다.

**[v2] 응답 변경**
- `ok`: `lines[].cites` = 그 문장이 인용한 sourceId 목록(1개 이상). `fallback: true` 줄은 `cites`가 그 줄의 `sourceId` 하나. `sources`·`noteId`는 그대로. 근거가 한 사람뿐이면 `singleSenior: true`(화면 「선배 1명의 경험이에요」 라벨, 그 아래 「이 경험을 한 선배에게 더 묻기 · 질문함에 담기」).
- **새 `status: "chat"`**: 대화·메타(「아까도 한 얘기잖아」「데이터가 없나요?」「코트라 말고요」만 있고 질문이 없을 때). `message`는 서버 고정 문구(AI가 쓰지 않음), `chips`는 다음 행동. 질문함에 저장하지 않고 `questionId`가 없다.
- `notes`: 탐색(「어디 있어요?」「추천해 주세요」)도 이 상태. 카드에 `oneLine`(노트 커버 한 줄). 현장실습을 나라로 물으면(「독일 인턴 어디 있어요?」) 카드 대신 `kinds`(기관 유형 13개)와 안내 「현장실습 노트는 나라가 아니라 기관 유형으로 나뉘어요」 — 나라 열을 추가하지 않는다(해외 인턴십 케이스가 거의 없음, 11/23 미리).
```json
{ "status": "ok",
  "lines": [ { "text": "유럽 권역 무역관에서는 8주 동안 시장조사 지원과 화상 상담회 보조를 주로 했어요.", "cites": ["I007-1", "I012-2"], "lineId": "L-A1-1" },
             { "text": "선배들은 전공 언어를 실제 업무에 써 본 점을 가장 좋았던 점으로 꼽았어요.", "cites": ["I012-3"], "lineId": "L-A1-2" } ],
  "sources": { "I007-1": { "docType": "현장실습후기", "program": "KOTRA 해외무역관(유럽 권역)", "semester": "2025-1" }, "I012-2": { "...": "" }, "I012-3": { "...": "" } },
  "noteId": "N-kotra", "suggestSenior": false, "singleSenior": false }
{ "status": "chat", "lines": [], "sources": {}, "suggestSenior": false,
  "message": "아까는 KOTRA 해외무역관 이야기였어요. 다른 기관을 찾아볼까요?",
  "chips": [ { "label": "다른 기관 보기", "action": "notes", "payload": { "field": "현장실습", "exclude": ["KOTRA 해외무역관(유럽 권역)"] } },
             { "label": "질문함에 담기", "action": "save", "payload": { "question": "무역 관련 인턴 전반" } } ] }
{ "status": "notes", "lines": [], "sources": {}, "suggestSenior": true,
  "message": "현장실습 노트는 나라가 아니라 기관 유형으로 나뉘어요. 궁금한 유형을 골라 보세요.",
  "notes": [], "kinds": ["KOTRA 해외무역관", "중견기업 해외영업팀", "중소 무역회사", "…"] }
```
화면(민지): `chat`은 BOO 말풍선 + 칩(`action: notes`면 askBoo를 그 payload로 다시 부르지 않고 `../note/?type=…`로, `save`면 `saveQuestion`이 아니라 askBoo에 `{question: payload.question, force: "hold"}`로 질문함 저장). `ok`는 문장 끝에 인용 번호(HUFS GREEN 12px) + 근거 블록 「근거 원문 보기」를 펼치면 `cites` 순서로 원문. `lineId`는 `L-A{n}-{k}`(답 쓰기 줄, 신고 대상 아님 — 신고는 원문 문장에).
**[11/19] 규정 질문 판별(작업 18)**: 1단계보다 먼저 코드로 판별한다(AI 없음). 학교가 정하는 기준·금액·기한을 묻는 질문은 선배 경험으로 답하지 않고 공식 안내로 보낸다.
- 판별 표현: `평점|장학금|몇\s*학점|선발\s*(인원|기준)|휴학|등록금|초과학기|인정\s*신청|인정받을 수` (`가상질문` 36~45번이 `official`).
- **[11/23] 넓힌 판별 표현**(`askboo.OFFICIAL_WIDE_RE`, 원우 `tools/rule_probe.py` 제안에서 「자격증」만 뺌): 자격·참여/지원 조건·신청/접수/제출 기한·마감·언제까지·점수/어학/성적 기준·환산·파견 연장·중복 지원·불이익·포기/취소하면·지원 가능·학비·체재비·지원금 금액·마일리지·이수증·수료 기준·발표 언제 등. 이 표현은 **지난 경험을 묻는 말투**(`…했어요?`·`어땠`·`힘들`·`고민` 등, `EXPERIENCE_TONE`)이면 `official`로 보내지 않는다. 위 판별 표현에 걸리면 말투와 상관없이 `official`(예전보다 나빠지지 않게).
- 경험을 묻는 질문은 `official`이 아니다. "학점 인정 받을 때 주의할 점 있어요?"(5번)·"챙길 서류 있어요?"(15번)는 근거로 답한다. 그래서 "학점 인정"이라는 말만으로 판별하지 않는다.
- `officialUrl`: 질문에서 프로그램을 찾으면 `운영부서코드` → `departments.json`의 `공식안내URL`(getNote와 같은 순서). 프로그램을 못 찾으면 `현장실습|인턴` → D02, `특교원|탄뎀` → D03, 그 외 D01.
- 질문은 `questions.json`에 `status: "official"`로 저장한다. 내 보관함에는 「공식 안내」로 보이고, 콘솔 집계에 들어가며, `interviewNext`의 후배 질문으로는 쓰지 않는다.
**[11/19] 1단계 보강(작업 81)**: 프로그램명 글자 대조가 실패하면 `data/intern-keywords.json`(직군·기관 유형·업체 약칭 → 업체명, 원우)으로 후보 업체를 1~3개 고른다("무역 쪽 인턴" → KOTRA 해외무역관…). 후보가 여럿이면 각 업체의 근거를 합쳐 2~5단계로 넘기고 `sources`의 `program`으로 구분한다. 사전으로도 못 잡으면 `hold`. (P1-여건, 58③) 경량 임베딩: 사전 계산한 후기 문장 임베딩과 질문 임베딩의 코사인 상위 10문장을 후보 근거로 — 벡터 DB 없이 함수 안에서.
**[11/23 노트] 나라 이름·사람 찾기 질문**:
- ① 프로그램명·별칭·인턴 사전으로 못 찾으면 질문의 **나라 이름**(`programs.json` 국제교류의 `세부`)으로 그 나라 프로그램 중 근거가 있는 것을 근거 많은 순으로 고른다. 「독일어」「일본어」처럼 바로 뒤에 `어`가 오면 언어 이름이라 나라로 보지 않는다.
- 질문에 **주제어(②의 표)가 없고**, 사람을 찾는 표현(`다녀온|갔다 온|가 본|해 본|경험한` + `선배|사람|분`, `선배 있어요?`)이 있거나 나라 이름으로만 찾았으면 → **`status: "notes"`**: 답을 만들지 않고 그 해봤노트 카드(최대 5개, `evidenceCount` > 0인 것만)를 준다. AI 없음, 질문함에 저장하지 않는다(답할 질문이 아니라 길 안내). 주제어가 있으면(「네덜란드 교환 기숙사 어땠어요?」) 그 나라 프로그램들의 근거로 평소처럼 답한다.
- 주제어 표에 `준비`(지원·출국 전 준비 문항)를 더했다(「레이던 대학교 가려면 뭘 준비해요?」).
- `hold` 문구는 이유별: 프로그램을 못 찾음 → 「질문에 맞는 해봤노트를 찾지 못했어요. …」 / 노트는 있는데 이 내용이 없음 → 「{프로그램} 해봤노트에는 아직 이 내용이 없어요. …」 + **`noteId`**(화면이 노트 링크를 붙일 수 있음) / 근거가 하나도 없는 프로그램 → 기존 문구 「이 부분은 아직 경험한 선배가 없어요. …」. 세 문구 모두 「질문함에 담아 두었어요. 닮은 선배에게 물어볼까요?」로 끝난다. **[11/23 작업 87]** `force: "hold"`(chat 칩 「질문함에 담기」)는 학생이 직접 담은 것이라 「못 찾았어요」라고 하지 않고 「질문함에 담아 두었어요. 선배가 답하면 알려 드릴게요.」(`noteId` 없음, `suggestSenior: true`).
```json
{ "status": "notes", "lines": [], "sources": {}, "suggestSenior": true,
  "message": "네덜란드 해봤노트가 2개 있어요. 궁금한 노트를 골라 보세요.",
  "notes": [ { "noteId": "N-c158df", "program": "레이던 대학교", "type": "교환", "country": "네덜란드", "evidenceCount": 36 },
             { "noteId": "N-f03daf", "program": "흐로닝언대학교", "type": "교환", "country": "네덜란드", "evidenceCount": 24 } ] }
```
**[11/23 노트]** 카드 `type`(교환·파견·인턴·비교과)은 `listNotes` 카드의 `type`과 같은 값 — 분야 띠는 해봤노트 화면과 같은 규칙(`country`가 있으면 「교환학생 · 독일」).
화면(인터BOO 물어보기): `message` 말풍선 + 노트 카드(분야 띠·노트명·근거 N건, 누르면 `../note/?id=`) + 「닮은선배 보기」. 근거 블록은 두지 않는다(답이 아니므로). 노트가 1개면 `message`는 「{프로그램} 해봤노트에서 선배들의 경험을 볼 수 있어요. 궁금한 내용을 물어보셔도 돼요.」
**[11/19] 근거 풀** = `data/notes.json`의 문장 + `runtime/noteLines.json`의 동의 통과 문장(**[v2]** 후배 질문에 답한 문장은 질문의 칸에 들어가 있음). 그래서 선배가 답한 후배 질문은 다음 후배의 근거가 된다.
```json
{ "status": "ok",
  "lines": [ { "text": "...", "sourceId": "R03-1-1", "lineId": "L-R03-1-1" },
             { "text": "...", "sourceId": "R03-2-4", "lineId": "L-R03-2-4", "fallback": true } ],
  "sources": { "R03-1-1": { "docType": "귀국보고서", "program": "마르부르크필립스대학교", "semester": "2025-1" } },
  "noteId": "N-marburg", "suggestSenior": false }
{ "status": "hold", "lines": [], "sources": {}, "questionId": "Q-0001", "suggestSenior": true,
  "message": "이 부분은 아직 경험한 선배가 없어요. 질문함에 담아 두었어요. 닮은 선배에게 물어볼까요?" }
{ "status": "official", "lines": [], "sources": {}, "questionId": "Q-0002", "suggestSenior": false,
  "officialUrl": "https://oia.hufs.ac.kr",
  "message": "학교 규정에 관한 질문이라 국제교류팀 공식 안내에서 정확한 내용을 확인해 주세요." }
```
docType: `귀국보고서` | `현장실습후기` | `인터뷰`
**[11/19] `lines[].fallback`(작업 18)**: AI가 바꾼 문장이 사후 검증(HCX 원칙 v2 3절 5단계: 원문에 없는 숫자·영문·고유명사·새 낱말, JSON 형식 오류, 반말)에 걸려 **근거 원문을 그대로 보여 준 줄**이면 `true`. 원문에서 앞머리 군말(「참고로」 등)과 「ㅎㅎ」·「!!」만 지우고 낱말은 바꾸지 않는다. AI 문장이면 이 필드를 넣지 않는다(없으면 거짓). 화면은 이 줄에 「근거 원문 보기」 표시를 붙일 수 있고, 무시해도 문장은 정상으로 보인다.
**[11/23 작업 30]** 군말·꾸밈만 지우면 이미 해요체·합쇼체로 끝나는 근거는 **AI에 보내지 않고** 그 정리본을 그대로 쓴다. 이 줄은 검증에 걸린 것이 아니므로 `fallback`을 넣지 않는다. 변환(AI)은 반말·명사형 등으로 끝나는 근거만 받는다.

### interviewNext(program, answers)
선배 인터뷰에서 다음 질문 하나. payload `{program, answers:[{section, question, answer, questionId?, skipped?}]}`
```json
{ "done": false, "section": "생활", "junior": true, "questionId": "Q-0001", "asked": "마르부르크에서 학기 중 현지 인턴 병행할 수 있어요?",
  "question": "후배가 이렇게 물었어요 — \"마르부르크에서 학기 중 현지 인턴 병행할 수 있어요?\" 경험이 있으면 들려주세요.",
  "progress": { "filled": 0, "mine": 0, "total": 6 }, "covered": ["지원", "학점", "비용", "생활", "팁"], "pendingQuestions": 1 }
{ "done": false, "section": "팁", "question": "후배들이 마르부르크에 대해 잘 모르고 있는 것, 또는 잘못 알고 있는 게 있다면요?", "depth": true,
  "covered": ["지원", "학점", "비용", "생활", "팁"], "progress": { "filled": 1, "mine": 1, "total": 6 }, "pendingQuestions": 0 }
{ "done": false, "section": "학점", "question": "학점 칸은 최근 경험이 없어요. 마르부르크에서 들은 수업과 학점 인정은 어땠어요?", "covered": ["지원", "비용", "생활", "팁"], "progress": { "filled": 1, "mine": 1, "total": 6 } }
{ "done": true, "progress": { "filled": 4, "mine": 4, "total": 6 }, "covered": ["지원", "학점", "비용", "생활", "팁"] }
```
`total`은 그 프로그램 종류의 `frames.json` 칸 수(**[v2] 교환·파견 6**, 인턴 5, 비교과 2 — 「후배 질문」 칸 삭제). `배운점`은 다른 칸을 묻고 난 뒤 마지막에 묻는다.
**[v2] 후배 질문은 칸이 아니라 질문이다.** 질문함 질문을 먼저 묻는 것은 그대로이고, 응답에 `junior: true`·`questionId`·`asked`가 붙으며 **`section`은 그 질문이 속한 칸**(질문 행의 `칸`. 없으면 서버가 `문단분류` 프롬프트로 틀 안의 칸 하나를 고르고, 틀 밖 응답은 교환·파견 「팁」, 인턴·비교과 「배운점」)이다. 답은 그 칸에 담기고 `progress.filled`에도 센다. 건너뛰기(`skipped`)는 그대로. 진행 칩에 「후배 질문」 칩은 없고, `pendingQuestions`가 1 이상이면 화면이 안내 라벨 「후배 N명이 이 경험을 기다리고 있어요」만 보인다.
**[v2] 진행률**: `progress.filled` = 내가 답한 칸 수, `progress.mine`은 같은 값(이름을 분명히 하려고 둘 다 보냄), `covered`는 보고서가 이미 채운 칸. 화면은 「내 이야기 N칸 · 보고서 M칸」으로 보여 주고 `covered` 칸 칩은 「보고서」(중립색, 11/23 미리 결정으로 짧게). `done` 문구는 「지금 물을 건 다 물었어요. 더 들려줄 칸을 고르거나 AI 요약을 눌러 주세요」.
**[v2] 이어 쓰기(내 경험노트 반영)**: 서버는 `myNotes.json`에서 **같은 사람·같은 프로그램의 내 경험노트**를 읽어 문장이 있는 칸을 답한 것으로 친다(`answers`에 없어도). 그래서 다시 온 선배에게는 새 후배 질문·아직 안 한 깊이 질문·빈 칸만 묻고, 첫 응답에 `resumed: true`와 `myNoteId`가 붙는다(화면: 「이어서 들려주기 · 내 이야기 3칸」). 화면은 `../talk/?mode=tell&program=…`으로 들어오면 경험 선택 없이 바로 시작한다.
**[11/19] 질문 순서(작업 74)**: ① 서버가 `questions.json`에서 **같은 프로그램**의 `status: "hold"` 질문을 최근순으로 최대 3개 꺼내 먼저 묻는다(**[v2]** `junior: true`, `section` = 그 질문의 칸, `questionId`, `asked` = 후배 질문 원문. 본인이 한 질문·이미 `answered`·`deleted`인 것은 뺀다). 화면은 「경험이 없어요」 버튼을 두고, 누르면 `answers`에 `{questionId, skipped: true}`로 보내 건너뛴다(질문은 `hold` 유지, 다른 선배에게 다시 나온다). ② **[11/22] 보고서가 이미 답한 칸은 다시 묻지 않는다**: 그 뒤 근거(보고서 + 동의 통과 인터뷰 문장)가 **0건이거나 모두 2년 넘은 칸만** 기본 질문(근거 적은 칸 순, 오래된 칸은 「○○ 칸은 최근 경험이 없어요.」 머리말 — 디자인 규칙 6-2와 같은 기준). ③ **깊이 질문**(`depth: true`, 교환·파견 3개·인턴·비교과 2개): 보고서에 잘 안 쓰는 판단·비교·후회·오해를 묻는 고정 문장(`interview.py` `DEPTH_QUESTIONS`, 종류별 2~3개 중 근거 적은 칸에 담기는 것부터 — AI가 만들지 않음). 답은 그 칸에 담긴다. ④ `배운점` 마지막. 근거가 충분해 묻지 않은 칸은 **`covered`**(칸 이름 목록)로 매 응답에 알린다 — 화면은 진행 칩에서 비어 있지 않게(예: 「보고서」) 보여 주고, `done`이면 「노트 틀을 모두 채웠어요」 대신 답한 칸 기준 문구를 쓴다(민지). 마르부르크(지원15·학점15·비용5·생활20·팁5)는 후배 질문 → 팁(깊이) → 지원(깊이) → 생활(깊이) → 배운점. 꼬리 질문은 각 칸의 첫 답에 그대로 붙는다. **[v2]** 질문함 질문의 답도 그 칸에 담기므로 `progress.filled`에 세고, 남은 질문 수는 `pendingQuestions`로 따로 알린다.
**[11/19] `examples`(P1-여건, 작업 84)**: `frames.json`의 칸별 `예시`가 있으면 2~3개를 함께 보낸다. 화면은 칩으로 보여 주고 탭하면 입력창에 채운다. 없으면 생략.
**[11/23] 칩이 붙는 질문**: 기본 질문(②)·배운점(④)은 `frames.json` 칸 예시, 깊이 질문(③)은 질문마다 정한 예시(`DEPTH_QUESTIONS` 세 번째 값). 후배 질문·꼬리 질문에는 없다. **말머리만 보낸 답**: 답이 `…`로 끝나는 칩의 앞부분뿐이면(「가장 크게 배운 건 …」, `…`를 지우고 보내도 같음) 서버는 그 답을 없던 것으로 치고 같은 질문을 `"조금만 더 이어서 써 주세요. " + 원래 질문`으로 다시 묻는다(`retry: true`, 같은 `examples`). 화면은 그 질문 그대로 `answers`에 넣으면 되고, 서버가 머리말을 떼고 원래 질문으로 센다. `summarizeInterview`도 그런 답은 뺀다.

### summarizeInterview(program, transcript, append?)
payload `{program, transcript:[{section, question, answer, questionId?}], append?: true}`. 두 장을 돌려준다: 내 경험 노트(1인칭, 나만 봄)와 공개용 초안(선배가 고치고 동의해야 공개).
**서버는 응답과 함께 myNote를 내 경험노트로 저장한다**(`saved: true`, `myNoteId`). 화면은 "내 경험노트에 저장됨"을 표시하고, 공유는 이후 `saveConsent`로만 한다. 같은 프로그램으로 다시 요약하면 같은 `myNoteId`를 갱신한다.
**[v2] `append: true`(이어 쓰기)**: 같은 프로그램의 내 경험노트가 있으면 **기존 문장을 지우지 않고** 이번 transcript로 만든 새 문장을 칸 뒤에 덧붙인다. 공개 초안의 새 문장은 새 `lineId`(`L-D{n}-{k}`, `n`은 새 draftId), 기존 문장의 `edited`·공유 상태·동의는 그대로. 응답 `myNote`·`publicDraft`는 **합친 전체**이고 새 문장에 `new: true`. `draftId`는 새 값이며 `saveConsent(draftId)`는 합친 초안 전체를 대상으로 한다. `append`가 없으면 지금처럼 통째로 바꾸고, 화면은 `editedLines ≥ 1`이면 「다시 요약할까요?」 확인(getInbox 참고). `../talk/?mode=tell&program=…`으로 들어온 이어 쓰기와 질문이 끝난 뒤 「이어서 쓰기」는 모두 `append: true`로 부른다. `answered`는 기존 값과 이번 값 중 큰 쪽.
**[v2] 후배 질문의 답**: transcript 항목에 `questionId`가 있으면 그 답은 **그 항목의 `section`(질문의 칸)**에 들어가고 문장에 `answersQuestionId`·`asked`가 붙는다(「후배 질문」 칸은 없다). 화면의 요약 카드는 그 문장 앞에 「Q. …」 인용을 작게 보여 준다.
`match`는 AI 원문 일치 검사 결과. `false`면 화면이 "원문과 다를 수 있어요" 표시.
`identifying`은 코드(정규식·사전)가 찾은 본인 식별 문장(성적 숫자·수상·실명·특정 인물). `true`면 동의 시트에서 기본 꺼짐 + 주의 라벨.
**[11/22 열림]** 응답에 `answered`(이번 transcript의 유효 답변 수 — 서로 다른 질문, 10자 이상, 「몰라요」류·건너뛰기 제외)와 `need`(3)를 더한다. 서버는 내 경험노트에 큰 값을 남긴다. 화면은 `answered < need`면 공유 시트에 「세 가지 이상 이야기하면 선배 추천이 열려요」를 안내한다(요약·공유 자체는 막지 않음).
**[11/19]** 후배 질문에 답한 문장은 `answersQuestionId`·`asked`(질문 원문)를 유지한다(**[v2]** 칸은 질문의 칸). myNote·publicDraft 모두 같다. 요약 전에 transcript는 0장 마스킹을 거친다.
```json
{ "draftId": "D-0001", "program": "마르부르크필립스대학교", "saved": true, "myNoteId": "M-0001",
  "myNote": { "sections": [ { "name": "지원", "lines": [ { "text": "나는 출국 3학기 전부터 TestDaF를 준비했다." } ] },
                           { "name": "배운점", "lines": [ { "text": "낯선 행정 절차를 혼자 끝까지 처리하는 법을 배웠다." } ] } ] },
  "publicDraft": { "sections": [ { "name": "지원", "lines": [ { "lineId": "L-D1-1", "text": "출국 3학기 전부터 TestDaF를 준비했어요.", "match": true, "identifying": false } ] },
                                 { "name": "생활", "lines": [ { "lineId": "L-D1-7", "answersQuestionId": "Q-0001", "asked": "마르부르크에서 학기 중 현지 인턴 병행할 수 있어요?",
                                                                      "text": "학기 중에는 수업이 많아 인턴은 어렵고, 방학에 단기 인턴을 했어요.", "match": true, "identifying": false } ] } ] } }
```

### saveConsent(draftId, edits)
payload `{draftId, edits:{removed:[lineId], changed:[{lineId, text}]}, consent:true}`. `removed` = 동의 시트에서 끈 문장(내 경험노트에는 남고 해봤노트에는 안 들어감). 이미 공유한 경험노트에서 다시 부르면 공유 범위를 바꾼다.
**[11/19]** 통과한 문장은 `runtime/noteLines.json`에 `{noteId, section, text, sourceId: "I-…", semester, answersQuestionId?, asked?}`로 쌓인다(작업 26·74). **[v2]** `section`은 질문의 칸이고(「후배 질문」 칸 없음), 삭제된 질문(`status: "deleted"`)에 답한 문장은 칸 문장으로 싣되 `answered` 전환·알림은 하지 않는다. `answersQuestionId`가 있으면 그 질문을 `status: "answered"`, `noteId`로 바꾸고 질문자에게 알림 `「내 질문에 선배가 답했어요 · {프로그램} 해봤노트」`(`alerts.json`, `questionId`·`noteId` 포함)를 보낸다. **칸 이름이 같다는 이유만으로 알림을 보내지 않는다.** 노트가 아직 없는 프로그램이면 새 노트 id를 만든다(`"N-" + slug`).
```json
{ "ok": true, "noteId": "N-marburg", "added": 3, "answered": ["Q-0001"],
  "recommend": { "ready": true, "by": "talk", "need": 3, "talk": { "answered": 4, "shared": 3 }, "ask": false }, "unlocked": true }
```
**[11/22 열림]** `unlocked: true`면 이번 공유로 선배 추천이 처음 열린 것 → 화면 토스트 「선배 추천이 열렸어요」.
**[11/20]** `changed`의 문장은 저장 전에 `functions/msg_check.py`의 `check_public_text`로 다시 검사한다(학번·연락처·메일·링크·주소·금지어). **걸린 문장만 공개에서 빼고**(내 경험노트에는 남음) 나머지는 저장하며, 응답에 `rejected`를 붙인다. 화면은 문장마다 `message`를 보여 준다.
```json
{ "ok": true, "noteId": "N-marburg", "added": 2,
  "rejected": [{ "lineId": "L3", "reason": "연락처", "message": "해봤노트에는 연락처·메일·링크·주소를 넣을 수 없어요." }] }
```
**[11/23 고치기]** 공개 동의 시트의 「문장 고치기」(`common/consent.js`)가 `changed`를 보낸다. 서버 규칙:
- 앞뒤 공백을 지운다. 빈 문장은 고침으로 보지 않는다(원래 문장 그대로 — 공개하지 않으려면 `removed`). **300자**를 넘으면 그 문장만 `rejected`(`reason: "길이"`).
- 검사를 통과한 고친 문장은 해봤노트(`noteLines.json`)뿐 아니라 **내 경험노트의 공개 초안**(`myNotes[…].publicDraft`)에도 남긴다: `text` = 고친 문장, `edited: true`, `aiText` = 처음 AI가 만든 문장(처음 고칠 때 한 번만), `match`는 지운다(선배가 직접 쓴 문장은 원문 일치 검사 대상이 아님), `identifying`은 다시 검사한 값. 그래서 `getMyNote`의 `publicText`·`publicDraft`에 고친 문장이 나오고, 「공유 범위 바꾸기」로 다시 공유해도 AI 문장으로 돌아가지 않는다. 거절된 문장은 공개 초안을 바꾸지 않는다.
- **내 경험노트 문장(`myNote`)은 바꾸지 않는다.** 두 노트는 읽는 사람이 달라(본인 / 처음 보는 후배) 표현이 다를 수 있으므로 따로 고친다(내 경험노트 고치기는 `updateMyNote`).
- 화면: 문장 아래 Text 버튼 「문장 고치기」 → 입력창(라벨 「해봤노트에 보일 문장」, 안내 「내 경험노트 문장은 그대로예요. 연락처·메일·링크는 넣을 수 없어요.」) + Secondary 「저장」 / Text 「취소」. 고친 문장(이번에 고친 것·`edited: true`)에는 중립 라벨 「내가 고친 문장」, 「원문과 다를 수 있어요」는 붙이지 않는다. 고치는 중에는 「동의하고 공유」 비활성 + 「고치는 중인 문장을 저장하거나 취소해 주세요」.

### listNotes(filter)
payload `{filter:{type?: "교환"|"파견"|"인턴"|"비교과", q?: "검색어", country?: "독일", kind?: "공공기관"}}`   // country·kind [11/23 주제별]
```json
{ "notes": [ { "id": "N-marburg", "program": "마르부르크필립스대학교", "type": "교환",
  "oneLine": "TestDaF는 3학기 전부터, 기숙사는 합격 직후 신청", "forWhom": "독일어권 교환을 생각하는 1~2학년",
  "evidenceCount": 7, "lastSemester": "2026-1", "satisfaction": null, "completedCount": null, "country": "독일", "scrapped": true },
  { "id": "N-3ca17d", "program": "HUFS 동문멘토링 데이", "type": "비교과",
  "oneLine": "", "forWhom": "2학년이 많이 이수한 비교과", "evidenceCount": 0, "lastSemester": "2026-1", "satisfaction": 4.2, "completedCount": 150, "country": null, "scrapped": false } ] }
```
**[11/22]** `country`는 국제교류(교환·파견) 노트만 `programs.json`의 `세부`(국가) 글자 그대로, 인턴·비교과는 `null` → 카드 띠는 「교환학생 · 독일」, `null`이면 종류만. `scrapped`는 부른 사람(토큰) 기준 스크랩 여부. `oneLine`이 `""`이면 화면은 「–」(6-2).

**[11/23 주제별 묶기]** 해봤노트 목록을 주제별로 묶어 보여 주기 위한 값. AI 없음.
- 카드 `kind`(기관유형): **인턴 노트만** `programs.json`의 `세부` 글자 그대로(예: `"공공기관"`, `"KOTRA 해외무역관"`), 교환·파견·비교과는 `null`. `getNote`에도 같은 값.
- payload에 `filter.country?`(국가, 교환·파견), `filter.kind?`(기관유형, 인턴)를 더 받는다. 글자가 같은 카드만 남긴다. `type`·`q`와 함께 쓸 수 있다.
- 응답에 `groups: { country: [{name, count}], kind: [{name, count}] }` — 묶음 칩용. **`type`·`q`로 거른 뒤, `country`·`kind`로 거르기 전** 카드로 센다(칩 하나를 눌러도 다른 칩이 그대로 보이게). 노트 수 많은 순, 같으면 가나다순. 값이 `null`인 카드는 세지 않는다 → `type: "인턴"`이면 `country`는 `[]`, `type: "비교과"`면 둘 다 `[]`.
- 순서: **비교과 카드는 `completedCount`(이수 인원) 많은 순**(`null`은 뒤). 교환·파견·인턴 카드의 순서는 지금과 같다(`notes.json` 순서). 전체 목록에서 비교과 카드끼리만 자리를 바꾼다.
```json
{ "notes": [ { "id": "N-kotra", "program": "KOTRA 해외무역관(유럽 권역)", "type": "인턴", "country": null, "kind": "KOTRA 해외무역관", "...": "..." } ],
  "groups": { "country": [], "kind": [ { "name": "중소 무역회사", "count": 5 }, { "name": "공공기관", "count": 4 } ] } }
```
mock은 거르지 않는다(카드 3개 고정, `groups`는 실제 서버 전체 목록 값). 화면은 `type`을 고르면 그 종류에 맞는 칩 줄(교환·파견 = 나라, 인턴 = 기관유형, 비교과 = 칩 없음)을 보여 준다.

### scrapNote(noteId, scrap) [11/22]
payload `{noteId, scrap?: true|false}`(생략 = 켜기). 같은 상태로 다시 불러도 `ok`(멱등). 기록은 `runtime/scraps.json`(사람별 노트 id 목록). AI 없음.
```json
{ "ok": true, "noteId": "N-marburg", "scrapped": true }
{ "error": "노트를 찾지 못했어요" }
```
mock은 기억하지 않는다(받은 값을 그대로 돌려주고, 목록·노트의 `scrapped`는 mock-data.json 고정값). 화면은 응답의 `scrapped`로 버튼 상태를 바꾼다.

### saveQuestion(noteId, section) [11/22]
「질문함에 담기」 버튼(디자인 규칙 6-2 근거 없음 · 6-1 오래된 근거, PRD ⑧). 그 노트의 한 칸을 **질문함에 `hold`로** 넣는다 → 다음 선배 인터뷰(`interviewNext`)가 「후배가 이렇게 물었어요」로 먼저 묻고, 답이 공유되면 `answered` + 질문자 알림(기존 흐름 그대로). 질문 글은 서버가 정한다(`"{칸} 이야기를 최근 경험으로 듣고 싶어요."`, 자유 입력 없음 → 검사·AI 없음). 같은 사람·노트·칸의 `hold` 질문이 있으면 새로 만들지 않고 `already: true`(멱등). 노트에 없는 칸은 오류(**[v2]** 「후배 질문」 칸은 없다).
```json
{ "ok": true, "questionId": "Q-0101", "already": false, "message": "질문함에 담았어요. 다음 선배 인터뷰 때 먼저 물어볼게요." }
{ "error": "담을 수 없는 칸이에요" }
{ "error": "노트를 찾지 못했어요" }
```
화면은 `message`를 토스트로 보여 주고, 버튼을 「질문함에 담았어요」(비활성)로 바꾼다. mock은 고정값을 돌려준다.

### getNote(id)
칸 순서와 이름은 `data/frames.json`을 따른다. 빈 칸도 `lines: []`로 보낸다. `interviewOnly`가 true인 칸은 선배 인터뷰로만 채워진다.
**[11/19] 노트가 만들어지는 규칙(작업 26, PRD 4-2)**: 노트 = `data/notes.json`(사전 생성) + `runtime/noteLines.json`(동의 통과 인터뷰 문장)의 합집합.
- `tools/build_notes.py`(원우)가 `evidence.json`을 프로그램별·칸별로 묶어 `notes.json`을 만든다. 칸 문장 = 근거 문단 **원문 그대로 1:1**(`text` = `evidence.text`, `sourceId` = `evidence.id`, AI 변환 없음). `official`은 학점·장학·선발·자격 키워드 정규식. `forWhom`은 템플릿(`"{국가}권 {분야}를 생각하는 1~2학년"` / 인턴 `"{직군} 분야 현장실습을 생각하는 2~3학년"`), `oneLine`은 근거가 가장 많은 칸의 첫 문장(작업 78은 칸별 요약 문단 `summary`로 재정의 — 아래 [v2]), `evidenceCount` = 보고서 문단 + 동의 인터뷰 문장, `lastSemester` = 최대 학기. 현장실습 노트의 자동 분류 문장은 `autoClassified: true`(화면 「자동 분류」 라벨).
- 서버는 응답할 때 `noteLines.json`의 같은 `noteId` 문장을 해당 칸 뒤에 붙인다(`docType: "인터뷰"`). **[v2] 「후배 질문」 칸은 없다.** 후배 질문에 답한 문장은 질문의 칸에 일반 문장으로 들어가며 `answersQuestionId`·`asked`를 유지한다 → 화면은 그 문장에 중립 라벨 「후배 질문에 답한 문장」만 붙인다(Q는 보이지 않음). Q·A 쌍은 질문자의 내 보관함 질문 상세에서만 본다. 같은 질문에 선배 여럿이 답하면 그 칸에 문장이 여럿 쌓인다.
- **[v2, 작업 78 — 11/23 P0] 칸별 요약 문단 `summary`**: `tools/build_notes.py`(원우 파일 — 미리가 만듦)가 칸마다 askBoo ⑤ 「답 쓰기」 프롬프트를 질문 없이 돌려 만든다. `summary: [{text, sources: ["R213-6", …], years: [2023, 2026]}]`, 문장마다 `sources` 1개 이상, 코드 검증(askBoo ⑥과 같음)을 통과한 문장만. 같은 뜻 문장은 하나로 합치고 연도를 묶는다. **배운점은 만들지 않는다**(선배별 원문 인용 유지). 인터뷰로 새 문장이 들어와도 문단은 다시 만들지 않는다(화면: 문단 아래 「새로 더해진 선배 이야기 N건」 원문). 없으면 필드 생략 → 화면은 지금처럼 원문 목록. **[11/23] 전체 노트에 적용했다**(#193: 448칸 중 436칸·1,530문장, 다 버려진 12칸은 `summary` 없음 → 원문 목록). 11/24 품질 확인 뒤 문제가 있는 노트만 다시 만든다.
  - **[11/23 작업 78, #188] 만드는 방법**(`tools/build_notes.py`, 원우 파일 — 미리가 만듦): `python tools/build_notes.py --summary N-marburg[,N-…]`가 그 노트의 칸마다 AI를 불러 결과를 **`data/note-summaries.json`**(`{noteId: {칸: [{text, sources, years}]}}`)에 보존하고 이어서 `notes.json`을 다시 만든다. 칸 문단을 문장으로 쪼개 번호를 붙이고 askBoo ⑤ 「답 쓰기」를 질문 없이(「칸 정리」) 돌린 뒤 ⑥ 검증(`askboo.compose` 그대로: 근거 번호 없는 문장·반말 버림, 숫자·영문·고유명사·수량 코드 검사, 문장마다 답 검사)을 통과한 문장만 남긴다. 다 버려진 칸은 `summary` 없음. 배운점·인터뷰로만 칸은 만들지 않는다. **인자 없는 생성은 AI를 부르지 않고** `note-summaries.json`을 칸에 입히기만 하므로 칸 원문이 바뀌어도 문단은 자동으로 다시 만들어지지 않는다. `--check`는 AI 없이 출처가 그 칸 문장인지·`years`·해요체·숫자 검사를 다시 본다. 지금은 전체 121개 노트가 들어 있다(#193, 배운점 제외).
  - **[11/23 작업 78] 칸 상한·중복·official**(`apply_summaries`, AI 없음 — 생성 때 적용, `--check`가 다시 봄): 칸 근거(문단) 5건 이하면 요약 3문장, 그 외 5문장까지(AI에도 그 수를 요청, 넘으면 뒤에서 자름). 앞 칸(틀 순서)의 요약 문장과 같은 뜻인 문장(두 글자 묶음이 짧은 쪽 기준 45% 이상 겹침, 「~다는 선배도 있었어요」 같은 꼬리는 빼고 비교)은 뒤 칸에서 뺀다. 인용한 칸 문장 중 `official: true`가 하나라도 있으면 요약 문장도 `official: true`(없으면 `false`) → 화면은 칸 문장과 같은 공식 확인 표시.
  - **[11/23 작업 78, P0] 서버가 넘기는 규칙**(`functions/notes.py`, AI 없음): `notes.json`의 칸 `summary`를 그대로 보내고, 같은 칸에 **`newLines`**(요약을 만든 뒤 인터뷰로 붙은 문장 수 = `runtime/noteLines.json`에서 온 문장 수)를 붙인다. 인터뷰 문장은 늘 칸 `lines` **끝**에 붙으므로 화면은 `lines`의 마지막 `newLines`개를 「새로 더해진 선배 이야기 N건」으로, 나머지를 「원문 N건 보기」 접기로 보여 준다(`newLines` 0이면 새 이야기 줄 없음). 배운점 칸은 `summary`가 있어도 보내지 않는다. 신고로 숨긴 문장을 `sources`에 든 요약 문장은 뺀다. 요약 문장이 하나도 안 남으면 `summary`·`newLines` 둘 다 생략. `summary`가 없는 칸에는 `newLines`도 없다.
- **[11/22] 배운점 `senior`**: 배운점 칸 문장마다 `"senior": "선배 A"`. 글자는 **이 노트 안에서만** 쓰는 것으로, 칸에 처음 나온 선배부터 A·B·C(같은 선배는 같은 글자). 학과는 넣지 않는다 — PRD 9-1(노트가 프로그램 단위라 학과까지 보이면 소수 학과에서 특정됨). 닮은선배 `nickname`과도 같은 글자를 쓰지 않는다(이으면 학과가 드러남). 화면은 「선배 A · 2025」(senior + 출처 연도). 쓴 사람을 모르면 `senior`가 없다 → 출처만.
- `sources[*].semester`는 그대로 보내고 화면이 연도만 표시한다(0장). 근거 1~2건인 칸은 화면이 「선배 1명의 경험이에요」 라벨(`lines.length`로 판단, 서버 필드 없음).
```json
{ "id": "N-marburg", "program": "마르부르크필립스대학교", "type": "교환",
  "oneLine": "...", "forWhom": "...", "evidenceCount": 7, "lastSemester": "2026-1", "satisfaction": null, "completedCount": null,
  "country": "독일", "scrapped": true,   // [11/22] listNotes와 같음
  "officialUrl": "https://...",
  "sections": [ { "name": "지원", "interviewOnly": false,
                  "lines": [ { "text": "...", "sourceId": "R03-1-1", "lineId": "L-R03-1-1", "official": false } ] },
                { "name": "생활", "interviewOnly": false,
                  "summary": [ { "text": "기숙사는 합격 직후 신청해야 하고 월 300~680유로 사이였어요.", "sources": ["R03-2-4", "R149-2-4"], "years": [2025, 2026] } ],   // [v2] 작업 78(11/23 P0), 없으면 생략
                  "newLines": 1,   // [11/23] summary 있을 때만: lines 끝 1개가 요약 뒤 인터뷰로 붙은 문장
                  "lines": [ { "text": "...", "sourceId": "R03-2-4", "lineId": "L-R03-2-4", "official": false },
                             { "asked": "마르부르크에서 학기 중 현지 인턴 병행할 수 있어요?", "answersQuestionId": "Q-0001",
                               "text": "학기 중에는 수업이 많아 인턴은 어렵고, 방학에 단기 인턴을 했어요.", "sourceId": "I-0003", "lineId": "L-I-0003", "official": false } ] } ],
  "sources": { "R03-1-1": { "docType": "귀국보고서", "program": "마르부르크필립스대학교", "semester": "2025-1" },
               "I-0003": { "docType": "인터뷰", "program": "마르부르크필립스대학교", "semester": "2025-1" } } }
```
`satisfaction`은 비교과 노트만 숫자(`가상비교과만족도`의 `만족도(5점)`), 국제교류·현장실습은 `null` → 화면은 "–"(실제 체계에 학생별 만족도가 없음).
**[11/20]** `completedCount`(이수 인원)도 비교과 노트만 숫자(`가상비교과만족도`의 `이수 인원(가상)`), 교환·파견·인턴은 `null`. 노트 커버에 「이수 n명 · 만족도 4.2」처럼 보여 주는 용도만 쓰고 닮은선배·콘솔 집계에는 쓰지 않는다. `evidenceCount`(근거 문장 수)와 다른 값이다.
`official: true`인 문장(학점 인정·장학금·자격 요건·선발 기준 같은 규정성 진술)은 화면이 "개인 경험이에요" 표시 + `officialUrl` 링크를 붙인다.
`officialUrl`은 서버가 **프로그램의 `운영부서코드` → `departments.json`의 `공식안내URL`** 순서로 찾아 넣는다(프로그램 목록 시트에는 URL 열이 없다, PRD 6-2).

### recommendSeniors(noteId, more)
payload `{noteId, more?: true}`. `nickname`은 서버가 만든 선배 표시명 「학과 + 선배 + 영문 대문자」(예: `"독일어과 선배 A"`, 디자인 규칙 1-2절). 같은 선배는 닮은선배·프로필·쪽지창에서 같은 이름이다. **[11/22]** 해봤노트 배운점 인용은 이 이름을 쓰지 않고 노트 안에서만 쓰는 「선배 A」(getNote `senior`, PRD 9-1). 점수 계산은 `functions/score.py`(원우). AI 없음.

**[11/20 개정] 후보·점수 규칙 (작업 22):**
- 후보 = 그 노트(희망 프로그램)의 경험자 **전부**. 점수 하한은 없다(단과대가 달라도 그 경험을 한 선배는 추천한다). 직원 행·본인은 뺀다. **[11/23 추천]** 추천받기를 끈 선배(`setRecommendable(false)`)도 뺀다 — `score.rank_seniors` 결과를 `runtime_fns.recommendSeniors`가 거른다.
- 점수(순서용): **학과 일치 5 · 이중전공 일치 4 · 단과대 일치 3 · 공통 비교과 2**(공통 비교과가 여러 개여도 2점 한 번). 학과가 같으면 단과대도 같으므로 같은 학과 선배는 8점 이상이다.
- 정렬: 점수 내림차순 → 동점이면 ① 수락 대기 요청이 적은 선배 ② 최근 학기에 다녀온 선배 순.
- `reasons` 맨 앞은 항상 **「희망 프로그램을 경험했어요」**, 겹치는 점이 있으면 그 뒤에 더한다(0점 선배도 카드가 비지 않는다).

**인원 규칙(11/18, 11/20 개정, PRD 2-2·4-1):**
- 상한 **9명은 "한 번에 보이는 목록"의 크기**다(평생 누적 9명이 아니다). 목록은 늘 위 정렬의 상위 9명이다.
- 처음에는 상위 3명, `more: true`면 3명씩 더해 최대 9명. 9명에 닿았거나 후보가 바닥나면 `hasMore: false`. 날짜·횟수 제한은 없다.
- 지금 목록(studentId 순서)은 보는 사람·noteId별로 `shownSeniors.json`에 노트 버전과 함께 저장한다. 다시 계산하는 때는 세 가지뿐이고, 그 밖에는 저장된 목록을 그대로 돌려준다(호출할 때 버전 숫자만 비교).
  - 그 노트에 새 경험이 공유될 때(saveConsent → 노트 버전 +1) — P0
  - 학기가 바뀔 때(학기마다 1회 일괄) — P1
  - 보는 사람의 비교과·이중전공이 바뀔 때(`recomputed: true`) — P1
- **[11/22 열림] 잠김**: 경험 나눔·수요 제공 전에는 목록 대신 `{ "locked": true, "message": "경험을 들려주거나 궁금한 것을 정리하면 선배 추천이 열려요", "recommend": {…getMe.recommend와 같음} }`. 화면만이 아니라 서버가 막는다.
- 다시 계산해서 새로 들어온 선배 수는 `newCount`로 알린다(화면 배지 「새로 비슷한 선배 N명」).
- 목록에서 밀려난 선배는 보관함에 남기지 않는다. **쪽지를 주고받은 선배만** 「닮은선배 · 내 쪽지」에 남는다(**[11/23]** 쪽지 목록은 내 보관함이 아니라 닮은선배 안)(「선배 저장」 최대 9명은 P1).
- 글자는 `nicknames.json`에 만난 순서대로 따로 기억하므로, 목록에서 빠졌다가 다시 나타나도 같은 사람은 같은 글자다(I 다음은 J, K…).
- 받는 한도: 선배의 수락 대기(`waiting`) 요청이 **5건**이면 그 선배 카드에 `requestsFull: true`. 화면은 「지금은 요청이 많아요」를 보이고 쪽지 버튼 대신 「질문함으로 묻기」를 둔다(sendMessage 요청 한도 참고).
- **[11/24 retryAt]** 내가 쪽지 요청을 **취소한** 선배이고 아직 7일이 지나지 않았으면 그 카드에 `retryAt`(다시 보낼 수 있는 시각, ISO KST `+09:00`, 취소 시각 + 7일)이 붙는다. 7일이 지났거나 취소한 적이 없으면 필드가 없다. 화면은 쪽지 버튼을 비활성으로 두고 「11월 30일부터 다시 보낼 수 있어요」처럼 날짜를 보인다. 거절(`declined`)·만료(`expired`)에는 붙지 않는다 — 거절은 다시 보낼 수 없고, 만료는 바로 다시 보낼 수 있다.
```json
{ "seniors": [ { "studentId": "H0469", "nickname": "독일어과 선배 A", "score": 14, "requestsFull": false,
                 "reasons": ["희망 프로그램을 경험했어요", "같은 서양어대학", "같은 독일어과", "이중전공 경영학 같음", "한국외국어대학교 직무탐색 집중교육 함께 이수"] },
               { "studentId": "H0241", "nickname": "독일어과 선배 B", "score": 12, "requestsFull": false,
                 "reasons": ["희망 프로그램을 경험했어요", "같은 서양어대학", "같은 독일어과", "이중전공 경영학 같음"],
                 "retryAt": "2026-11-30T09:00:00+09:00" } ],
  "shown": 2, "hasMore": false, "newCount": 0 }
```
`hasMore: true`일 때만 화면에 「선배 더 보기」를 두고, `false`면 「비슷한 선배를 모두 보여드렸어요」를 보인다. 시연 mock은 후보가 2명이므로 첫 화면부터 `hasMore: false`다.

### checkMessage(text)
payload `{text}`. 연락처·학번은 코드(정규식), 비방은 AI 판정. **[11/20]** 코드 검사는 `functions/msg_check.py`의 `check_message`(작업 27): 연락처·학번은 `mask.find()`(callAI 마스킹과 같은 규칙)에서 메일만 뺀 것 — 학번(`H`+숫자, 9자리, `staff`)은 `학번`, 전화·한글로 쓴 번호·메신저 아이디·주소(건물번호·동·호)·링크는 `연락처` — 에 금지어(명백한 욕설) `비방`을 더한다. 숫자 8자리 규칙은 쓰지 않는다('2024 2025학년도' 오탐).
```json
{ "ok": true }
{ "ok": false, "reason": "연락처", "message": "전화번호나 SNS 아이디는 보낼 수 없어요. 이메일은 괜찮아요." }
```
reason: `연락처` | `학번` | `비방`

### sendMessage(to, text)
payload `{to, text}`. `to`는 상대 studentId. 첫 메시지는 쪽지 신청이 된다.
**요청 한도(11/18):** 같은 선배에게 열린 대화가 이미 있으면 새 요청을 만들지 않고 그 대화에 붙인다(선배 한 명당 요청 1건). 보낸 사람이 **수락 전(`status: "waiting"`)인 요청을 3건** 가지고 있으면 `{ "ok": false, "reason": "한도", "message": "답을 기다리는 쪽지가 3건이에요. 기다리는 요청을 취소하거나 선배가 답하면 더 보낼 수 있어요." }`. 닮은선배 추천 수를 제한하지 않는 대신 쪽지는 여기서 막는다.
**[11/23 차단]** 차단된 대화(누가 차단했든)에는 양쪽 모두 `{ "ok": false, "reason": "차단", "message": "더 이어 갈 수 없는 대화예요" }`. 한 쌍에 대화는 하나이므로 차단당한 사람이 새 요청을 보내도 같은 응답이다.
**[11/20] 받는 한도:** 받는 선배의 수락 대기 요청이 이미 **5건**이면 `{ "ok": false, "reason": "선배한도", "message": "지금은 이 선배에게 요청이 많아요. 질문함에 남기면 선배 인터뷰 때 함께 물어볼게요." }`. 인기 선배에게 쪽지가 몰리지 않게 하고, 같은 질문은 질문함 → 인터뷰(작업 74) → 해봤노트로 한 번에 답하게 한다. 「당분간 쪽지 쉬기」 스위치는 P1.
막힘 방지(응답 없는 선배 3명에게 갇히지 않게) 두 가지:
- **보낸 사람이 취소(P0)**: `respondRequest(threadId, cancel: true)`로 기다리는 요청을 거둔다 → `status: "cancelled"`, 한도에서 빠진다. 취소한 선배에게는 7일 동안 다시 요청하지 못한다(반복 요청 방지). 선배 화면에서는 그 요청이 조용히 사라진다(알림 없음). 7일 안에 다시 보내면 `{ "ok": false, "reason": "취소", "message": "요청을 취소한 선배에게는 7일 뒤에 다시 보낼 수 있어요.", "retryAt": "2026-11-30T09:00:00+09:00" }`(**[11/24]** `retryAt` = 취소 시각 + 7일, ISO KST).
- **자동 만료(P1)**: 보낸 뒤 **7일** 안에 선배가 수락·거절하지 않으면 서버가 `status: "expired"`로 바꾸고 한도에서 뺀다. 보낸 사람에게 알림 「선배가 아직 못 봤어요. 다른 선배에게 보내 볼까요?」(`alerts.json`). 만료 판정은 `getMessages`·`sendMessage` 호출 때 `requestedAt` 기준으로 한다(별도 스케줄러 없음). 시연에서는 7일이 지나지 않으므로 문구로만 설명한다. **[작업 85]** 서버는 `respondRequest`·`recommendSeniors`를 부를 때도 같은 판정을 먼저 한다(카드의 `requestsFull`·`retryAt`이 만료를 반영하도록).
**[작업 85] 거절된 요청:** 선배가 거절(`declined`)한 대화에 다시 보내면 `{ "ok": false, "reason": "상태", "message": "선배가 이 요청을 받지 않았어요" }`. 만료와 달리 다시 열리지 않는다. 받은 선배가 수락 전(`waiting`)에 답하려 하면 `{ "ok": false, "reason": "상태", "message": "쪽지 요청을 먼저 수락해 주세요" }`.
**[11/23 추천] 추천 제외:** 추천받기를 끈 선배에게 **새 요청·다시 요청**을 보내면 `{ "ok": false, "reason": "추천 제외", "message": "이 선배는 지금 쪽지 요청을 받지 않아요." }`. 이미 수락한 대화는 막지 않는다.
**[11/22 열림] 잠김:** 선배 추천이 잠긴 사람의 **새 요청·다시 요청**은 `{ "ok": false, "reason": "잠김", "message": "경험을 들려주거나 궁금한 것을 정리하면 선배 추천이 열려요", "recommend": {…} }`. 이미 열린 대화에 이어 쓰기와 받은 선배의 답장은 막지 않는다.
대화 상태 `status`: `waiting`(수락 대기) | `accepted` | `declined` | `cancelled` | `expired`. 한도에 세는 것은 `waiting`만이다. 기존 `accepted: true|false`는 `status`로 대신한다.
첫 메시지일 때 서버가 이 대화에서 쓸 보낸 사람 닉네임(`myNickname`, 형용사 + 동물)을 만든다. 화면은 요청 시트를 열 때 `previewNickname(to)`로 같은 값을 미리 받아 「선배에게는 '용감한 수달'로 보여요」를 보여 준다.
```json
{ "ok": true, "threadId": "T-0001", "myNickname": "용감한 수달", "at": "2026-11-20T10:00:00+09:00" }
```

### previewNickname(to)
payload `{to}`. 이 선배에게 보낼 대화의 내 닉네임을 정해 돌려준다(아직 대화가 없으면 새로 만들고, 있으면 그 값). AI 없음, 목록(형용사 × 동물)에서 코드가 고른다. **[11/22 열림]** 대화가 없고 잠겼으면 recommendSeniors와 같은 `locked` 응답.
```json
{ "myNickname": "용감한 수달" }
```

### getMessages(read?)
**[11/23 읽음]** payload `{}` 또는 `{read: threadId}`. 그냥 부르면 목록만 돌려주고 **읽음으로 바꾸지 않는다**(닮은선배 버튼 상태·내 쪽지 목록). 대화창을 열 때 `{read: threadId}`로 부르면 그 대화만 내 쪽 읽음으로 바꾼다. `unread`는 읽음 처리 전, 상대가 보낸 글 중 안 읽은 수. 내가 보내면(`sendMessage`) 그 대화는 읽음.
`role`은 이 대화에서 내 역할: `asker`(쪽지를 보낸 사람) | `senior`(받은 선배). `nickname`은 **상대**의 이름으로, 내가 asker면 `"독일어과 선배 A"`, senior면 `"용감한 수달"`. `askerInfo`는 senior에게만 온다(학과 없음). **[11/22 열림]** `관심`은 보낸 사람의 수요 인터뷰·질문함에서 최근 것부터 최대 2개, 「분야·세부」 형식(국제교류는 「교환학생·독일」, 현장실습은 「현장실습·공공기관」, 비교과는 「비교과·진로·취업 교육과정」). `시기`는 수요 인터뷰에서 고른 것(「아직 몰라요」면 없음). 상황·바라는 것 답변 원문은 선배에게 보내지 않는다.
```json
{ "threads": [
  { "threadId": "T-0001", "role": "asker", "withId": "H0469", "nickname": "독일어과 선배 A", "myNickname": "용감한 수달",
    "status": "accepted", "requestedAt": "2026-11-20T10:00:00+09:00", "unread": 1,
    "messages": [ { "from": "me", "text": "...", "at": "..." }, { "from": "them", "text": "...", "at": "..." } ] },
  { "threadId": "T-0002", "role": "senior", "withId": "H0102", "nickname": "조용한 고래",
    "askerInfo": { "학년": 2, "관심": ["교환학생·독일"], "시기": "다음 학기" },
    "status": "waiting", "requestedAt": "2026-11-21T09:00:00+09:00", "unread": 1,
    "messages": [ { "from": "them", "text": "...", "at": "..." } ] } ],
  "waitingCount": 1, "waitingLimit": 3 }
```
`waitingCount`는 내가 asker로 보낸 `waiting` 요청 수. 화면은 `waitingCount >= waitingLimit`이면 「쪽지 요청」 버튼 대신 안내를 보인다(디자인 규칙 ④·⑤). `cancelled`·`expired` 대화는 asker에게만 보이고(선배 목록에서는 사라짐), 보낸 글은 남는다.
**[11/24 retryAt]** asker의 `cancelled` 대화에 취소 뒤 7일이 지나지 않았으면 `retryAt`(다시 보낼 수 있는 시각, ISO KST, 취소 시각 + 7일)이 붙는다. 7일이 지나면 필드가 없어지고 바로 다시 요청할 수 있다(같은 대화가 `waiting`으로 다시 열림). 닮은선배 카드의 `retryAt`(recommendSeniors)과 같은 값이다.
**[11/23 차단]** `status: "blocked"`인 대화는 양쪽 목록에 남고 `blockedByMe`(내가 차단했는지)가 붙는다. 화면은 입력창 대신 차단한 쪽에 「차단한 대화예요」, 차단당한 쪽에 「더 이어 갈 수 없는 대화예요」를 보인다(누가 차단했는지 상대에게 말하지 않음).

### respondRequest(threadId, accept | cancel)
payload `{threadId, accept: true|false}` 또는 `{threadId, cancel: true}`.
- `accept`: 받은 선배가 수락·거절한다. `waiting`이 아닌 대화에는 `{ "ok": false, "reason": "상태", "status": "<지금 상태>" }`.
- `cancel`: 보낸 사람이 기다리는 요청을 거둔다(`waiting` → `cancelled`). `waiting`이 아니면 `{ "ok": false, "reason": "상태", "status": "<지금 상태>" }`.
- **[작업 85]** 없는 대화, 내 대화가 아닌 것(남의 요청 취소, 보낸 사람이 수락·거절), 선배 쪽에서 사라진 취소·만료 요청을 선배가 부르면 `{ "error": "볼 수 없는 기록이에요" }`(남의 대화 상태를 알려 주지 않는다).
```json
{ "ok": true, "status": "accepted" }
{ "ok": true, "status": "cancelled", "retryAt": "2026-11-30T09:00:00+09:00" }
```
**[11/24]** 취소 응답의 `retryAt`은 그 선배에게 다시 보낼 수 있는 시각(취소 시각 + 7일, ISO KST)이다.
**[작업 85]** 서버는 화면 호환을 위해 옛 필드 `accepted: true|false`도 함께 보낸다(`respondRequest` 수락·거절 응답, `getMessages`의 각 대화 — 거절된 대화에는 `declined: true`도). 새 화면은 `status`만 쓴다. 11/20 이전 기록의 `status: "requested"`는 `waiting`으로 읽는다.

### reportThread(threadId, reason, block) [11/23 차단]
payload `{threadId, reason?, block?}`. 쪽지 대화 ⋮ 메뉴의 신고·차단(디자인 규칙 8절 익명 쪽지 대화). AI 없음.
- `reason`(신고 사유, 최대 100자)이 있으면 `threadReports.json`에 `{threadId, by, role, reason, block, at}`을 남긴다. 대화는 그대로 이어진다.
- `block: true`면 `status: "blocked"`(`blockedBy`·`blockedAt`·`statusBeforeBlock` 저장). 그 두 사람 사이 대화는 양쪽 다 더 못 보낸다(`sendMessage` → `reason: "차단"`). 수락 대기 요청이었으면 보낸 사람 한도에서 빠지고 선배의 요청 알림을 지운다. 상대에게 알리지 않는다. 이미 차단된 대화는 그대로.
- 둘 다 없으면 `{ "error": "신고 사유를 골라 주세요" }`. 그 대화의 asker·senior가 아니면 `{ "error": "볼 수 없는 기록이에요" }`(선배 목록에서 사라진 취소·만료 요청도 선배는 못 부름).
- 차단 풀기는 P1. 신고된 쪽지의 콘솔 표시는 하지 않는다(콘솔 신고 섹션은 해봤노트 문장만, 작업 33).
```json
{ "ok": true, "reported": true, "blocked": true, "status": "blocked" }
```

### getInbox()
```json
{ "myNotes": [ { "id": "M-0001", "program": "마르부르크필립스대학교", "type": "교환", "noteId": "N-marburg",
                 "share": "partial", "filled": 4, "total": 7, "sharedLines": 3, "editedLines": 0, "updatedAt": "..." } ],   // [11/22] 최근에 요약한 것이 위
  "questions": [ { "questionId": "Q-0001", "text": "...", "status": "hold", "askedAt": "..." },
                 { "questionId": "Q-0002", "text": "...", "status": "answered", "noteId": "N-marburg", "answeredAt": "..." } ],
  "scraps": [ { "noteId": "N-marburg", "program": "마르부르크필립스대학교" } ],   // [11/22] scrapNote로 켠 노트, 최근이 위
  "alerts": [ { "text": "내 질문에 선배가 답했어요 · 마르부르크필립스대학교 해봤노트", "questionId": "Q-0002", "noteId": "N-marburg", "at": "..." } ] }
```
**[11/22] 내 경험노트 카드(`myNotes`)**: `id`는 내 경험노트 번호(`M-…`), `noteId`는 공유되는 해봤노트 번호. `share` = `private`(나만 보기) | `partial`(일부 공유 — 화면 「N문장 공유」, N = `sharedLines`) | `shared`(해봤노트 공유됨). **「반영 중」 상태는 없다** — `saveConsent`가 그 자리에서 해봤노트에 반영하므로(11/22 미리 결정), 공유 직후 알림은 「해봤노트에 내 이야기가 반영됐어요」(`noteId` 포함). `filled`/`total` = 노트 틀에서 내 문장이 있는 칸 수 / 전체 칸 수(「노트 틀 4/7」). `sharedLines` = 지금 해봤노트에 보이는 내 문장 수(신고로 숨긴 것 제외).
**[11/23 고치기] `editedLines`** = 선배가 고친 문장 수(내 경험노트 문장 `updateMyNote` + 공개 문장 `saveConsent` `changed`, 줄마다 `edited: true`인 것). `getMyNote`에도 같은 값. **다시 요약하면 고친 문장이 사라진다** — `summarizeInterview`는 같은 프로그램의 내 경험노트와 공개 초안을 새 AI 문장으로 통째로 바꾼다(**[v2]** `append: true`면 지우지 않고 덧붙이므로 이 확인은 `append`가 아닐 때만). 그래서 화면(인터BOO 들려주기)은 「AI 요약」을 누르면 `getInbox().myNotes`에서 같은 `program` 카드를 찾아 `editedLines ≥ 1`이면 확인 바텀시트를 먼저 띄운다: 제목 「다시 요약할까요?」, 본문 「고친 문장 N개가 새 요약으로 바뀌어요. 해봤노트에 이미 공유한 문장은 다시 공유하기 전까지 그대로예요.」, Primary 「새로 요약하기」 / Text 「취소」. 0이거나 카드가 없으면 바로 요약한다.
**[11/19]** 질문 `status`는 `hold`(미답변) | `answered` | `official`. 화면은 `answered`에 「선배가 답했어요」 라벨 + 해봤노트 링크(**[v2]** 「후배 질문」 칸이 없으므로 질문 상세의 「선배의 답」 Q·A가 주 화면, 노트 링크는 보조). (이전 예시의 `waiting`은 쓰지 않는다.) **[v2]** `deleted`는 목록에 나오지 않는다. 카드·상세의 「더 들려주기」(`myNotes` 카드, `../talk/?mode=tell&program=…`)는 비활성 「자소서용 요약 보기」 자리에 둔다. `total`은 「후배 질문」 칸을 뺀 칸 수.

### deleteQuestion(questionId) · updateQuestion(questionId, text) [v2]
내 보관함 질문 상세의 「질문 삭제」·「질문 고치기」. **본인 질문이고 `status: "hold"`일 때만**. `answered`는 `{ "error": "선배가 답한 질문은 지울 수 없어요" }`(deleteQuestion) / `{ "error": "선배가 답한 질문은 고칠 수 없어요" }`(updateQuestion), `official`은 `{ "error": "공식 안내 질문은 지울 수 없어요" }` / `{ "error": "공식 안내 질문은 고칠 수 없어요" }`, 남의 것·없는 것·이미 지운 것은 `{ "error": "볼 수 없는 기록이에요" }`.
- `deleteQuestion`: **소프트 삭제** — `status: "deleted"`, `deletedAt`. 행은 남아 콘솔 통계(PRD 9-3 「학번 제거 후 통계 영구」)에만 쓰이고 `interviewNext`·`getInbox`·askBoo 근거·수요 집계의 「미답변」에서는 뺀다. 선배가 답하는 도중 삭제되면 saveConsent 참고.
- `updateQuestion`: `text` 앞뒤 공백 제거, 빈 문장·**300자** 초과는 `{error}`. 선배 화면에 그대로 나가므로 `check_public_text`(학번·연락처·메일·링크·주소·금지어)를 거쳐 걸리면 `{ "error": "질문에 연락처·메일·링크를 넣을 수 없어요", "reason": "연락처" }`. 통과하면 `질문`을 덧쓰고 `editedAt`, 응답에 고친 질문. 프로그램·칸은 바꾸지 않는다(바꾸려면 삭제 후 다시 묻기). AI 없음.
```json
{ "ok": true, "questionId": "Q-0001", "status": "deleted" }
{ "ok": true, "questionId": "Q-0001", "text": "마르부르크에서 학기 중에 인턴을 같이 할 수 있어요?", "editedAt": "..." }
```
화면(민지): 질문 상세에서만, 하단 Text 「질문 고치기」「질문 삭제」. 삭제는 확인 대화상자(디자인 규칙 5-10), 고치기는 입력창 + Secondary 「저장」 / Text 「취소」(공개 동의 시트 「문장 고치기」와 같은 모양). 목록 카드에는 두지 않는다.

### saveInterviewDraft(program, answers) · getInterviewDraft(program) [v2, P1-여건 79]
들려주기 미완성 초안. 답할 때마다 `saveInterviewDraft(program, answers)`(answers는 interviewNext payload와 같은 모양), 들어올 때 `getInterviewDraft(program)` → `{answers, savedAt}` 또는 `{answers: []}`. 사람·프로그램별 하나, `runtime/interviewDrafts.json`. **7일** 지나면 없는 것으로 보고, `summarizeInterview`가 끝나면 지운다(0장 보관기간). 마스킹 전 원문이므로 본인만(`owner == me`). AI 없음. 빈 `answers`로 저장하면 초안을 지운다(`savedAt: null`). 답은 30개·한 답 1000자까지 남기고, 읽거나 쓸 때 7일 지난 초안을 모두 지운다(스케줄러 없음).
- **1단계(즉시, 서버 없음)**: 화면이 들려주기·물어보기 대화를 `sessionStorage`에 프로그램별로 저장·복원한다(탭마다 따로 — 두 창 시연). 돌아오면 BOO가 「아까 이야기를 이어서 할게요」 + 마지막 질문을 다시 보인다. 물어보기 저장분은 askBoo `history`로도 쓴다.
- **2단계(작업 79)**: 위 두 함수. 다른 기기·다음 날에도 이어 쓴다.
```json
{ "ok": true, "savedAt": "2026-11-23T16:00:00+09:00", "expiresAt": "2026-11-30T16:00:00+09:00" }
{ "answers": [ { "section": "팁", "question": "…", "answer": "…" } ], "savedAt": "..." }
```

### getMyNote(id) [11/22]
내 경험노트 상세(디자인 규칙 8절). **본인 것만**(남의 것·없는 것은 `{"error": "볼 수 없는 기록이에요"}`). AI 없음.
카드 값(`getInbox.myNotes`와 같음)에 더해, 칸은 노트 틀 순서(빈 칸도 `lines: []`), 문장마다 `text`(내 경험노트 1인칭 문장) · `publicText`(해봤노트용 해요체 문장) · `lineId`(공개 동의 시트의 문장 번호) · `shared`(지금 해봤노트에 보이는지 — 「공유됨」 라벨). 「해봤노트에 공유」/「공유 범위 바꾸기」는 `publicDraft`·`draftId`로 공개 동의 시트를 다시 열고 `saveConsent(draftId, edits)`를 그대로 부른다(다시 부르면 이번 범위로 바뀐다).
```json
{ "id": "M-0001", "program": "마르부르크필립스대학교", "type": "교환", "noteId": "N-marburg",
  "share": "partial", "filled": 4, "total": 7, "sharedLines": 3, "updatedAt": "...", "draftId": "D-0001",
  "sections": [ { "name": "지원", "lines": [ { "text": "나는 출국 3학기 전부터 TestDaF를 준비했다.",
                  "publicText": "출국 3학기 전부터 TestDaF를 준비했어요.", "lineId": "L-D1-1", "shared": true } ] },
                { "name": "학점", "lines": [ { "text": "...", "publicText": "...", "lineId": "L-D1-4", "shared": false } ] },
                { "name": "비용", "lines": [] } ],
  "publicDraft": { "sections": [ "...summarizeInterview의 publicDraft 그대로" ] } }
```
**[11/23 고치기]** `updateMyNote`로 고친 문장에는 `edited: true`(화면: 중립 라벨 「내가 고친 문장」). 공개 동의 시트에서 고친 공개 문장은 `publicDraft`의 그 줄에 `edited: true`(saveConsent [11/23 고치기]).

### updateMyNote(id, changed) [11/23 고치기]
내 경험노트 문장 고치기. **본인 것만**(남의 것·없는 것은 `{"error": "볼 수 없는 기록이에요"}`). AI 없음.
payload `{id, changed: [{section, index, text}]}` — `index`는 `getMyNote`의 그 칸 `lines` 순서(0부터).
- `text`는 앞뒤 공백을 지운다. 빈 문장이면 `{"error": "문장을 적어 주세요", section, index}`, **300자**를 넘으면 `{"error": "300자 안으로 적어 주세요", section, index}`. 없는 칸·범위 밖 `index`면 `{"error": "고칠 문장을 찾지 못했어요"}`. **하나라도 틀리면 아무것도 바꾸지 않는다.**
- 내 경험노트는 본인만 보므로 공개 문장 검사(`check_public_text`)는 하지 않는다(성적·실명도 적을 수 있음).
- 고친 줄은 `text` = 고친 문장, `edited: true`, `aiText` = 처음 AI가 만든 문장(처음 고칠 때 한 번만). 같은 문장으로 저장하면 고침으로 보지 않는다. `updatedAt`을 갱신한다.
- **해봤노트 공개 문장(`publicDraft`·`noteLines`)은 바뀌지 않는다.** 이미 공유한 노트면 화면은 저장 뒤 안내 「해봤노트 문장은 그대로예요 · 해봤노트 문장 고치기」(→ 공개 동의 시트 「공유 범위 바꾸기」)를 보여 준다.
- 응답은 `getMyNote`와 같은 모양에 `ok: true`를 더한 것 → 화면은 그대로 다시 그린다.
```json
{ "ok": true, "id": "M-0001", "program": "마르부르크필립스대학교", "share": "partial", "...": "getMyNote와 같음",
  "sections": [ { "name": "생활", "lines": [ { "text": "2~3학년에게 꼭 추천하고 싶다.", "edited": true,
                  "publicText": "2~3학년에게 추천하고 싶어요.", "lineId": "L-D1-2", "shared": true } ] } ] }
```
화면(내 보관함 · 내 경험노트 상세, 민지): 문장마다 Text 버튼 「문장 고치기」 → 입력창(라벨 「내 경험노트 문장」, 안내 「나만 보는 문장이에요. 해봤노트 문장은 바뀌지 않아요.」) + Secondary 「저장」 / Text 「취소」 — 공개 동의 시트의 「문장 고치기」와 같은 모양(`common/consent.js` 참고).

### demandNext(state) [11/22 열림]
「궁금한 것 정리하기」(수요 인터뷰) 다음 단계 하나. **AI 없음** — 칩과 규칙만(`functions/demand.py`). interviewNext처럼 서버는 기억하지 않고, 화면이 응답의 `state`를 들고 다니다 고른 값·쓴 답을 넣어 다시 보낸다.
순서: `field`(국제교류·현장실습·비교과·잘 모르겠어요) → (`explore`: 「잘 모르겠어요」면 고민 칩으로 분야·분류를 정함) → `detail`(국제교류 = 나라, 현장실습 = 기관 유형, 비교과 = 프로그램 분류, `programs.json` `세부`) → `program`(그 분류의 프로그램 + 「아직 정하지 않았어요」) → `section`(노트 틀 칸) → `when`(이번 학기·다음 학기·1년 뒤·아직 몰라요) → **답변 3개** `situation`(지금 내 상황) · `question`(고른 칸에 대해 선배에게 묻고 싶은 것) · `hope`(이 경험이 남겨 줬으면 하는 것) → `more`(더 궁금한 것 최대 2개, `canSkip` — 건너뛰려면 `state.moreDone = true`).
- 칩 단계의 값: `state[step] = 고른 값`. `detail` 칩은 `{value, label}`이고 「아직 정하지 않았어요」는 `value: null`. `explore`는 `state.explore = 고른 label`(state.field는 「잘 모르겠어요」 그대로).
- 답변 단계: `state[step] = 쓴 문장`, `more`는 `state.more = [..., 문장]`. **유효 답변** = 10자 이상, 「몰라요」류·같은 글자 반복 아님, `check_message`(학번·연락처·비방) 통과. 아니면 같은 단계 + `retry`(문구).
- `progress.answered`는 유효 답변 수(칩은 세지 않음), `need`는 3.
- **물어보기에서 이어 하기**: askBoo가 보류(`hold`)한 내 질문으로 시작하면 `state = { fromQuestionId: "Q-0001" }` → 분야·세부·프로그램·칸·질문 문장이 미리 채워져 `when`부터 묻는다(답변 1개가 이미 있음). 남의 질문이면 `{"error": "볼 수 없는 기록이에요"}`.
```json
{ "done": false, "step": "detail", "question": "어느 나라가 궁금해요?",
  "options": [ { "value": "프랑스", "label": "프랑스" }, { "value": "독일", "label": "독일" }, { "value": null, "label": "아직 정하지 않았어요" } ],
  "progress": { "answered": 0, "need": 3 }, "state": { "field": "국제교류" } }
{ "done": false, "step": "situation", "question": "지금 어느 정도 준비됐어요? …", "examples": ["2학년이고 어학 점수를 준비하고 있어요"],
  "retry": "조금만 더 자세히 적어 주세요(10자 이상).", "progress": { "answered": 0, "need": 3 }, "state": { … } }
{ "done": true, "progress": { "answered": 3, "need": 3 }, "state": { … },
  "summary": { "interest": "교환학생·독일", "program": "마르부르크필립스대학교", "section": "학점", "when": "다음 학기",
               "situation": "2학년이고 독일어 B1, 어학 점수를 준비하고 있어요", "questions": ["학점 인정은 전공 몇 학점까지 되나요?"],
               "hope": "외국어로 일상을 꾸려 본 자신감을 얻고 싶어요" } }
```
화면은 `done`이면 「내가 궁금한 것」 카드(summary)와 동의 문구 「이 질문을 선배와 담당 부서에 전해도 될까요?」를 보여 주고 `saveDemand`를 부른다.

### saveDemand(state) [11/22 열림]
payload `{state, consent: true}`. 서버가 같은 규칙으로 다시 검사한다. 끝나지 않았으면 `{ "ok": false, "message": "아직 정리가 끝나지 않았어요", "next": {demandNext 응답} }`.
저장: 질문 문장(가장 궁금한 것 + 더 궁금한 것)을 **질문함에 `hold`로**(`프로그램명`·`칸`·`시기`·`수요: true`) — 다음 그 프로그램 선배의 들려주기가 후배 질문으로 먼저 묻고(작업 74, **[v2]** `junior: true`), 콘솔 수요 현황에도 합산된다. `fromQuestionId`로 시작했으면 그 질문 행에 맥락만 붙인다(질문함이 늘지 않음). 상황·바라는 것은 `runtime/demands.json`에만 둔다(선배에게 보내지 않음, 부서 집계는 P1).
```json
{ "ok": true, "demandId": "R-0001", "questionIds": ["Q-0003"],
  "recommend": { "ready": true, "by": "ask", "need": 3, "talk": { "answered": 0, "shared": 0 }, "ask": true }, "unlocked": true }
```
`unlocked: true`면 이번에 처음 열린 것 → 토스트 「선배 추천이 열렸어요」 + 「닮은선배 보기」.

### reportStatement(lineId, reason)
payload `{lineId, reason?}`. 신고된 문장은 즉시 숨김, 부서 리포트에 집계.
```json
{ "ok": true, "hidden": true }
```

### getDeptReport(dept)
**[작업 66] 관리자 함수는 PRD 7장이 원본이고 `functions/admin.py`에 있다.** `getDeptReport`는 옛 이름으로 남겨 `getAdminOverview`와 같은 응답을 준다(아래 옛 예시는 쓰지 않음). 7장 8개에 더해 `getIssuedReport(reportId)` → `{reportId, issuedAt, summary, html}`(발행 이력 「열기」, 화면은 iframe srcdoc sandbox로만 표시)를 둔다. 제안 id는 `S-` + 프로그램·칸 해시 6자리라 기간이 바뀌어도 상태가 이어진다. **[작업 67]** 제안 문장은 `data/suggestions.json`(묶음 id → `유형`·`제목`·`제안`, `functions/suggest.py`로 사전 생성, 사후 검증 통과분만)에서 읽고, 빈 칸은 코드 유형·템플릿 제목으로 채운다. 묶음 규칙이나 `usage-log.json`이 바뀌면 `python functions/suggest.py --retry`로 다시 만든다. `issueReport`의 `summary`는 AI 한 단락(입력에 없는 숫자·고유명사·URL·HTML이 있으면 템플릿)이고 응답에 `summarySource: "ai"|"template"`가 붙는다. 그래서 `issueReport`는 AI 호출 한도(AI_ROUTES)에 든다.

직원 전용. AI는 `summary` 한 단락만.
```json
{ "dept": "국제교류팀", "period": "2026-11",
  "programs": [ { "program": "마르부르크필립스대학교", "questions": 12, "unanswered": 3, "reports": 1 } ],
  "unansweredQuestions": [ { "text": "...", "count": 4 } ],
  "reportedStatements": 1,
  "summary": "..." }
```

## 5. data.js에 둘 export (시그니처)

```js
login(id, pw) · getMe() · askBoo(question, history = []) · setRecommendable(on)   // setRecommendable [11/23 추천] · history [v2]
interviewNext(program, answers) · summarizeInterview(program, transcript, append = false) · saveConsent(draftId, edits)   // append [v2]
deleteQuestion(questionId) · updateQuestion(questionId, text) · saveInterviewDraft(program, answers) · getInterviewDraft(program)   // [v2] 질문 삭제·고치기 · 미완성 초안(P1-여건 79)
listNotes(filter) · getNote(id) · scrapNote(noteId, scrap = true) · saveQuestion(noteId, section) · reportStatement(lineId, reason)   // scrapNote·saveQuestion [11/22]
recommendSeniors(noteId, more) · checkMessage(text) · previewNickname(to) · sendMessage(to, text) · getMessages(read?) · respondRequest(threadId, accept) · cancelRequest(threadId) · reportThread(threadId, reason, block = false)   // cancelRequest = respondRequest {threadId, cancel: true} (작업 85) · reportThread [11/23 차단] · getMessages(threadId) = 그 대화만 읽음 [11/23 읽음]
getInbox() · getMyNote(id) · updateMyNote(id, changed) · getDeptReport(dept)   // getMyNote [11/22] · updateMyNote [11/23 고치기]
demandNext(state = {}) · saveDemand(state)   // [11/22 열림] 궁금한 것 정리하기 → 선배 추천 열림. 열림 상태는 getMe().recommend
getDepartments() · getAdminOverview(dept, period) · getAdminSuggestions(dept, period) · setSuggestionStatus(id, status)
getReportSettings(dept) · saveReportSettings(dept, settings) · issueReport(dept, period) · listIssuedReports(dept) · getIssuedReport(reportId)   // 작업 66, PRD 7장
currentUser() · logout()   // sessionStorage "me" 읽기·지우기 (login()이 성공 시 저장)
```

## 6. mock-data.json 작성 지시

- 최상위 키는 함수 이름. 3장 pickMock 규칙에 나오는 하위 키(`login.student/staff/staffDept/fail`, `askBoo.exchange/hold/official`, `interviewNext.byProgram[프로그램명].steps/done`·`interviewNext.questions`, `getNote["N-marburg"]`, `checkMessage.ok/blocked`)를 만든다.
- 내용은 1장 시연 인물 기준. askBoo.exchange 문장 3개, getNote["N-marburg"]는 교환 6칸(지원·학점·비용·생활·팁·배운점) 중 4칸 채우고 비용은 빈 칸, 배운점은 `interviewOnly: true`로 선배 인용 1개(`docType: "인터뷰"`).
- `getNote["N-kotra"]`도 하나: 현장실습 노트(`KOTRA 해외무역관(유럽 권역)`, 데이터에서 후기가 가장 많은 기관), 칸은 5개 [`지원동기`, `업무내용`, `배운점`, `지원·선발`, `근무조건`]. 마지막 두 칸은 `interviewOnly: true`이고 비어 있음. (`지원·선발`은 한 칸의 이름이다)
- 출처 학기는 선배1(H0469)의 보고서 `2025-1`, H0745의 보고서 `2025-2`. 노트의 `lastSemester`는 마르부르크 보고서 중 최근인 `2026-1`.
- recommendSeniors는 선배1(H0469, 14점: 학과 5+이중전공 4+단과대 3+공통 비교과 `한국외국어대학교 직무탐색 집중교육` 2), 선배2(H0241, 12점: 학과·이중전공·단과대, 공통 비교과 없음) 두 명(11/20 가중치 기준. 실제 데이터의 3~5위 H0751·H0995·H0745는 8점), reasons 맨 앞은 「희망 프로그램을 경험했어요」. 가상 문장만 쓰고 실제 후기 원문을 옮기지 않는다.
- ~~**[11/19]** `getNote["N-marburg"]`에 7번째 칸 `후배 질문`~~ → **[v2]** 「후배 질문」 칸을 뺀다. `getNote["N-marburg"]`는 6칸이고 생활 칸에 `answersQuestionId: "Q-0001"`·`asked`가 붙은 인터뷰 문장 1개. `interviewNext.byProgram["마르부르크필립스대학교"].steps[0]`은 `junior: true`·`section: "생활"`(questionId·asked·pendingQuestions 1), `steps[1..]`은 기존 칸, `total` 6, 모든 step에 `covered`. `summarizeInterview.publicDraft` 생활 칸에 `answersQuestionId` 문장 1개. `saveConsent`에 `answered: ["Q-0001"]`. `getInbox.questions[1]`은 `answered`, `alerts[0]`은 「내 질문에 선배가 답했어요」. `getNote["N-kotra"]`는 칸 5개(…`근무조건`)이고 자동 분류 문장에 `autoClassified: true`. **[v2]** `askBoo.chat` 하나(「아까는 KOTRA 해외무역관 이야기였어요…」 + 칩 2개), `askBoo.exchange` 문장마다 `cites`. **[11/23 작업 78]** `getNote["N-marburg"]` 비용 칸에 `summary` 2문장·`newLines: 0`, 생활 칸에 `summary` 1문장·`newLines: 2`(끝 두 문장이 인터뷰). 나머지 칸은 `summary` 없음(원문 목록), 배운점은 늘 없음.

## 7. data/frames.json (이번에 함께 생성)

```json
{
  "교환": { "칸": ["지원", "학점", "비용", "생활", "팁", "배운점"], "인터뷰로만": ["배운점"] },
  "파견": { "칸": ["지원", "학점", "비용", "생활", "팁", "배운점"], "인터뷰로만": ["배운점"] },
  "인턴": { "칸": ["지원동기", "업무내용", "배운점", "지원·선발", "근무조건"], "인터뷰로만": ["지원·선발", "근무조건"] },
  "비교과": { "칸": ["활동내용", "배운점"], "인터뷰로만": [] }
}
```
- 11/16: 교환·파견에 `배운점` 추가(PRD 4-1). 실제 `data/frames.json` 반영은 작업 70. `배운점` 칸은 해봤노트에서 선배별 원문 인용으로 렌더한다(합쳐 요약하지 않음).
- ~~11/19: 네 틀 모두에 `후배 질문` 추가~~ → **[v2] 11/23: 「후배 질문」 칸을 뺀다**(팀 합의, 검토안 3-5). 후배 질문은 질문함에 쌓였다가 다음 선배에게 나가면 되고, 답은 질문이 속한 칸에 들어간다. `data/frames.json` 반영은 원우(작업 89), 서버·화면의 `QUESTION_SECTION` 분기 제거는 미리·민지. `인터뷰로만`은 그대로(비교과는 빈 목록). 보고서 문항 매핑(9장)은 바뀌지 않는다. (P1-여건, 작업 84) 칸별 `"예시"`: `{"지원": ["출국 3학기 전", "1년 전", "합격 후"], …}` 모양으로 원우가 추가하면 `interviewNext.examples`로 나간다.

## 8. 완료 확인

- `screens/talk/index.html`에 askBoo를 부르는 임시 화면(입력창+버튼+결과)을 두고, "마르부르크 파견 준비 언제부터?"는 출처 달린 문장 3개, "HUFS특강 어때요?"는 보류 안내, "교환학생 지원하려면 평점 몇 점 이상이어야 해요?"는 공식 안내 링크가 나온다.
- data/README.md에는 이 문서 4장의 응답 모양을 표로 옮기고 "원본: docs/spec-v1.md"라고 적는다.

## 9. 데이터 파일 (원우: 시트 → data/)

**원본: `@VCC/가상데이터/가상데이터_1000명.xlsx`** (가상학생 1,000 + 직원 2 · 가상비교과 2,249 · 가상비교과만족도 130 · 가상귀국보고서 280 · 가상현장실습후기 277 · 가상질문 개발 70, 봉인 30은 시트 밖). 시트 하나가 파일 하나. 각 행은 객체 하나이고, 키는 시트 헤더를 글자 그대로 쓴다(띄어쓰기·괄호·마침표 포함). `분포요약`·`생성기준` 시트는 변환하지 않는다.

| 시트 | 파일 | 키(헤더 그대로) |
|---|---|---|
| 가상학생 | `students.json` | `번호` `colreg_no` `univ_nm` `crs_nm` `dbl_mjr_nm` `regst_grad` `입학년도` `해외경험` `해외경험 유형` `파견국가` `파견대학` `파견시기` `현장실습·인턴십` `인턴 유형` `기관 유형(가상)` `기관명(가상)` `인턴 시기` `비교과 이수 건수` `비교과 유형` `이수 비교과 프로그램` `경험 조합` |
| 가상비교과 | `extracurricular.json` | `번호` `가상학번` `학과(전공)` `현재 학년` `이수학년도` `이수학기(1~4)` `학기구분` `프로그램명` `비교과 유형` `이수 당시 학년` |
| 가상비교과만족도 | `extracurricular-satisfaction.json` | `번호` `프로그램명` `비교과 유형` `이수 인원(가상)` `만족도(5점)` |
| 가상귀국보고서 | `reports.json` | `학번` `학년도` `학기` `국가` `대학명` + 문항 헤더 14개(`1. 출국 전 준비사항` … `4. 후배들에게 남기고픈 한마디`) |
| 가상현장실습후기 | `internships.json` | `학번` `학년도` `학기` `업체명` `직군` `후기` |
| 가상질문 | `eval-questions.csv` | `번호` `질문` `정답` `기대결과` `관련 프로그램` `관련 칸` `기대 근거ID` `유형` `봉인` `질문자 학번` `비고` |
| 부서리스트 | `departments.json` | `부서코드` `부서명` `담당분야` `비교과 배정 키워드` `대표메일(가상)` `공식안내URL` `배정 범위(설명)` |
| 비교과_부서배정(확인용) | (변환하지 않음) | `수동 지정 부서코드` 열만 programs.json 만들 때 읽는다 |

- **학생 열쇠**: `가상학생.colreg_no` = `가상비교과.가상학번` = `가상귀국보고서.학번` = `가상현장실습후기.학번` (값 형식 `H0001`~`H1000`). 가상학생 맨 위 두 행은 직원(`staff01` 총괄, `staff02` 혁신지원팀 담당자).
- **부서 배정(programs.json의 `운영부서코드`)**: 국제교류 프로그램은 `담당분야`에 국제교류가 있는 부서(D01), 현장실습 프로그램은 현장실습이 있는 부서(D02). 비교과는 ① `비교과_부서배정(확인용)` 시트의 `수동 지정 부서코드`가 있으면 그것, ② 없으면 부서리스트를 **위에서부터** 보며 `비교과 배정 키워드`(`;`로 구분) 중 하나가 프로그램명에 들어 있는 첫 부서. 130개 모두 배정되어야 한다(미배정은 오류 목록 출력).
- **가상질문 열**: `기대결과` = `답변`·`보류`·`공식안내`, `유형` = `동의어`·`범위밖`·`함정`·`규정오해`, `봉인` = `Y`/빈칸. 봉인 30개는 공유 시트가 아니라 원우 PC에만 두고, 시트에는 개발용만 둔다.
- **학기 코드**(세 시트 공통): `1`=1학기, `2`=여름방학, `3`=2학기, `4`=겨울방학. 화면·응답의 `semester`는 `"2024-1"`, `"2025-여름"`, `"2024-2"`, `"2025-겨울"`로 바꿔 쓴다. 가상비교과는 `이수학기(1~4)` 숫자와 `학기구분` 글자가 같이 있다.
- **dbl_mjr_nm**: 1학년은 빈칸(이중전공 미선택). 2~4학년은 모집단 분석 비율로 배정(생성기준 시트).
- **programs.json은 시트가 아니라 변환 스크립트가 만든다**: 국제교류 = `가상학생`의 (`파견국가`, `파견대학`) 고유값, 프로그램명은 `파견대학` 글자 그대로(예: `마르부르크필립스대학교`) · 현장실습 = `가상현장실습후기.업체명` 고유값 · 비교과 = `가상비교과만족도.프로그램명`. 키: `프로그램명` `분야`(국제교류/현장실습/비교과) `세부`(국가 / 기관 유형 / 비교과 유형) `만족도(5점)`(비교과만) `운영부서코드`(아래 부서 배정 규칙). 모든 시트의 프로그램명은 이 목록과 글자 그대로 같아야 한다(askBoo 1단계 대조 기준).
- **노트 틀**: 국제교류 노트는 `frames.json`의 `교환` 틀(파견과 같음), 현장실습 노트는 `인턴` 틀, 비교과는 `비교과` 틀.
- `evidence.json`은 시트가 아니라 `reports.json`·`internships.json`에서 만드는 근거 문단 목록이다. 문단 하나가 `{ "id", "docType", "학번", "학년도", "학기", "프로그램명", "문항", "칸", "text" }`. `문항`은 원래 시트 헤더 글자 그대로(예: `"2-4. 기숙사 정보"`, `"후기"`), `칸`은 `frames.json`의 칸 이름.
- 귀국보고서 문항 → 칸: 지원(1-1, 1-2, 1-3) · 학점(2-2, 2-3, 3) · 비용(2-6) · 생활(2-1, 2-4, 2-5, 2-7) · 팁(4). `1.`·`2.` 제목 칸은 비어 있어 건너뛴다.
- 현장실습후기는 `후기` 한 칸 자유 서술이다. **[11/19] 문장 단위**로 쪼개 한 문장이 한 건이 되고(`id`는 `I001-1`, `I001-2`…) `칸`은 비워 둔다 → 작업 50(문장 자동 분류)이 `지원동기`·`업무내용`·`배운점` 중 하나를 채우고 `autoClassified: true`를 붙인다. 문단 단위로 두면 한 문단에 업무·배운점이 섞여 칸 하나로 뭉개진다(11/19 샘플 확인). 분류 정확도는 원우의 정답 칸으로 측정(작업 50).
- **[11/19]** `intern-keywords.json`(원우, 작업 81): `{ "직군": {"전시·행사 지원": ["KOTRA 해외무역관(유럽 권역)", …]}, "기관유형": {...}, "약칭": {"코트라": "KOTRA 해외무역관(유럽 권역)"} }`. 값은 모두 `programs.json`의 프로그램명과 글자 그대로 같아야 한다.
- **[11/19]** `notes.json`(원우, 작업 26 `tools/build_notes.py`): getNote 응답 모양(4장) 그대로, 프로그램별 1건. `runtime/noteLines.json`과 합치는 것은 서버.
- 함수 응답(4장)의 `studentId`, `withId`, `to`는 `colreg_no` 값을 가리킨다.

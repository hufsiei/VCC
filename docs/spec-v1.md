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
> **11/23 개정(작업 28, 민지 요청)**: 쪽지 대화 ⋮ 메뉴용 새 함수 **`reportThread(threadId, reason, block)`** — 신고(`threadReports.json`)·차단(`status: "blocked"`, 양쪽 다 더 못 보냄). `sendMessage`에 `reason: "차단"`, `getMessages`에 `blockedByMe`. 바뀐 곳은 **[11/23 차단]** 표시.
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
- **[11/19] 보관기간(운영 규칙, PRD 9-3).** 쪽지 원문 90일, 인터뷰 답변 원문은 요약·동의 처리 뒤 30일, 질문 로그는 학번 제거 후 통계만, 대회 종료(12/9) 후 runtime 전체 삭제(`reset_runtime.py`). 시연 기간에는 삭제 스케줄러를 만들지 않고 규칙만 문서화한다.
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
- **파일(기록 종류마다 하나):** `messages.json`(쪽지 대화) · `nicknames.json`(보는 사람별 선배 글자 A·B·C) · `questions.json`(질문함, 사용 로그와 같은 모양) · `demands.json`(**[11/22 열림]** 궁금한 것 정리하기 — 분야·세부·프로그램·칸·시기·상황·바라는 것, 선배 추천 열림 근거) · `consents.json`(공개 동의) · `myNotes.json`(내 경험노트) · `reported.json`(신고 문장) · **[11/23 차단]** `threadReports.json`(쪽지 대화 신고) · `alerts.json`(알림) · `pendingNicknames.json`(요청 시트에서 미리 정한 동물 닉네임) · `shownSeniors.json`(보는 사람·노트별 지금 추천 목록 최대 9명과 노트 버전) · `counters.json`(번호 매기기) · **[작업 85]** `noteVersions.json`(노트별 버전 — saveConsent가 +1, recommendSeniors가 비교) · **[11/19]** `noteLines.json`(공개 동의를 통과한 인터뷰 문장, 노트별 — 사전 생성 `data/notes.json`과 합쳐 노트가 된다) · `aiUsage.json`(사용자별 AI 호출 수) · (P1-여건) `sessions.json`(로그인 토큰, 작업 73) · `interviewDrafts.json`(인터뷰 중간 저장, 작업 79). 코드: `functions/store.py`(저장) · `functions/runtime_fns.py`(쓰기 함수 10개: checkMessage·previewNickname·sendMessage·getMessages·respondRequest·reportThread·recommendSeniors·saveConsent·reportStatement·getInbox, 그리고 askBoo·summarizeInterview·recommendSeniors가 쓸 도우미 `add_question`·`save_my_note`·`senior_label`). **[작업 66]** 관리자 콘솔용 `reportSettings.json`(부서코드별 발행 설정) · `issuedReports.json`(발행 이력) · `reportHtml.json`(리포트 id → HTML, PRD 6-4의 `reports/{id}.html` 대신 한 파일) · `suggestionStatus.json`(제안 id → 상태). 코드: `functions/admin.py`.
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
| askBoo | 4장의 규정 질문 표현이 있으면 `askBoo.official`, 아니면 질문에 `교환\|파견\|독일\|마르부르크`가 있으면 `askBoo.exchange`, 그 외 `askBoo.hold` |
| interviewNext | **[11/20]** `program`이 `interviewNext.byProgram`에 있으면(마르부르크 시연 대본) `answers.length`번째 `steps`, 다 쓰면 `done`(steps[0]은 「후배 질문」). 그 밖의 프로그램은 서버(`interview.py`)처럼 `data/programs.json`의 `분야` → `data/frames.json` 노트 틀을 고르고, 아직 답하지 않은 칸을 틀 순서대로(「배운점」은 마지막) `interviewNext.questions[칸]` 문장으로 묻는다(`{p}` = 별칭 첫째 또는 프로그램명). 꼬리 질문·후배 질문은 없다(`pendingQuestions: 0`) |
| getNote | `getNote[id]`가 있으면 그것, 없으면 `getNote["N-marburg"]` |
| getMyNote [11/22] | `getMyNote` 하나(M-0001, 일부 공유 예시). 받은 `id`를 그대로 넣어 돌려준다 |
| 선배 추천 열림 [11/22 열림] | mock 기본은 **열림**. 주소에 `?locked=1`이면 잠김: `getMe.recommend.ready: false`, `recommendSeniors`·`previewNickname` → `locked`, `sendMessage` → `reason: "잠김"`. mock `saveDemand`·`saveConsent`를 부르면 그 탭은 열린다(sessionStorage `mockUnlocked`) |
| demandNext·saveDemand [11/22 열림] | `data.js`의 `mockDemand`가 서버(`demand.py`)와 같은 순서로 `programs.json`·`frames.json`에서 칩을 만든다. `fromQuestionId`는 마르부르크·생활 보류 질문으로 채운다 |
| summarizeInterview [11/22 열림] | `summarizeInterview` + transcript로 센 `answered`, `need: 3` |
| checkMessage | 숫자가 8자리 이상 연속(전화·학번)이면 `checkMessage.blocked`, 그 외 `checkMessage.ok` |
| 나머지 | `m[name]` 그대로 |

## 4. 함수 15개

### login(id, pw)
payload `{id, pw}`
`status`는 시트 열이 아니라 서버가 정한다: `colreg_no`가 `staff`로 시작하면 `"직원"`, 그 외는 `"학생"`. 직원은 그 행의 `crs_nm`을 `부서명`으로 주고, `권한`을 정한다: `crs_nm`이 `"전체"`면 `"총괄"`(전 부서 조회, 리포트 설정·발행), 부서명이면 `"부서"`(자기 부서만 조회, 받은 리포트 확인 — 관리자 콘솔 함수는 `dept`를 무시하고 이 부서로 고정). 직원 행은 학생 집계·닮은 선배 후보·사용 로그 생성에서 뺀다.
```json
{ "ok": true, "user": { "colreg_no": "H0143", "status": "학생" } }
{ "ok": true, "user": { "colreg_no": "staff01", "status": "직원", "부서명": "전체", "권한": "총괄" } }
{ "ok": true, "user": { "colreg_no": "staff02", "status": "직원", "부서명": "혁신지원팀", "부서코드": "D04", "권한": "부서" } }
{ "ok": false, "reason": "아이디 또는 비밀번호가 맞지 않아요." }
```

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
`by` = `"talk"`(경험 나눔으로 열림) | `"ask"`(수요 제공으로 열림) | `null`. `talk`는 내 경험노트 중 가장 많이 한 것(유효 답변 수·지금 공유된 문장 수).

귀국보고서 항목 예: `{ "학년도": 2024, "학기": 1, "국가": "독일", "대학명": "마르부르크필립스대학교" }` · 현장실습후기 항목 예: `{ "학년도": 2025, "학기": 2, "업체명": "KOTRA 해외무역관(유럽 권역)", "직군": "전시·행사 지원" }`(학기 2 = 여름방학). 학기 숫자를 화면에 낼 때는 9장의 학기 코드표로 바꾼다.

### askBoo(question)
payload `{question}`. 규정 질문이면 `official`, 근거가 있으면 `ok`, 없으면 `hold`(`hold`·`official` 질문은 자동으로 질문함에 저장되고 `questionId`가 옴).
**[11/19] 규정 질문 판별(작업 18)**: 1단계보다 먼저 코드로 판별한다(AI 없음). 학교가 정하는 기준·금액·기한을 묻는 질문은 선배 경험으로 답하지 않고 공식 안내로 보낸다.
- 판별 표현: `평점|장학금|몇\s*학점|선발\s*(인원|기준)|휴학|등록금|초과학기|인정\s*신청|인정받을 수` (`가상질문` 36~45번이 `official`).
- 경험을 묻는 질문은 `official`이 아니다. "학점 인정 받을 때 주의할 점 있어요?"(5번)·"챙길 서류 있어요?"(15번)는 근거로 답한다. 그래서 "학점 인정"이라는 말만으로 판별하지 않는다.
- `officialUrl`: 질문에서 프로그램을 찾으면 `운영부서코드` → `departments.json`의 `공식안내URL`(getNote와 같은 순서). 프로그램을 못 찾으면 `현장실습|인턴` → D02, `특교원|탄뎀` → D03, 그 외 D01.
- 질문은 `questions.json`에 `status: "official"`로 저장한다. 내 보관함에는 「공식 안내」로 보이고, 콘솔 집계에 들어가며, `interviewNext`의 후배 질문으로는 쓰지 않는다.
**[11/19] 1단계 보강(작업 81)**: 프로그램명 글자 대조가 실패하면 `data/intern-keywords.json`(직군·기관 유형·업체 약칭 → 업체명, 원우)으로 후보 업체를 1~3개 고른다("무역 쪽 인턴" → KOTRA 해외무역관…). 후보가 여럿이면 각 업체의 근거를 합쳐 2~5단계로 넘기고 `sources`의 `program`으로 구분한다. 사전으로도 못 잡으면 `hold`. (P1-여건, 58③) 경량 임베딩: 사전 계산한 후기 문장 임베딩과 질문 임베딩의 코사인 상위 10문장을 후보 근거로 — 벡터 DB 없이 함수 안에서.
**[11/19] 근거 풀** = `data/notes.json`의 문장 + `runtime/noteLines.json`의 동의 통과 문장(「후배 질문」 칸의 A 문장 포함). 그래서 선배가 답한 후배 질문은 다음 후배의 근거가 된다.
```json
{ "status": "ok",
  "lines": [ { "text": "...", "sourceId": "R03-1-1", "lineId": "L-R03-1-1" },
             { "text": "...", "sourceId": "R03-2-4", "lineId": "L-R03-2-4", "fallback": true } ],
  "sources": { "R03-1-1": { "docType": "귀국보고서", "program": "마르부르크필립스대학교", "semester": "2025-1" } },
  "noteId": "N-marburg", "suggestSenior": false }
{ "status": "hold", "lines": [], "sources": {}, "questionId": "Q-0001", "suggestSenior": true,
  "message": "이 부분은 아직 들은 선배가 없어요. 질문함에 담아 두었어요. 닮은 선배에게 물어볼까요?" }
{ "status": "official", "lines": [], "sources": {}, "questionId": "Q-0002", "suggestSenior": false,
  "officialUrl": "https://oia.hufs.ac.kr",
  "message": "학교 규정에 관한 질문이라 국제교류팀 공식 안내에서 정확한 내용을 확인해 주세요." }
```
docType: `귀국보고서` | `현장실습후기` | `인터뷰`
**[11/19] `lines[].fallback`(작업 18)**: AI가 바꾼 문장이 사후 검증(HCX 원칙 v2 3절 5단계: 원문에 없는 숫자·영문·고유명사·새 낱말, JSON 형식 오류, 반말)에 걸려 **근거 원문을 그대로 보여 준 줄**이면 `true`. 원문에서 앞머리 군말(「참고로」 등)과 「ㅎㅎ」·「!!」만 지우고 낱말은 바꾸지 않는다. AI 문장이면 이 필드를 넣지 않는다(없으면 거짓). 화면은 이 줄에 「근거 원문 보기」 표시를 붙일 수 있고, 무시해도 문장은 정상으로 보인다.

### interviewNext(program, answers)
선배 인터뷰에서 다음 질문 하나. payload `{program, answers:[{section, question, answer, questionId?, skipped?}]}`
```json
{ "done": false, "section": "후배 질문", "questionId": "Q-0001", "asked": "마르부르크에서 학기 중 현지 인턴 병행할 수 있어요?",
  "question": "후배가 이렇게 물었어요 — \"마르부르크에서 학기 중 현지 인턴 병행할 수 있어요?\" 경험이 있으면 들려주세요.",
  "progress": { "filled": 0, "total": 7 }, "pendingQuestions": 1 }
{ "done": false, "section": "팁", "question": "후배들이 마르부르크에 대해 잘 모르고 있는 것, 또는 잘못 알고 있는 게 있다면요?", "depth": true,
  "covered": ["지원", "학점", "비용", "생활", "팁"], "progress": { "filled": 1, "total": 7 }, "pendingQuestions": 0 }
{ "done": false, "section": "학점", "question": "학점 칸은 최근 경험이 없어요. 마르부르크에서 들은 수업과 학점 인정은 어땠어요?", "covered": ["지원", "비용", "생활", "팁"], "progress": { "filled": 1, "total": 7 } }
{ "done": true, "progress": { "filled": 4, "total": 7 }, "covered": ["지원", "학점", "비용", "생활", "팁"] }
```
`total`은 그 프로그램 종류의 `frames.json` 칸 수(**[11/19] 교환·파견 7**, 인턴 6, 비교과 3). `배운점`은 다른 칸을 묻고 난 뒤 마지막에 묻는다.
**[11/19] 질문 순서(작업 74)**: ① 서버가 `questions.json`에서 **같은 프로그램**의 `status: "hold"` 질문을 최근순으로 최대 3개 꺼내 먼저 묻는다(`section: "후배 질문"`, `questionId`, `asked` = 후배 질문 원문. 본인이 한 질문·이미 `answered`인 것은 뺀다). 화면은 「경험이 없어요」 버튼을 두고, 누르면 `answers`에 `{questionId, skipped: true}`로 보내 건너뛴다(질문은 `hold` 유지, 다른 선배에게 다시 나온다). ② **[11/22] 보고서가 이미 답한 칸은 다시 묻지 않는다**: 그 뒤 근거(보고서 + 동의 통과 인터뷰 문장)가 **0건이거나 모두 2년 넘은 칸만** 기본 질문(근거 적은 칸 순, 오래된 칸은 「○○ 칸은 최근 경험이 없어요.」 머리말 — 디자인 규칙 6-2와 같은 기준). ③ **깊이 질문**(`depth: true`, 교환·파견 3개·인턴·비교과 2개): 보고서에 잘 안 쓰는 판단·비교·후회·오해를 묻는 고정 문장(`interview.py` `DEPTH_QUESTIONS`, 종류별 2~3개 중 근거 적은 칸에 담기는 것부터 — AI가 만들지 않음). 답은 그 칸에 담긴다. ④ `배운점` 마지막. 근거가 충분해 묻지 않은 칸은 **`covered`**(칸 이름 목록)로 매 응답에 알린다 — 화면은 진행 칩에서 비어 있지 않게(예: 「보고서로 채워짐」) 보여 주고, `done`이면 「노트 틀을 모두 채웠어요」 대신 답한 칸 기준 문구를 쓴다(민지). 마르부르크(지원15·학점15·비용5·생활20·팁5)는 후배 질문 → 팁(깊이) → 지원(깊이) → 생활(깊이) → 배운점. 꼬리 질문은 각 칸의 첫 답에 그대로 붙는다. 질문함 질문은 `progress.filled`에 세지 않고 `pendingQuestions`로 따로 알린다.
**[11/19] `examples`(P1-여건, 작업 84)**: `frames.json`의 칸별 `예시`가 있으면 2~3개를 함께 보낸다. 화면은 칩으로 보여 주고 탭하면 입력창에 채운다. 없으면 생략.

### summarizeInterview(program, transcript)
payload `{program, transcript:[{section, question, answer}]}`. 두 장을 돌려준다: 내 경험 노트(1인칭, 나만 봄)와 공개용 초안(선배가 고치고 동의해야 공개).
**서버는 응답과 함께 myNote를 내 경험노트로 저장한다**(`saved: true`, `myNoteId`). 화면은 "내 경험노트에 저장됨"을 표시하고, 공유는 이후 `saveConsent`로만 한다. 같은 프로그램으로 다시 요약하면 같은 `myNoteId`를 갱신한다.
`match`는 AI 원문 일치 검사 결과. `false`면 화면이 "원문과 다를 수 있어요" 표시.
`identifying`은 코드(정규식·사전)가 찾은 본인 식별 문장(성적 숫자·수상·실명·특정 인물). `true`면 동의 시트에서 기본 꺼짐 + 주의 라벨.
**[11/22 열림]** 응답에 `answered`(이번 transcript의 유효 답변 수 — 서로 다른 질문, 10자 이상, 「몰라요」류·건너뛰기 제외)와 `need`(3)를 더한다. 서버는 내 경험노트에 큰 값을 남긴다. 화면은 `answered < need`면 공유 시트에 「세 가지 이상 이야기하면 선배 추천이 열려요」를 안내한다(요약·공유 자체는 막지 않음).
**[11/19]** 후배 질문에 답한 문장은 `section: "후배 질문"`에 들어가고 `answersQuestionId`·`asked`(질문 원문)를 유지한다. myNote·publicDraft 모두 같다. 요약 전에 transcript는 0장 마스킹을 거친다.
```json
{ "draftId": "D-0001", "program": "마르부르크필립스대학교", "saved": true, "myNoteId": "M-0001",
  "myNote": { "sections": [ { "name": "지원", "lines": [ { "text": "나는 출국 3학기 전부터 TestDaF를 준비했다." } ] },
                           { "name": "배운점", "lines": [ { "text": "낯선 행정 절차를 혼자 끝까지 처리하는 법을 배웠다." } ] } ] },
  "publicDraft": { "sections": [ { "name": "지원", "lines": [ { "lineId": "L-D1-1", "text": "출국 3학기 전부터 TestDaF를 준비했어요.", "match": true, "identifying": false } ] },
                                 { "name": "후배 질문", "lines": [ { "lineId": "L-D1-7", "answersQuestionId": "Q-0001", "asked": "마르부르크에서 학기 중 현지 인턴 병행할 수 있어요?",
                                                                      "text": "학기 중에는 수업이 많아 인턴은 어렵고, 방학에 단기 인턴을 했어요.", "match": true, "identifying": false } ] } ] } }
```

### saveConsent(draftId, edits)
payload `{draftId, edits:{removed:[lineId], changed:[{lineId, text}]}, consent:true}`. `removed` = 동의 시트에서 끈 문장(내 경험노트에는 남고 해봤노트에는 안 들어감). 이미 공유한 경험노트에서 다시 부르면 공유 범위를 바꾼다.
**[11/19]** 통과한 문장은 `runtime/noteLines.json`에 `{noteId, section, text, sourceId: "I-…", semester, answersQuestionId?, asked?}`로 쌓인다(작업 26·74). `answersQuestionId`가 있으면 그 질문을 `status: "answered"`, `noteId`로 바꾸고 질문자에게 알림 `「내 질문에 선배가 답했어요 · {프로그램} 해봤노트」`(`alerts.json`, `questionId`·`noteId` 포함)를 보낸다. **칸 이름이 같다는 이유만으로 알림을 보내지 않는다.** 노트가 아직 없는 프로그램이면 새 노트 id를 만든다(`"N-" + slug`).
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

### listNotes(filter)
payload `{filter:{type?: "교환"|"파견"|"인턴"|"비교과", q?: "검색어"}}`
```json
{ "notes": [ { "id": "N-marburg", "program": "마르부르크필립스대학교", "type": "교환",
  "oneLine": "TestDaF는 3학기 전부터, 기숙사는 합격 직후 신청", "forWhom": "독일어권 교환을 생각하는 1~2학년",
  "evidenceCount": 7, "lastSemester": "2026-1", "satisfaction": null, "completedCount": null, "country": "독일", "scrapped": true },
  { "id": "N-3ca17d", "program": "HUFS 동문멘토링 데이", "type": "비교과",
  "oneLine": "", "forWhom": "2학년이 많이 이수한 비교과", "evidenceCount": 0, "lastSemester": "2026-1", "satisfaction": 4.2, "completedCount": 150, "country": null, "scrapped": false } ] }
```
**[11/22]** `country`는 국제교류(교환·파견) 노트만 `programs.json`의 `세부`(국가) 글자 그대로, 인턴·비교과는 `null` → 카드 띠는 「교환학생 · 독일」, `null`이면 종류만. `scrapped`는 부른 사람(토큰) 기준 스크랩 여부. `oneLine`이 `""`이면 화면은 「–」(6-2).

### scrapNote(noteId, scrap) [11/22]
payload `{noteId, scrap?: true|false}`(생략 = 켜기). 같은 상태로 다시 불러도 `ok`(멱등). 기록은 `runtime/scraps.json`(사람별 노트 id 목록). AI 없음.
```json
{ "ok": true, "noteId": "N-marburg", "scrapped": true }
{ "error": "노트를 찾지 못했어요" }
```
mock은 기억하지 않는다(받은 값을 그대로 돌려주고, 목록·노트의 `scrapped`는 mock-data.json 고정값). 화면은 응답의 `scrapped`로 버튼 상태를 바꾼다.

### saveQuestion(noteId, section) [11/22]
「질문함에 담기」 버튼(디자인 규칙 6-2 근거 없음 · 6-1 오래된 근거, PRD ⑧). 그 노트의 한 칸을 **질문함에 `hold`로** 넣는다 → 다음 선배 인터뷰(`interviewNext`)가 「후배가 이렇게 물었어요」로 먼저 묻고, 답이 공유되면 `answered` + 질문자 알림(기존 흐름 그대로). 질문 글은 서버가 정한다(`"{칸} 이야기를 최근 경험으로 듣고 싶어요."`, 자유 입력 없음 → 검사·AI 없음). 같은 사람·노트·칸의 `hold` 질문이 있으면 새로 만들지 않고 `already: true`(멱등). `후배 질문` 칸과 노트에 없는 칸은 오류.
```json
{ "ok": true, "questionId": "Q-0101", "already": false, "message": "질문함에 담았어요. 다음 선배 인터뷰 때 먼저 물어볼게요." }
{ "error": "담을 수 없는 칸이에요" }
{ "error": "노트를 찾지 못했어요" }
```
화면은 `message`를 토스트로 보여 주고, 버튼을 「질문함에 담았어요」(비활성)로 바꾼다. mock은 고정값을 돌려준다.

### getNote(id)
칸 순서와 이름은 `data/frames.json`을 따른다. 빈 칸도 `lines: []`로 보낸다. `interviewOnly`가 true인 칸은 선배 인터뷰로만 채워진다.
**[11/19] 노트가 만들어지는 규칙(작업 26, PRD 4-2)**: 노트 = `data/notes.json`(사전 생성) + `runtime/noteLines.json`(동의 통과 인터뷰 문장)의 합집합.
- `tools/build_notes.py`(원우)가 `evidence.json`을 프로그램별·칸별로 묶어 `notes.json`을 만든다. 칸 문장 = 근거 문단 **원문 그대로 1:1**(`text` = `evidence.text`, `sourceId` = `evidence.id`, AI 변환 없음). `official`은 학점·장학·선발·자격 키워드 정규식. `forWhom`은 템플릿(`"{국가}권 {분야}를 생각하는 1~2학년"` / 인턴 `"{직군} 분야 현장실습을 생각하는 2~3학년"`), `oneLine`은 근거가 가장 많은 칸의 첫 문장(P1-여건 78: 칸별 AI 한 줄 요약 `sectionSummary`), `evidenceCount` = 보고서 문단 + 동의 인터뷰 문장, `lastSemester` = 최대 학기. 현장실습 노트의 자동 분류 문장은 `autoClassified: true`(화면 「자동 분류」 라벨).
- 서버는 응답할 때 `noteLines.json`의 같은 `noteId` 문장을 해당 칸 뒤에 붙인다(`docType: "인터뷰"`). **「후배 질문」 칸**의 문장은 `asked`(Q)와 `text`(A)를 함께 보내고, 화면은 Q·A 쌍으로 원문 인용한다(합쳐 요약하지 않음). 같은 `answersQuestionId`에 선배 여럿이 답하면 A가 쌓인다.
- **[11/22] 배운점 `senior`**: 배운점 칸 문장마다 `"senior": "선배 A"`. 글자는 **이 노트 안에서만** 쓰는 것으로, 칸에 처음 나온 선배부터 A·B·C(같은 선배는 같은 글자). 학과는 넣지 않는다 — PRD 9-1(노트가 프로그램 단위라 학과까지 보이면 소수 학과에서 특정됨). 닮은선배 `nickname`과도 같은 글자를 쓰지 않는다(이으면 학과가 드러남). 화면은 「선배 A · 2025」(senior + 출처 연도). 쓴 사람을 모르면 `senior`가 없다 → 출처만.
- `sources[*].semester`는 그대로 보내고 화면이 연도만 표시한다(0장). 근거 1~2건인 칸은 화면이 「선배 1명의 경험이에요」 라벨(`lines.length`로 판단, 서버 필드 없음).
```json
{ "id": "N-marburg", "program": "마르부르크필립스대학교", "type": "교환",
  "oneLine": "...", "forWhom": "...", "evidenceCount": 7, "lastSemester": "2026-1", "satisfaction": null, "completedCount": null,
  "country": "독일", "scrapped": true,   // [11/22] listNotes와 같음
  "officialUrl": "https://...",
  "sections": [ { "name": "지원", "interviewOnly": false,
                  "lines": [ { "text": "...", "sourceId": "R03-1-1", "lineId": "L-R03-1-1", "official": false } ] },
                { "name": "후배 질문", "interviewOnly": true,
                  "lines": [ { "asked": "마르부르크에서 학기 중 현지 인턴 병행할 수 있어요?", "answersQuestionId": "Q-0001",
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
- 후보 = 그 노트(희망 프로그램)의 경험자 **전부**. 점수 하한은 없다(단과대가 달라도 그 경험을 한 선배는 추천한다). 직원 행·본인은 뺀다.
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
```json
{ "seniors": [ { "studentId": "H0469", "nickname": "독일어과 선배 A", "score": 14, "requestsFull": false,
                 "reasons": ["희망 프로그램을 경험했어요", "같은 서양어대학", "같은 독일어과", "이중전공 경영학 같음", "한국외국어대학교 직무탐색 집중교육 함께 이수"] },
               { "studentId": "H0241", "nickname": "독일어과 선배 B", "score": 12, "requestsFull": false,
                 "reasons": ["희망 프로그램을 경험했어요", "같은 서양어대학", "같은 독일어과", "이중전공 경영학 같음"] } ],
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
- **보낸 사람이 취소(P0)**: `respondRequest(threadId, cancel: true)`로 기다리는 요청을 거둔다 → `status: "cancelled"`, 한도에서 빠진다. 취소한 선배에게는 7일 동안 다시 요청하지 못한다(반복 요청 방지). 선배 화면에서는 그 요청이 조용히 사라진다(알림 없음).
- **자동 만료(P1)**: 보낸 뒤 **7일** 안에 선배가 수락·거절하지 않으면 서버가 `status: "expired"`로 바꾸고 한도에서 뺀다. 보낸 사람에게 알림 「선배가 아직 못 봤어요. 다른 선배에게 보내 볼까요?」(`alerts.json`). 만료 판정은 `getMessages`·`sendMessage` 호출 때 `requestedAt` 기준으로 한다(별도 스케줄러 없음). 시연에서는 7일이 지나지 않으므로 문구로만 설명한다.
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

### getMessages()
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
**[11/23 차단]** `status: "blocked"`인 대화는 양쪽 목록에 남고 `blockedByMe`(내가 차단했는지)가 붙는다. 화면은 입력창 대신 차단한 쪽에 「차단한 대화예요」, 차단당한 쪽에 「더 이어 갈 수 없는 대화예요」를 보인다(누가 차단했는지 상대에게 말하지 않음).

### respondRequest(threadId, accept | cancel)
payload `{threadId, accept: true|false}` 또는 `{threadId, cancel: true}`.
- `accept`: 받은 선배가 수락·거절한다. `waiting`이 아닌 대화에는 `{ "ok": false, "reason": "상태" }`.
- `cancel`: 보낸 사람이 기다리는 요청을 거둔다(`waiting` → `cancelled`). 자기 대화가 아니거나 `waiting`이 아니면 `{ "ok": false, "reason": "상태" }`.
```json
{ "ok": true, "status": "accepted" }
{ "ok": true, "status": "cancelled" }
```
**[작업 85]** 서버는 화면 호환을 위해 옛 필드 `accepted: true|false`도 함께 보낸다(`respondRequest` 수락·거절 응답, `getMessages`의 각 대화). 새 화면은 `status`만 쓴다. 11/20 이전 기록의 `status: "requested"`는 `waiting`으로 읽는다.

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
                 "share": "partial", "filled": 4, "total": 7, "sharedLines": 3, "updatedAt": "..." } ],   // [11/22] 최근에 요약한 것이 위
  "questions": [ { "questionId": "Q-0001", "text": "...", "status": "hold", "askedAt": "..." },
                 { "questionId": "Q-0002", "text": "...", "status": "answered", "noteId": "N-marburg", "answeredAt": "..." } ],
  "scraps": [ { "noteId": "N-marburg", "program": "마르부르크필립스대학교" } ],   // [11/22] scrapNote로 켠 노트, 최근이 위
  "alerts": [ { "text": "내 질문에 선배가 답했어요 · 마르부르크필립스대학교 해봤노트", "questionId": "Q-0002", "noteId": "N-marburg", "at": "..." } ] }
```
**[11/22] 내 경험노트 카드(`myNotes`)**: `id`는 내 경험노트 번호(`M-…`), `noteId`는 공유되는 해봤노트 번호. `share` = `private`(나만 보기) | `partial`(일부 공유 — 화면 「N문장 공유」, N = `sharedLines`) | `shared`(해봤노트 공유됨). **「반영 중」 상태는 없다** — `saveConsent`가 그 자리에서 해봤노트에 반영하므로(11/22 미리 결정), 공유 직후 알림은 「해봤노트에 내 이야기가 반영됐어요」(`noteId` 포함). `filled`/`total` = 노트 틀에서 내 문장이 있는 칸 수 / 전체 칸 수(「노트 틀 4/7」). `sharedLines` = 지금 해봤노트에 보이는 내 문장 수(신고로 숨긴 것 제외).
**[11/19]** 질문 `status`는 `hold`(미답변) | `answered`. 화면은 `answered`에 「선배가 답했어요」 라벨 + 노트 「후배 질문」 칸 링크. (이전 예시의 `waiting`은 쓰지 않는다.)

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

### demandNext(state) [11/22 열림]
「궁금한 것 정리하기」(수요 인터뷰) 다음 단계 하나. **AI 없음** — 칩과 규칙만(`functions/demand.py`). interviewNext처럼 서버는 기억하지 않고, 화면이 응답의 `state`를 들고 다니다 고른 값·쓴 답을 넣어 다시 보낸다.
순서: `field`(국제교류·현장실습·비교과·잘 모르겠어요) → (`explore`: 「잘 모르겠어요」면 고민 칩으로 분야·분류를 정함) → `detail`(국제교류 = 나라, 현장실습 = 기관 유형, 비교과 = 프로그램 분류, `programs.json` `세부`) → `program`(그 분류의 프로그램 + 「아직 정하지 않았어요」) → `section`(노트 틀 칸, 후배 질문 제외) → `when`(이번 학기·다음 학기·1년 뒤·아직 몰라요) → **답변 3개** `situation`(지금 내 상황) · `question`(고른 칸에 대해 선배에게 묻고 싶은 것) · `hope`(이 경험이 남겨 줬으면 하는 것) → `more`(더 궁금한 것 최대 2개, `canSkip` — 건너뛰려면 `state.moreDone = true`).
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
저장: 질문 문장(가장 궁금한 것 + 더 궁금한 것)을 **질문함에 `hold`로**(`프로그램명`·`칸`·`시기`·`수요: true`) — 다음 그 프로그램 선배의 들려주기가 「후배 질문」으로 먼저 묻고(작업 74), 콘솔 수요 현황에도 합산된다. `fromQuestionId`로 시작했으면 그 질문 행에 맥락만 붙인다(질문함이 늘지 않음). 상황·바라는 것은 `runtime/demands.json`에만 둔다(선배에게 보내지 않음, 부서 집계는 P1).
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
login(id, pw) · getMe() · askBoo(question)
interviewNext(program, answers) · summarizeInterview(program, transcript) · saveConsent(draftId, edits)
listNotes(filter) · getNote(id) · scrapNote(noteId, scrap = true) · saveQuestion(noteId, section) · reportStatement(lineId, reason)   // scrapNote·saveQuestion [11/22]
recommendSeniors(noteId, more) · checkMessage(text) · previewNickname(to) · sendMessage(to, text) · getMessages() · respondRequest(threadId, accept) · cancelRequest(threadId) · reportThread(threadId, reason, block = false)   // cancelRequest = respondRequest {threadId, cancel: true} (작업 85) · reportThread [11/23 차단]
getInbox() · getMyNote(id) · getDeptReport(dept)   // getMyNote [11/22]
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
- **[11/19]** `getNote["N-marburg"]`에 7번째 칸 `후배 질문`(`interviewOnly: true`, Q·A 1쌍, `asked`·`answersQuestionId: "Q-0001"`). `interviewNext.byProgram["마르부르크필립스대학교"].steps[0]`은 `section: "후배 질문"`(questionId·asked·pendingQuestions 1), `steps[1..]`은 기존 칸, `total` 7. `summarizeInterview.publicDraft`에 `후배 질문` 칸 1문장. `saveConsent`에 `answered: ["Q-0001"]`. `getInbox.questions[1]`은 `answered`, `alerts[0]`은 「내 질문에 선배가 답했어요」. `getNote["N-kotra"]`는 칸 6개(…`근무조건`, `후배 질문`)이고 자동 분류 문장에 `autoClassified: true`.

## 7. data/frames.json (이번에 함께 생성)

```json
{
  "교환": { "칸": ["지원", "학점", "비용", "생활", "팁", "배운점", "후배 질문"], "인터뷰로만": ["배운점", "후배 질문"] },
  "파견": { "칸": ["지원", "학점", "비용", "생활", "팁", "배운점", "후배 질문"], "인터뷰로만": ["배운점", "후배 질문"] },
  "인턴": { "칸": ["지원동기", "업무내용", "배운점", "지원·선발", "근무조건", "후배 질문"], "인터뷰로만": ["지원·선발", "근무조건", "후배 질문"] },
  "비교과": { "칸": ["활동내용", "배운점", "후배 질문"], "인터뷰로만": ["후배 질문"] }
}
```
- 11/16: 교환·파견에 `배운점` 추가(PRD 4-1). 실제 `data/frames.json` 반영은 작업 70. `배운점` 칸은 해봤노트에서 선배별 원문 인용으로 렌더한다(합쳐 요약하지 않음).
- **11/19: 네 틀 모두에 `후배 질문` 추가**(PRD 4-2 ⑤). 질문함의 미답변 질문과 그 답이 Q·A 쌍으로 쌓이는 칸. 보고서 문항 매핑(9장)은 바뀌지 않는다. `data/frames.json`에 11/19 반영 완료. (P1-여건, 작업 84) 칸별 `"예시"`: `{"지원": ["출국 3학기 전", "1년 전", "합격 후"], …}` 모양으로 원우가 추가하면 `interviewNext.examples`로 나간다.

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

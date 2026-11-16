# 외대人사이드 함수·응답 명세 v1 (2026-11-14)

이 문서대로 `common/data.js`, `common/mock-data.json`, `data/README.md`를 채운다.
화면은 `common/data.js`의 함수만 부르고, 응답 모양은 이 문서를 따른다.
명세를 바꿔야 하면 코드보다 이 문서를 먼저 고치고 팀에 알린다.

> 11/14 개정: 데이터 키를 시트 헤더 그대로(0장·9장), 선배·후배 고정 없음(0장), login·getMe 모양 변경(4장), 인턴 노트 5칸(6장).
> 11/16 개정 ②(데이터 기준 확정): **최종 데이터 원본 = `@VCC/가상데이터/가상데이터_1000명.xlsx`**. 9장을 그 파일의 시트·헤더로 다시 썼다. 시연 인물을 그 파일의 실제 행(H0143·H0469·H0745)으로 바꾸고, 시연 프로그램을 데이터에 있는 `마르부르크필립스대학교`로, 공통 비교과를 `합격 면접 취업특강(커리어랩)`으로 바꿨다(1·3·4·6장 예시 포함). 학생 A는 2학년(1학년은 이중전공 없음).
> 11/16 개정(PRD 4-1): 교환·파견 노트 틀에 `배운점`(인터뷰로만) 추가 → 6칸. `summarizeInterview`가 끝나면 myNote를 서버가 바로 저장(저장은 기본, 공유는 선택). `saveConsent`의 `edits.removed`가 문장 단위 비공개를 뜻함. 공개 초안 문장에 `identifying` 표시 추가. 사람 이름: 추천 선배는 `독일어과 선배 A`, 쪽지 보낸 사람은 `형용사 + 동물`(대화마다 새로) — `previewNickname`·`respondRequest` 신설, `sendMessage`·`getMessages`에 `myNickname`·`role`·`askerInfo` 추가.

## 0. 공통 규칙

- 모든 함수는 `async`이고 JSON 객체를 돌려준다.
- 실패 시 공통 모양: `{ "error": "사람이 읽을 메시지" }`. 화면은 `res.error`가 있으면 안내 문구를 보여 준다.
- 학기 표기는 `"2025-1"`, `"2025-2"`, `"2025-여름"`, `"2025-겨울"`.
- 화면에는 학번을 보여 주지 않는다. 다른 사람은 서버가 자동 생성한 닉네임(`nickname`)으로만 표시한다(닮은 선배 카드, 익명 쪽지창). 닉네임은 시트·프로필에 두지 않는다. 형식은 **`학과 + " 선배 " + 영문 대문자`**(예: `"독일어과 선배 A"`)이고 학번·입학년도는 넣지 않는다. 글자는 보는 사람 기준으로 처음 만난 순서대로 A, B, C…를 주고, 그 사람에게는 카드·프로필·쪽지창에서 계속 같은 값을 쓴다.
- **쪽지를 보낸 사람**은 다른 이름 체계를 쓴다: `"형용사 + 동물"`(예: `"용감한 수달"`). 쪽지 요청을 여는 순간 서버가 만들고 **대화(thread) 하나마다 새로** 정한다(같은 후배가 다른 선배에게 보내면 다른 이름). 선배 화면에서 보낸 사람은 이 이름 + 학년 + 관심 경험만 보이고 학과는 보이지 않는다. 보낸 사람 화면에서 선배는 계속 `"독일어과 선배 A"`다. 즉 **보는 사람 입장에서 상대 이름은 늘 하나**다.
- 로그인한 사용자 정보는 화면이 `sessionStorage`의 `"me"`에 저장한다. 함수는 이를 따로 받지 않는다(서버 연결 후 미리가 처리).
- **데이터 열 이름은 `가상데이터_1000명.xlsx`의 헤더를 그대로 쓴다.** 가상학생 시트는 종합정보시스템 학적 영문 코드(`colreg_no`, `crs_nm`, `dbl_mjr_nm` 등), 나머지 시트는 한글 헤더(`학번`, `학년도`, `프로그램명` 등)가 JSON 키가 된다. 시트에 없는 값만 영어 이름을 붙인다(예: `docType`, 자동 생성 `nickname`). 자세한 대응은 9장.
- **변환에서 빼는 열**: `studt_na_kr`(가상 성명)·`sex`·`나이(만)`은 시트에만 두고 `students.json`에 넣지 않는다(저장소가 공개돼도 명단처럼 보이지 않게). 사람을 구분하는 열쇠는 `colreg_no` 하나로 충분하다(1,001개 모두 고유, 다른 시트 학번과 100% 연결 확인).
- **응답에 넣지 않는 열**: `비번`(로그인 대조만).
- **선배·후배를 사람에게 고정하지 않는다.** 같은 사람이 어떤 프로그램에서는 묻고, 다른 프로그램에서는 답한다. 그 프로그램을 이수한 기록(가상비교과·가상학생의 파견·인턴 열·귀국보고서·현장실습후기)이 있으면 그 프로그램에 대해 답할 수 있다. 학년과 상관없다. "닮은 선배"의 선배는 "그 경험을 먼저 해 본 사람"이라는 뜻이다.

## 1. 시연 인물과 가상 계정 (README.md에도 적을 것)

| 역할 | 아이디 | 비밀번호 | 설명 |
|---|---|---|---|
| 학생 A | H0143 | 1 | 서양어대학 독일어과 2학년, 이중전공 경영학, 해외경험 없음. 비교과 `합격 면접 취업특강(커리어랩)`(2025-2) 이수. 질문하는 사람 |
| 선배 B | H0469 | 1 | 독일어과 4학년, 이중전공 경영학, 학과 파견학생 독일 `마르부르크필립스대학교`(2024-1, 귀국보고서 있음), A와 같은 비교과 이수 |
| 선배 C | H0745 | 1 | 독일어과 4학년, 이중전공 브릭스, 교환학생 같은 대학(2024-2, 귀국보고서 있음). 비교 대상(공통점은 단과대·학과뿐) |
| 직원 | staff01 | 1 | 총괄 관리자(관리자 콘솔). 가상학생 시트 맨 아래 한 줄: `colreg_no`=`staff01`, `비번`=`1`, `crs_nm`=`전체`(부서 담당자면 부서명), 나머지 빈칸 |

모두 `가상데이터_1000명.xlsx`의 실제 행이다(성명 열은 화면에 쓰지 않음). 마르부르크필립스대학교 귀국보고서는 5편(H0469·H0534·H0745·H0751·H0995)이라 노트 근거로 충분하다. 학생 데이터(`data/students.json`)는 원우가 이 파일에서 변환한다. mock은 위 인물로 만든다.

## 2. 접속 주소 (README.md)

- 로컬: 저장소 폴더에서 `python -m http.server 8000` → `http://localhost:8000/screens/login/`
- 미리 개발 서버(미리 PC만): `functions/local_fn.py` → `http://localhost:8787`
- 공개 주소(GitHub Pages 등): 미정. 정해지면 추가.

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
| login | `id`가 `"staff"`로 시작하면 `login.staff`, 그 외 비밀번호가 `"1"`이면 `login.student`, 아니면 `login.fail` |
| askBoo | 질문에 `교환|파견|독일|마르부르크`가 있으면 `askBoo.exchange`, 그 외 `askBoo.hold` |
| interviewNext | `answers.length`가 0~2면 `interviewNext.steps[answers.length]`, 3 이상이면 `interviewNext.done` |
| getNote | `getNote[id]`가 있으면 그것, 없으면 `getNote["N-marburg"]` |
| checkMessage | 숫자가 8자리 이상 연속(전화·학번)이면 `checkMessage.blocked`, 그 외 `checkMessage.ok` |
| 나머지 | `m[name]` 그대로 |

## 4. 함수 15개

### login(id, pw)
payload `{id, pw}`
`status`는 시트 열이 아니라 서버가 정한다: `colreg_no`가 `staff`로 시작하면 `"직원"`(그 행의 `crs_nm`을 `부서명`으로 줌, 총괄 관리자는 `"전체"`), 그 외는 `"학생"`. 직원 행은 학생 집계·닮은 선배 후보·사용 로그 생성에서 뺀다.
```json
{ "ok": true, "user": { "colreg_no": "H0143", "status": "학생" } }
{ "ok": true, "user": { "colreg_no": "staff01", "status": "직원", "부서명": "전체" } }
{ "ok": false, "reason": "아이디 또는 비밀번호가 맞지 않아요." }
```

### getMe()
가상학생 한 줄(시트 헤더 그대로, `번호`·`비번` 제외) + 이수 기록. 이수 기록도 각 시트 헤더 그대로이고, 귀국보고서·현장실습후기는 본문 칸을 빼고 기본 정보만 담는다.
```json
{ "colreg_no": "H0143", "univ_nm": "서양어대학", "crs_nm": "독일어과", "dbl_mjr_nm": "경영학",
  "regst_grad": 2, "입학년도": 2025, "해외경험": "없음", "현장실습·인턴십": "있음",
  "인턴 유형": "국내 인턴십(학점 인정)", "기관 유형(가상)": "국제기구 한국사무소", "기관명(가상)": "국제이주정책연구소 서울사무소",
  "인턴 시기": "2학년 동계방학", "비교과 이수 건수": 3, "경험 조합": "인턴만",
  "비교과이수내역": [ { "이수학년도": 2025, "이수학기(1~4)": 3, "학기구분": "2학기",
                       "프로그램명": "합격 면접 취업특강(커리어랩)", "비교과 유형": "1회성", "이수 당시 학년": 1 } ],
  "귀국보고서": [],
  "현장실습후기": [] }
```
귀국보고서 항목 예: `{ "학년도": 2024, "학기": 1, "국가": "독일", "대학명": "마르부르크필립스대학교" }` · 현장실습후기 항목 예: `{ "학년도": 2025, "학기": 2, "업체명": "KOTRA 해외무역관(유럽 권역)", "직군": "전시·행사 지원" }`(학기 2 = 여름방학). 학기 숫자를 화면에 낼 때는 9장의 학기 코드표로 바꾼다.

### askBoo(question)
payload `{question}`. 근거가 있으면 `ok`, 없으면 `hold`(질문은 자동으로 질문함에 저장되고 `questionId`가 옴).
```json
{ "status": "ok",
  "lines": [ { "text": "...", "sourceId": "R03-1-1", "lineId": "L-R03-1-1" } ],
  "sources": { "R03-1-1": { "docType": "귀국보고서", "program": "마르부르크필립스대학교", "semester": "2024-1" } },
  "noteId": "N-marburg", "suggestSenior": false }
{ "status": "hold", "lines": [], "sources": {}, "questionId": "Q-0001", "suggestSenior": true,
  "message": "이 부분은 아직 들은 선배가 없어요. 질문함에 담아 두었어요. 닮은 선배에게 물어볼까요?" }
```
docType: `귀국보고서` | `현장실습후기` | `인터뷰`

### interviewNext(program, answers)
선배 인터뷰에서 다음 질문 하나. payload `{program, answers:[{section, question, answer}]}`
```json
{ "done": false, "section": "지원", "question": "마르부르크 파견은 언제부터 준비하셨어요?", "progress": { "filled": 0, "total": 6 } }
{ "done": true, "progress": { "filled": 6, "total": 6 } }
```
`total`은 그 프로그램 종류의 `frames.json` 칸 수(교환·파견 6). `배운점`은 다른 칸을 묻고 난 뒤 마지막에 묻는다.

### summarizeInterview(program, transcript)
payload `{program, transcript:[{section, question, answer}]}`. 두 장을 돌려준다: 내 경험 노트(1인칭, 나만 봄)와 공개용 초안(선배가 고치고 동의해야 공개).
**서버는 응답과 함께 myNote를 내 경험노트로 저장한다**(`saved: true`, `myNoteId`). 화면은 "내 경험노트에 저장됨"을 표시하고, 공유는 이후 `saveConsent`로만 한다. 같은 프로그램으로 다시 요약하면 같은 `myNoteId`를 갱신한다.
`match`는 AI 원문 일치 검사 결과. `false`면 화면이 "원문과 다를 수 있어요" 표시.
`identifying`은 코드(정규식·사전)가 찾은 본인 식별 문장(성적 숫자·수상·실명·특정 인물). `true`면 동의 시트에서 기본 꺼짐 + 주의 라벨.
```json
{ "draftId": "D-0001", "program": "마르부르크필립스대학교", "saved": true, "myNoteId": "M-0001",
  "myNote": { "sections": [ { "name": "지원", "lines": [ { "text": "나는 출국 3학기 전부터 TestDaF를 준비했다." } ] },
                           { "name": "배운점", "lines": [ { "text": "낯선 행정 절차를 혼자 끝까지 처리하는 법을 배웠다." } ] } ] },
  "publicDraft": { "sections": [ { "name": "지원", "lines": [ { "lineId": "L-D1-1", "text": "출국 3학기 전부터 TestDaF를 준비했어요.", "match": true, "identifying": false } ] } ] } }
```

### saveConsent(draftId, edits)
payload `{draftId, edits:{removed:[lineId], changed:[{lineId, text}]}, consent:true}`. `removed` = 동의 시트에서 끈 문장(내 경험노트에는 남고 해봤노트에는 안 들어감). 이미 공유한 경험노트에서 다시 부르면 공유 범위를 바꾼다.
```json
{ "ok": true, "noteId": "N-marburg", "added": 3 }
```

### listNotes(filter)
payload `{filter:{type?: "교환"|"파견"|"인턴"|"비교과", q?: "검색어"}}`
```json
{ "notes": [ { "id": "N-marburg", "program": "마르부르크필립스대학교", "type": "교환",
  "oneLine": "TestDaF는 3학기 전부터, 기숙사는 합격 직후 신청", "forWhom": "독일어권 교환을 생각하는 1~2학년",
  "evidenceCount": 7, "lastSemester": "2026-1", "satisfaction": null } ] }
```

### getNote(id)
칸 순서와 이름은 `data/frames.json`을 따른다. 빈 칸도 `lines: []`로 보낸다. `interviewOnly`가 true인 칸은 선배 인터뷰로만 채워진다.
```json
{ "id": "N-marburg", "program": "마르부르크필립스대학교", "type": "교환",
  "oneLine": "...", "forWhom": "...", "evidenceCount": 7, "lastSemester": "2026-1", "satisfaction": null,
  "officialUrl": "https://...",
  "sections": [ { "name": "지원", "interviewOnly": false,
                  "lines": [ { "text": "...", "sourceId": "R03-1-1", "lineId": "L-R03-1-1", "official": false } ] } ],
  "sources": { "R03-1-1": { "docType": "귀국보고서", "program": "마르부르크필립스대학교", "semester": "2024-1" } } }
```
`satisfaction`은 비교과 노트만 숫자(`가상비교과만족도`의 `만족도(5점)`), 국제교류·현장실습은 `null` → 화면은 "–"(실제 체계에 학생별 만족도가 없음).
`official: true`인 문장(학점 인정·장학금·자격 요건·선발 기준 같은 규정성 진술)은 화면이 "개인 경험이에요" 표시 + `officialUrl` 링크를 붙인다.

### recommendSeniors(noteId)
payload `{noteId}`. `nickname`은 서버가 만든 선배 표시명 「학과 + 선배 + 영문 대문자」(예: `"독일어과 선배 A"`, 디자인 규칙 1-2절). 같은 선배는 닮은선배·프로필·해봤노트 인용·쪽지창에서 같은 이름이다. 점수 계산은 `common/score.js`(원우). AI 없음.
```json
{ "seniors": [ { "studentId": "H0469", "nickname": "독일어과 선배 A", "score": 13,
                 "reasons": ["같은 서양어대학", "같은 독일어과", "이중전공 경영학 같음", "합격 면접 취업특강(커리어랩) 함께 이수"] } ] }
```

### checkMessage(text)
payload `{text}`. 연락처·학번은 코드(정규식), 비방은 AI 판정.
```json
{ "ok": true }
{ "ok": false, "reason": "연락처", "message": "전화번호나 학번은 보낼 수 없어요. 이메일은 괜찮아요." }
```
reason: `연락처` | `학번` | `비방`

### sendMessage(to, text)
payload `{to, text}`. `to`는 상대 studentId. 첫 메시지는 쪽지 신청이 된다.
첫 메시지일 때 서버가 이 대화에서 쓸 보낸 사람 닉네임(`myNickname`, 형용사 + 동물)을 만든다. 화면은 요청 시트를 열 때 `previewNickname(to)`로 같은 값을 미리 받아 「선배에게는 '용감한 수달'로 보여요」를 보여 준다.
```json
{ "ok": true, "threadId": "T-0001", "myNickname": "용감한 수달", "at": "2026-11-20T10:00:00+09:00" }
```

### previewNickname(to)
payload `{to}`. 이 선배에게 보낼 대화의 내 닉네임을 정해 돌려준다(아직 대화가 없으면 새로 만들고, 있으면 그 값). AI 없음, 목록(형용사 × 동물)에서 코드가 고른다.
```json
{ "myNickname": "용감한 수달" }
```

### getMessages()
`role`은 이 대화에서 내 역할: `asker`(쪽지를 보낸 사람) | `senior`(받은 선배). `nickname`은 **상대**의 이름으로, 내가 asker면 `"독일어과 선배 A"`, senior면 `"용감한 수달"`. `askerInfo`는 senior에게만 온다(학과 없음).
```json
{ "threads": [
  { "threadId": "T-0001", "role": "asker", "withId": "H0469", "nickname": "독일어과 선배 A", "myNickname": "용감한 수달",
    "accepted": true, "unread": 1,
    "messages": [ { "from": "me", "text": "...", "at": "..." }, { "from": "them", "text": "...", "at": "..." } ] },
  { "threadId": "T-0002", "role": "senior", "withId": "H0102", "nickname": "조용한 고래",
    "askerInfo": { "학년": 1, "관심": ["교환학생·독일"] },
    "accepted": false, "unread": 1,
    "messages": [ { "from": "them", "text": "...", "at": "..." } ] } ] }
```

### respondRequest(threadId, accept)
받은 선배가 쪽지 요청을 수락·거절한다. payload `{threadId, accept: true|false}`
```json
{ "ok": true, "accepted": true }
```

### getInbox()
```json
{ "myNotes": [ { "id": "N-marburg", "program": "마르부르크필립스대학교" } ],
  "questions": [ { "questionId": "Q-0001", "text": "...", "status": "waiting", "askedAt": "..." },
                 { "questionId": "Q-0002", "text": "...", "status": "answered", "noteId": "N-marburg" } ],
  "scraps": [ { "noteId": "N-marburg", "program": "마르부르크필립스대학교" } ],
  "alerts": [ { "text": "기다리던 질문에 새 노트가 생겼어요.", "noteId": "N-marburg", "at": "..." } ] }
```

### reportStatement(lineId, reason)
payload `{lineId, reason?}`. 신고된 문장은 즉시 숨김, 부서 리포트에 집계.
```json
{ "ok": true, "hidden": true }
```

### getDeptReport(dept)
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
listNotes(filter) · getNote(id) · reportStatement(lineId, reason)
recommendSeniors(noteId) · checkMessage(text) · previewNickname(to) · sendMessage(to, text) · getMessages() · respondRequest(threadId, accept)
getInbox() · getDeptReport(dept)
```

## 6. mock-data.json 작성 지시

- 최상위 키는 함수 이름. 3장 pickMock 규칙에 나오는 하위 키(`login.student/staff/fail`, `askBoo.exchange/hold`, `interviewNext.steps/done`, `getNote["N-marburg"]`, `checkMessage.ok/blocked`)를 만든다.
- 내용은 1장 시연 인물 기준. askBoo.exchange 문장 3개, getNote["N-marburg"]는 교환 6칸(지원·학점·비용·생활·팁·배운점) 중 4칸 채우고 비용은 빈 칸, 배운점은 `interviewOnly: true`로 선배 인용 1개(`docType: "인터뷰"`).
- `getNote["N-kotra"]`도 하나: 현장실습 노트(`KOTRA 해외무역관(유럽 권역)`, 데이터에서 후기가 가장 많은 기관), 칸은 5개 [`지원동기`, `업무내용`, `배운점`, `지원·선발`, `근무조건`]. 마지막 두 칸은 `interviewOnly: true`이고 비어 있음. (`지원·선발`은 한 칸의 이름이다)
- 출처 학기는 B의 보고서 `2024-1`, C의 보고서 `2024-2`. 노트의 `lastSemester`는 마르부르크 보고서 중 최근인 `2026-1`.
- recommendSeniors는 B(13점: 단과대 3+학과 5+이중전공 3+공통 비교과 2), C(8점: 단과대·학과) 두 명(PRD·score.js 기본 가중치 기준). 가상 문장만 쓰고 실제 후기 원문을 옮기지 않는다.

## 7. data/frames.json (이번에 함께 생성)

```json
{
  "교환": { "칸": ["지원", "학점", "비용", "생활", "팁", "배운점"], "인터뷰로만": ["배운점"] },
  "파견": { "칸": ["지원", "학점", "비용", "생활", "팁", "배운점"], "인터뷰로만": ["배운점"] },
  "인턴": { "칸": ["지원동기", "업무내용", "배운점", "지원·선발", "근무조건"], "인터뷰로만": ["지원·선발", "근무조건"] },
  "비교과": { "칸": ["활동내용", "배운점"] }
}
```
- 11/16: 교환·파견에 `배운점` 추가(PRD 4-1). 실제 `data/frames.json` 반영은 작업 70. `배운점` 칸은 해봤노트에서 선배별 원문 인용으로 렌더한다(합쳐 요약하지 않음).

## 8. 완료 확인

- `screens/talk/index.html`에 askBoo를 부르는 임시 화면(입력창+버튼+결과)을 두고, "마르부르크 파견 준비 언제부터?"는 출처 달린 문장 3개, "HUFS특강 어때요?"는 보류 안내가 나온다.
- data/README.md에는 이 문서 4장의 응답 모양을 표로 옮기고 "원본: docs/spec-v1.md"라고 적는다.

## 9. 데이터 파일 (원우: 시트 → data/)

**원본: `@VCC/가상데이터/가상데이터_1000명.xlsx`** (가상학생 1,000 · 가상비교과 2,248 · 가상비교과만족도 139 · 가상귀국보고서 367 · 가상현장실습후기 277 · 가상질문 80). 시트 하나가 파일 하나. 각 행은 객체 하나이고, 키는 시트 헤더를 글자 그대로 쓴다(띄어쓰기·괄호·마침표 포함). `분포요약`·`생성기준` 시트는 변환하지 않는다.

| 시트 | 파일 | 키(헤더 그대로) |
|---|---|---|
| 가상학생 | `students.json` | `번호` `colreg_no` `비번` `univ_nm` `crs_nm` `dbl_mjr_nm` `regst_grad` `입학년도` `해외경험` `해외경험 유형` `파견국가` `파견대학` `파견시기` `현장실습·인턴십` `인턴 유형` `기관 유형(가상)` `기관명(가상)` `인턴 시기` `비교과 이수 건수` `비교과 유형` `이수 비교과 프로그램` `경험 조합` |
| 가상비교과 | `extracurricular.json` | `번호` `가상학번` `학과(전공)` `현재 학년` `이수학년도` `이수학기(1~4)` `학기구분` `프로그램명` `비교과 유형` `이수 당시 학년` |
| 가상비교과만족도 | `extracurricular-satisfaction.json` | `번호` `프로그램명` `비교과 유형` `이수 인원(가상)` `만족도(5점)` |
| 가상귀국보고서 | `reports.json` | `학번` `학년도` `학기` `국가` `대학명` + 문항 헤더 14개(`1. 출국 전 준비사항` … `4. 후배들에게 남기고픈 한마디`) |
| 가상현장실습후기 | `internships.json` | `학번` `학년도` `학기` `업체명` `직군` `후기` |
| 가상질문 | `eval-questions.csv` | `번호` `질문` `정답` |
| 부서목록(작성 예정, PRD 6-2) | `departments.json` | 시트를 만들 때 정한 헤더 그대로 |

- **학생 열쇠**: `가상학생.colreg_no` = `가상비교과.가상학번` = `가상귀국보고서.학번` = `가상현장실습후기.학번` (값 형식 `H0001`~`H1000`).
- **학기 코드**(세 시트 공통): `1`=1학기, `2`=여름방학, `3`=2학기, `4`=겨울방학. 화면·응답의 `semester`는 `"2024-1"`, `"2025-여름"`, `"2024-2"`, `"2025-겨울"`로 바꿔 쓴다. 가상비교과는 `이수학기(1~4)` 숫자와 `학기구분` 글자가 같이 있다.
- **dbl_mjr_nm**: 1학년은 빈칸(이중전공 미선택). 2~4학년은 모집단 분석 비율로 배정(생성기준 시트).
- **programs.json은 시트가 아니라 변환 스크립트가 만든다**: 국제교류 = `가상학생`의 (`파견국가`, `파견대학`) 고유값, 프로그램명은 `파견대학` 글자 그대로(예: `마르부르크필립스대학교`) · 현장실습 = `가상현장실습후기.업체명` 고유값 · 비교과 = `가상비교과만족도.프로그램명`. 키: `프로그램명` `분야`(국제교류/현장실습/비교과) `세부`(국가 / 기관 유형 / 비교과 유형) `만족도(5점)`(비교과만) `운영부서코드`(부서목록 시트가 생기면). 모든 시트의 프로그램명은 이 목록과 글자 그대로 같아야 한다(askBoo 1단계 대조 기준).
- **노트 틀**: 국제교류 노트는 `frames.json`의 `교환` 틀(파견과 같음), 현장실습 노트는 `인턴` 틀, 비교과는 `비교과` 틀.
- `evidence.json`은 시트가 아니라 `reports.json`·`internships.json`에서 만드는 근거 문단 목록이다. 문단 하나가 `{ "id", "docType", "학번", "학년도", "학기", "프로그램명", "문항", "칸", "text" }`. `문항`은 원래 시트 헤더 글자 그대로(예: `"2-4. 기숙사 정보"`, `"후기"`), `칸`은 `frames.json`의 칸 이름.
- 귀국보고서 문항 → 칸: 지원(1-1, 1-2, 1-3) · 학점(2-2, 2-3, 3) · 비용(2-6) · 생활(2-1, 2-4, 2-5, 2-7) · 팁(4). `1.`·`2.` 제목 칸은 비어 있어 건너뛴다.
- 현장실습후기는 `후기` 한 칸 자유 서술이다. 문단마다 한 건으로 쪼개고 `칸`은 비워 둔다 → 작업 50(문단 자동 분류)이 `지원동기`·`업무내용`·`배운점` 중 하나를 채운다.
- 함수 응답(4장)의 `studentId`, `withId`, `to`는 `colreg_no` 값을 가리킨다.

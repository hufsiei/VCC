# 데이터 약속표

원본: docs/spec-v1.md (4장 함수, 9장 데이터 파일). 이 표와 명세가 다르면 명세가 맞습니다. 바꿔야 하면 명세를 먼저 고치고 팀에 알립니다.
모든 데이터는 가상입니다. 실제 학생 정보와 후기 원문은 올리지 않습니다.

## 데이터 파일

**원본: `@VCC/가상데이터/가상데이터_1000명.xlsx`** (구글 드라이브). 시트 하나가 파일 하나입니다. **JSON 키는 시트 헤더를 글자 그대로** 씁니다(띄어쓰기·괄호·마침표 포함). 시트에 없는 값만 영어 이름을 붙입니다. `분포요약`·`생성기준` 시트는 변환하지 않습니다.

| 시트 | 파일 | 키 |
|---|---|---|
| 가상학생 (1,000 + 직원 2) | `students.json` | 아래 표 |
| 가상비교과 (2,249) | `extracurricular.json` | `번호` `가상학번` `학과(전공)` `현재 학년` `이수학년도` `이수학기(1~4)` `학기구분` `프로그램명` `비교과 유형` `이수 당시 학년` |
| 가상비교과만족도 (130) | `extracurricular-satisfaction.json` | `번호` `프로그램명` `비교과 유형` `이수 인원(가상)` `만족도(5점)` |
| 가상귀국보고서 (280) | `reports.json` | `학번` `학년도` `학기` `국가` `대학명` + 문항 14개(아래) |
| 가상현장실습후기 (277) | `internships.json` | `학번` `학년도` `학기` `업체명` `직군` `후기` |
| 가상질문 | `eval-questions.csv` | `번호` `질문` `정답` `기대결과` `관련 프로그램` `관련 칸` `기대 근거ID` `유형` `봉인` `질문자 학번` `비고` |
| 부서리스트 (9) | `departments.json` | `부서코드` `부서명` `담당분야` `비교과 배정 키워드` `대표메일(가상)` `공식안내URL` `배정 범위(설명)` |
| 비교과_부서배정(확인용) | (변환하지 않음) | `수동 지정 부서코드`만 programs.json의 운영부서코드에 반영 |
| (시트 아님) | `programs.json` | 변환 스크립트가 만든 프로그램 목록. 아래 |

### students.json (가상학생 — 종합정보시스템 학적 영문 코드)

시트의 `studt_na_kr`(성명)·`sex`·`나이(만)`은 **변환할 때 뺍니다**(저장소에 이름·성별·나이가 있는 명단처럼 보이는 파일을 두지 않기 위해). 사람 구분은 `colreg_no` 하나로 충분합니다.

| 키 | 뜻 | 응답에 |
|---|---|---|
| 번호 | 행 번호 | 넣지 않음 |
| colreg_no | 학번(가상, `H0001`~`H1000`, 직원 `staff01`·`staff02`). 다른 시트의 `가상학번`·`학번`과 같은 값. 사람을 잇는 유일한 열쇠 | 내 정보에만 |
| 비번 | 로그인 대조용(전원 `1`). 서버는 이 열을 읽지 않고 `VCC_LOGIN_PW`만 본다 — 열 삭제는 원우 | **넣지 않음** |
| univ_nm | 단과대학 (`서양어대학`) | |
| crs_nm | 학과(전공) (예: `독일어과`, `프랑스어학부 FATI전공`) | |
| dbl_mjr_nm | 이중전공명 (예: `경영학`). **1학년은 빈칸** | |
| regst_grad | 학년 | |
| 입학년도 · 해외경험 · 해외경험 유형 · 파견국가 · 파견대학 · 파견시기 | 국제교류 이수 요약 | |
| 현장실습·인턴십 · 인턴 유형 · 기관 유형(가상) · 기관명(가상) · 인턴 시기 | 현장실습 이수 요약 | |
| 비교과 이수 건수 · 비교과 유형 · 이수 비교과 프로그램 · 경험 조합 | 비교과 요약 | |

선배·후배를 나누는 열은 두지 않습니다. 같은 사람이 이수한 프로그램에서는 답하고, 이수하지 않은 프로그램에서는 묻습니다. 직원 계정은 가상학생 시트 맨 위 두 행입니다: `staff01`(`crs_nm` = `전체`, 총괄 관리자)과 `staff02`(`crs_nm` = `혁신지원팀`, 부서 담당자). `colreg_no`가 `staff`로 시작하면 직원이고, `crs_nm`이 `전체`면 권한 `총괄`, 부서명이면 권한 `부서`(그 부서만 조회)입니다. 이 행들은 학생 집계·닮은 선배 후보·사용 로그에서 뺍니다.

### 학기 코드 (세 시트 공통)

`1` = 1학기 · `2` = 여름방학 · `3` = 2학기 · `4` = 겨울방학. 응답의 `semester`는 `2024-1`, `2025-여름`, `2024-2`, `2025-겨울`로 바꿔 씁니다.

변환 스크립트가 `extracurricular.json`·`reports.json`·`internships.json`·`evidence.json`의 각 행에 이 값을 `semester` 키로 미리 넣어 둡니다(시트에 없는 값이라 영어 키). 원래 학기 코드 열도 그대로 있습니다.

### programs.json (변환 스크립트가 생성 — 시트를 따로 만들지 않음)

쓰는 곳: askBoo 1단계 프로그램명 대조(목록에 없으면 AI 없이 보류) · 해봤노트 목록(프로그램 하나 = 노트 하나)과 분야 칩 · 관리자 콘솔의 질문→프로그램→운영부서 연결 · 별칭 대조(`마르부르크` → `마르부르크필립스대학교`). 별칭은 시연에 쓰는 것만 스크립트에 `별칭` 키(목록)로 적는다.

**별칭 (작업 82)**: 줄임말·옛 이름·오타가 있는 프로그램만 `별칭` 키(목록)를 가진다(원본은 `tools/sheet_to_json.py`의 `ALIASES`). 대조 규칙은 `tools/check_alias_match.py`가 기준이다.
1. 질문·프로그램명·별칭 모두 띄어쓰기를 지우고 영문은 소문자로 바꾼다.
2. 프로그램명이나 별칭이 질문 안에 들어 있으면 그 프로그램이 걸린다.
3. 걸린 말이 다른 걸린 말 안에 들어 있으면 짧은 쪽을 버린다(긴 이름 우선 — `밀라노` vs `밀라노 협력기관(온라인)`).

한 별칭이 두 프로그램에 걸리면 변환 스크립트가 오류를 낸다. 그래서 `리옹`(리옹2·리옹3)·`소르본`(파리 제4·제13)·단독 `KOTRA`는 넣지 않는다. 가짜 이름(함정 질문)도 넣지 않는다. 점검: `python tools/check_alias_match.py` → 답변 기대 25개 + 함정 3개 대조.

| 분야 | 어디서 | 프로그램명 |
|---|---|---|
| 국제교류 | `가상학생`의 (`파견국가`, `파견대학`) 고유값 | `파견대학` 글자 그대로(예: `마르부르크필립스대학교`) |
| 현장실습 | `가상현장실습후기.업체명` 고유값 | `업체명` 글자 그대로 |
| 비교과 | `가상비교과만족도.프로그램명` | 그대로 |

키: `프로그램명` `분야` `세부`(국가 / 기관 유형 / 비교과 유형) `만족도(5점)`(비교과만) `운영부서코드`. 모든 시트의 프로그램명은 이 목록과 글자 그대로 같아야 합니다(askBoo 1단계 대조 기준).

운영부서코드: 국제교류는 D01, 현장실습은 D02. 비교과는 ① `비교과_부서배정(확인용)` 시트의 `수동 지정 부서코드`, ② 없으면 부서리스트를 위에서부터 보며 `비교과 배정 키워드`(`;` 구분)가 프로그램명에 든 첫 부서. 130개 모두 배정돼야 합니다.

### reports.json 문항 헤더와 노트 칸

| 칸 (`frames.json`) | 문항 헤더 |
|---|---|
| 지원 | `1-1. 입학허가서 신청시 유의사항` `1-2. 비자 취득, 항공권 및 유학생 보험 구입` `1-3. 기타 유의사항` |
| 학점 | `2-2. 수강신청` `2-3. 수업내용 및 프로그램 과정` `3. 파견대학 취득 성적 본교 학점 인정 관련` |
| 비용 | `2-6. 소요 비용` |
| 생활 | `2-1. 공항에서 학교까지 교통편` `2-4. 기숙사 정보` `2-5. 교내 활동` `2-7. 기타 사항` |
| 팁 | `4. 후배들에게 남기고픈 한마디` |
| 배운점 | (없음 — 선배 인터뷰로만 채움, `frames.json`의 `인터뷰로만`) |
| (제목 칸, 비어 있음) | `1. 출국 전 준비사항` `2. 파견대학 관련` |

현장실습후기는 `후기` 한 칸 자유 서술입니다. **[11/20] 문장마다 한 건**으로 쪼개고(`id` = `I{후기 번호}-{후기 안 문장 순번}`, 예: `I001-1`, `I001-2`) `칸`은 비워 두면 작업 50(문장 자동 분류)이 `지원동기`·`업무내용`·`배운점` 중 하나를 채웁니다. 한 문단에 업무·배운점이 섞여 있어 문단 단위로는 칸 하나로 나눌 수 없기 때문입니다(spec 9장). 원래 문단 번호는 `문단` 키에 남깁니다. **작업 50 자동 분류 결과는 `data/intern-sections.json`(`{sourceId: 칸}`)에 따로 두고**, `sheet_to_json.py`가 변환할 때마다 `칸`과 `autoClassified: true`를 다시 입힙니다(evidence.json에만 써 두면 다시 변환할 때 지워지므로). 분류를 다시 돌렸으면 이 파일을 갈아 끼우고 `sheet_to_json.py` → `build_notes.py` 순서로 돌립니다. 11/20 전의 `I001-1`은 '1번 후기의 1번째 문단'이었고 지금은 '1번째 문장'이라, 옛 번호를 그대로 쓰면 다른 글을 가리킵니다. `지원·선발`, `근무조건` 칸은 선배 인터뷰로만 채웁니다. 국제교류 노트는 `frames.json`의 `교환` 틀, 현장실습 노트는 `인턴` 틀을 씁니다.

### evidence.json (시트에서 만드는 근거 문단)

`reports.json`의 칸 하나, `internships.json`의 `후기` **문장** 하나가 근거 한 건입니다(귀국보고서 3,360건 + 현장실습후기 1,438문장 = 4,798건).

| 키 | 뜻 |
|---|---|
| id | 근거 번호(예: `R03-1-1`). 함수 응답의 `sourceId` |
| docType | `귀국보고서` · `현장실습후기` · `인터뷰` |
| 학번 · 학년도 · 학기 | 원래 시트 값 그대로(학기는 코드 숫자) |
| 프로그램명 | `programs.json`의 이름 |
| 문항 | 원래 시트 헤더 글자 그대로(예: `2-4. 기숙사 정보`, `후기`) |
| 문단 | (현장실습후기만) 원래 후기 안 문단 번호 — 추적용 |
| 칸 | `frames.json`의 칸 이름(현장실습후기는 작업 50 전까지 빈 값) |
| text | 귀국보고서는 문항 답 전체, 현장실습후기는 문장 하나 |

함수 응답의 `studentId`, `withId`, `to`는 모두 `colreg_no` 값입니다.

### usage-log.json (사용 로그 시드 — 시트가 아니라 `tools/make_usage_log.py`가 생성, 작업 65)

관리자 콘솔 집계(작업 66)의 재료입니다. 같은 seed(`20261120`)면 결과가 한 글자도 같습니다. 모든 문장은 템플릿 생성이고 실제 학생·후기 문장은 없습니다. 직원 계정과 시연 인물(H0143·H0469·H0745)은 넣지 않습니다. 점검: `python tools/make_usage_log.py --check`.

| 키 | 건수 | 한 행 |
|---|---|---|
| meta | — | `seed` · `기간`(2025-09-01~2026-11-30) · `건수` |
| questions | 1,200 | `id`(UQ-0001) · `at` · `colreg_no` · `crs_nm` · `regst_grad` · `프로그램명`(없으면 null) · `분야` · `칸` · `status`(ok·hold·official) · `질문` · `근거수` · `noteId`(null) · `운영부서코드`(없으면 null = '분류 안 됨') |
| interviews | 40 | `id`(UI-001) · `at` · `colreg_no`(그 프로그램 이수자) · `프로그램명` · `분야` · `문장수` · `후배질문답` |
| consents | 32 | `id`(UC-001) · `at` · `interviewId` · `colreg_no` · `프로그램명` · `공개문장수` · `제외문장수` |
| reports | 12 | `id`(UR-001) · `at` · `colreg_no`(신고자) · `프로그램명` · `lineId`(L-근거id) · `sourceId` · `사유` · `status`(숨김 중·공식 안내 연결됨·복구) |
| requests | 60 | `id`(UM-001) · `at` · `from`(미이수자) · `to`(이수자) · `프로그램명` · `status`(accepted 38·declined·pending) |

- `questions` 행은 서버가 시연 중 쌓는 `runtime/questions.json`(`add_question`)과 같은 모양에 `분야`·`근거수`를 더한 것입니다. 집계 때 둘을 합칩니다.
- 상태는 askBoo 규칙과 같습니다: 규정 표현(평점·장학금·몇 학점·선발 인원/기준·휴학·등록금·초과학기·인정 신청)이면 official, 근거가 있으면 ok, 없으면 hold(노트 없는 프로그램·보고서에 칸이 없는 주제·인턴 근무조건).
- 비율: hold 28%(336건), official 120건 = '학점·장학·선발'이 든 질문의 60%. 분야 몫은 국제교류 55·현장실습 20·비교과 15·분류 안 됨 10%이고, 분야 안에서는 이수 인원에 비례합니다(분야를 가리지 않고 비례하면 비교과가 76%가 되어 보류율 28%를 맞출 수 없음). 시연 프로그램 마르부르크필립스대학교는 ×6 가중으로 질문 1위입니다.

## 공통 규칙

| 규칙 | 내용 |
|---|---|
| 함수 | 모두 `async`이고 JSON 객체를 돌려준다 |
| 실패 | `{ "error": "사람이 읽을 메시지" }`. 화면은 `res.error`가 있으면 안내 문구를 보여 준다 |
| 학기 표기 | `2025-1`, `2025-2`, `2025-여름`, `2025-겨울` |
| 사람 표시 | 학번은 화면에 보이지 않는다. 다른 사람은 서버가 자동 생성한 `nickname`으로만 표시한다(닮은 선배 카드, 익명 쪽지창). 시트·프로필에는 닉네임이 없다. 형식은 `독일어과 선배 A`(학과 + 선배 + 영문 대문자, 학번·입학년도 없음), 보는 사람마다 만난 순서로 A, B, C…. 쪽지를 보낸 사람은 선배에게 `용감한 수달`(형용사 + 동물, 대화마다 새로, 학과 없음)로만 보인다 |
| 로그인 정보 | 화면이 `sessionStorage`의 `"me"`에 저장한다. 함수는 따로 받지 않는다 |
| docType | `귀국보고서` · `현장실습후기` · `인터뷰` |

## 함수 15개

| 함수 | 보내는 값 |
|---|---|
| login(id, pw) | `{id, pw}` |
| getMe() | 없음 |
| askBoo(question) | `{question}` |
| interviewNext(program, answers) | `{program, answers:[{section, question, answer}]}` |
| summarizeInterview(program, transcript) | `{program, transcript:[{section, question, answer}]}` |
| saveConsent(draftId, edits) | `{draftId, edits:{removed:[lineId], changed:[{lineId, text}]}, consent:true}` |
| listNotes(filter) | `{filter:{type?, q?}}` (type: 교환·파견·인턴·비교과) |
| getNote(id) | `{id}` |
| recommendSeniors(noteId) | `{noteId}` |
| checkMessage(text) | `{text}` |
| previewNickname(to) | `{to}` (쪽지 요청 시트를 열 때, 이 대화에서 쓸 내 닉네임) |
| sendMessage(to, text) | `{to, text}` (to는 상대 studentId) |
| getMessages() | 없음 |
| respondRequest(threadId, accept) | `{threadId, accept}` (받은 선배의 수락·거절) |
| getInbox() | 없음 |
| reportStatement(lineId, reason) | `{lineId, reason?}` |
| getDeptReport(dept) | `{dept}` (직원 전용) |

## 응답 모양

### login

| 필드 | 형식 | 뜻 |
|---|---|---|
| ok | 참/거짓 | 로그인 성공 여부 |
| user.colreg_no | 글자 | 학번(직원은 아이디) |
| user.token | 글자 | 로그인 토큰(24시간). `data.js`가 `me`에 저장하고 요청마다 헤더 `X-Token`으로 보낸다 |
| user.status | 글자 | `colreg_no`가 `staff`로 시작하면 `직원`, 아니면 `학생` — 서버가 정함 |
| user.부서명 | 글자 | 직원만. 총괄 관리자는 `전체` |
| user.부서코드 | 글자 | 부서 담당자만(예: `D04`) |
| user.권한 | 글자 | 직원만. `총괄`(전 부서, 리포트 설정·발행) 또는 `부서`(자기 부서만, 받은 리포트 확인) |
| reason | 글자 | 실패일 때만. 안내 문구 |

### getMe

가상학생 한 줄(`students.json` 키 그대로, `번호`·`비번` 제외)에 아래를 더합니다.

| 필드 | 형식 | 뜻 |
|---|---|---|
| 비교과이수내역 | 목록 | `extracurricular.json`의 내 행들(키 그대로, `번호`·`가상학번` 제외) |
| 귀국보고서 | 목록 | 내 귀국보고서의 `학년도` `학기` `국가` `대학명` |
| 현장실습후기 | 목록 | 내 현장실습후기의 `학년도` `학기` `업체명` `직군` |

선배·후배 구분 필드는 없습니다. 어떤 프로그램에 답할 수 있는지는 위 이수 기록으로 정해집니다.

### askBoo

| 필드 | 형식 | 뜻 |
|---|---|---|
| status | 글자 | `ok`(근거 있음), `hold`(근거 없음), `official`(규정 질문, 공식 안내로 연결) |
| lines[].text / sourceId / lineId | 글자 | 답변 문장과 출처, 문장 번호 |
| lines[].fallback | 참/거짓 | AI 문장이 검증에 걸려 근거 원문을 그대로 보여 준 줄이면 true. 없으면 거짓 |
| sources | 객체 | sourceId별 `{docType, program, semester}` |
| noteId | 글자 | `ok`일 때. 관련 노트 |
| suggestSenior | 참/거짓 | 닮은 선배 추천을 권할지 |
| questionId | 글자 | `hold`·`official`일 때. 질문함에 자동 저장된 질문 번호 |
| officialUrl | 글자 | `official`일 때. 담당 부서의 공식 안내 주소 |
| message | 글자 | `hold`·`official`일 때. 안내 문구 |

### interviewNext

| 필드 | 형식 | 뜻 |
|---|---|---|
| done | 참/거짓 | 인터뷰가 끝났는지 |
| section, question | 글자 | `done`이 false일 때. 다음 질문 한 개 |
| progress.filled / total | 숫자 | 채운 칸 수 / 전체 칸 수 |

### summarizeInterview

| 필드 | 형식 | 뜻 |
|---|---|---|
| draftId | 글자 | 초안 번호 |
| program | 글자 | 프로그램 이름 |
| myNote.sections[].name | 글자 | 내 경험 노트(1인칭, 나만 봄)의 칸 이름 |
| myNote.sections[].lines[].text | 글자 | 문장 |
| publicDraft.sections[].lines[].lineId / text | 글자 | 공개용 초안 문장. 선배가 고치고 동의해야 공개 |
| publicDraft.sections[].lines[].match | 참/거짓 | AI 원문 일치 검사. false면 "원문과 다를 수 있어요" 표시 |
| publicDraft.sections[].lines[].identifying | 참/거짓 | 코드가 찾은 본인 식별 문장. true면 동의 시트에서 기본 꺼짐 |
| saved / myNoteId | 참/거짓 · 글자 | 요약과 동시에 내 경험노트로 저장됐는지, 그 번호(저장은 기본, 공유는 선택) |

### saveConsent

| 필드 | 형식 | 뜻 |
|---|---|---|
| ok | 참/거짓 | 저장 성공 여부 |
| noteId | 글자 | 반영된 노트 |
| added | 숫자 | 추가된 문장 수 |

### listNotes

| 필드 | 형식 | 뜻 |
|---|---|---|
| notes[].id / program / type | 글자 | 노트 번호, 프로그램, 종류 |
| notes[].oneLine / forWhom | 글자 | 한 줄 요약, 추천 대상 |
| notes[].evidenceCount | 숫자 | 근거 개수 |
| notes[].lastSemester | 글자 | 가장 최근 학기 |
| notes[].satisfaction | 숫자 | 만족도 |

### getNote

칸 순서와 이름은 `data/frames.json`을 따릅니다. 빈 칸도 `lines: []`로 보냅니다.

| 필드 | 형식 | 뜻 |
|---|---|---|
| id / program / type / oneLine / forWhom | 글자 | listNotes와 같음 |
| evidenceCount / lastSemester / satisfaction | 숫자·글자 | listNotes와 같음 |
| officialUrl | 글자 | 공식 안내 주소. 프로그램의 `운영부서코드`로 `departments.json`의 `공식안내URL`을 찾아 넣음(프로그램 목록에는 URL 없음) |
| sections[].name | 글자 | 칸 이름 |
| sections[].interviewOnly | 참/거짓 | true면 선배 인터뷰로만 채워지는 칸 |
| sections[].lines[].text / sourceId / lineId | 글자 | 문장, 출처, 문장 번호 |
| sections[].lines[].official | 참/거짓 | true면 규정성 진술. "개인 경험이에요" 표시와 `officialUrl` 링크를 붙인다 |
| sources | 객체 | sourceId별 `{docType, program, semester}` |

### recommendSeniors

| 필드 | 형식 | 뜻 |
|---|---|---|
| seniors[].studentId | 글자 | 선배 학번(화면에 보이지 않음) |
| seniors[].nickname | 글자 | 자동 생성 닉네임 |
| seniors[].score | 숫자 | 닮은 정도 점수 |
| seniors[].reasons | 글자 목록 | 점수 이유 |

### checkMessage

| 필드 | 형식 | 뜻 |
|---|---|---|
| ok | 참/거짓 | 보내도 되는지 |
| reason | 글자 | 막힌 이유: `연락처` · `학번` · `비방` |
| message | 글자 | 막혔을 때 안내 문구 |

### sendMessage

| 필드 | 형식 | 뜻 |
|---|---|---|
| ok | 참/거짓 | 전송 성공 여부 |
| threadId | 글자 | 대화 번호. 첫 메시지는 쪽지 신청이 된다 |
| myNickname | 글자 | 이 대화에서 선배에게 보이는 내 이름(형용사 + 동물, 대화마다 새로) |
| at | 글자 | 보낸 시각 |

### previewNickname

| 필드 | 형식 | 뜻 |
|---|---|---|
| myNickname | 글자 | 요청 시트에 「선배에게는 '○○'로 보여요」로 보여 줄 값. sendMessage가 같은 값을 쓴다 |

### getMessages

| 필드 | 형식 | 뜻 |
|---|---|---|
| threads[].threadId / withId | 글자 | 대화 번호, 상대 학번(화면에 표시 안 함) |
| threads[].role | 글자 | 내 역할: `asker`(보낸 사람) · `senior`(받은 선배) |
| threads[].nickname | 글자 | 상대 이름. asker에게는 `독일어과 선배 A`, senior에게는 `용감한 수달` |
| threads[].myNickname | 글자 | asker일 때 선배에게 보이는 내 이름 |
| threads[].askerInfo.학년 / 관심 | 숫자 · 목록 | senior에게만. 보낸 사람의 학년과 관심 경험(학과 없음) |
| threads[].accepted | 참/거짓 | 상대가 수락했는지 |
| threads[].unread | 숫자 | 안 읽은 메시지 수 |
| threads[].messages[].from | 글자 | `me` 또는 `them` |
| threads[].messages[].text / at | 글자 | 내용, 시각 |

### getInbox

| 필드 | 형식 | 뜻 |
|---|---|---|
| myNotes[].id / program | 글자 | 내 경험 노트 |
| questions[].questionId / text | 글자 | 질문 번호, 내용 |
| questions[].status | 글자 | `waiting` 또는 `answered` |
| questions[].askedAt / noteId | 글자 | 질문 시각(waiting) / 답이 된 노트(answered) |
| scraps[].noteId / program | 글자 | 스크랩한 노트 |
| alerts[].text / noteId / at | 글자 | 알림 문구, 관련 노트, 시각 |

### reportStatement

| 필드 | 형식 | 뜻 |
|---|---|---|
| ok | 참/거짓 | 신고 접수 여부 |
| hidden | 참/거짓 | 신고된 문장을 즉시 숨겼는지 |

### getDeptReport

| 필드 | 형식 | 뜻 |
|---|---|---|
| dept / period | 글자 | 부서, 기간(예: 2026-11) |
| programs[].program | 글자 | 프로그램 이름 |
| programs[].questions / unanswered / reports | 숫자 | 질문 수, 미해결 수, 신고 수 |
| unansweredQuestions[].text / count | 글자·숫자 | 미해결 질문과 횟수 |
| reportedStatements | 숫자 | 신고된 문장 수 |
| summary | 글자 | AI가 쓴 한 단락 요약 |

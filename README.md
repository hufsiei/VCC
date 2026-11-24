# VCC

외대人사이드 본선 저장소. 함수·응답 명세는 [docs/spec-v1.md](docs/spec-v1.md)를 따릅니다.

> **가상 데이터 PoC입니다. 실제 학생 정보가 없습니다.** `data/`의 학생(H0001~H1000)·귀국보고서·실습 후기·질문 로그는 모두 생성한 가상 데이터이고, 이름 열은 아예 없습니다. 실제 학번(9자리)·실명·연락처는 어디에도 올리지 않습니다. 자세한 것은 [data/README.md](data/README.md).

## 접속 주소

- 로컬: 저장소 폴더에서 `python functions/serve_screens.py` 실행 후 `http://localhost:8000/screens/login/` (이 PC에서만 열림)
- 미리 개발 서버(미리 PC만): `functions/local_fn.py` 실행 후 `http://localhost:8787`
- 공개 주소(GitHub Pages, `main` 루트): <https://hufsiei.github.io/VCC/screens/login/>
  - 저장소 루트는 `https://hufsiei.github.io/VCC/`이고, 각 화면은 그 아래 `screens/<화면>/`입니다.
  - 지금은 `USE_MOCK=true`(mock 데이터)로 배포합니다. 서버 함수 호출 확인은 작업 47 이후입니다.
  - 서버 함수(`functions/cloud/`)의 CORS는 `https://hufsiei.github.io`와 로컬 `http://localhost:8000`·`http://127.0.0.1:8000`만 허용합니다. 다른 주소를 더하려면 함수의 `ALLOW_ORIGIN` 기본 파라미터(쉼표 구분)를 씁니다.
  - 저장소가 공개라서 `data/`·`common/` 등 올린 파일은 누구나 볼 수 있습니다. 가상 데이터만 올리고, 키는 `.env`(커밋 금지)와 NCP 콘솔 기본 파라미터에만 둡니다. `.env`에 넣을 항목은 [.env.example](.env.example)(AI 키, 로그인 비번 표 `VCC_LOGIN_PW`)를 보세요.

## 가상 계정

| 역할 | 아이디 | 설명 |
|---|---|---|
| 후배1 | H0143 | 독일어과 2학년, 이중전공 경영학, 해외경험·현장실습 없음, 비교과 Jump Start 프로그램·ISO 국제학생회 BUDDY·직무탐색 집중교육 이수. 질문하는 사람 |
| 선배1 | H0469 | 독일어과 4학년, 이중전공 경영학, 2025-1 독일 마르부르크필립스대학교 학과 파견, 후배1과 같은 비교과(직무탐색 집중교육) 이수. 닮은 선배 1위 14점 |
| 선배2 | H0241 | 독일어과 3학년, 이중전공 경영학, 2026-1 같은 대학 학과 파견. 공통 비교과 없음. 닮은 선배 2위 12점 |
| 직원 | staff01 | 부서 리포트용 직원 계정 |

모두 가상 계정입니다. 학생·직원 계정 모두 `가상데이터_1000명.xlsx` 가상학생 시트의 행입니다(직원은 `colreg_no`가 `staff`로 시작).

## 실행법

```
cd C:\dev\VCC
python functions/serve_screens.py
```

파일을 더블클릭해 열면 동작하지 않습니다. 반드시 위 서버로 `localhost:8000`에서 엽니다.
`python -m http.server 8000`은 쓰지 않습니다(11/24). 저장소 전체를 같은 와이파이의 다른 기기에도 열어 `.env`(키)·`functions/logs`·`data/runtime`이 주소로 보입니다. `serve_screens.py`는 이 PC(127.0.0.1)에서만 열리고 `screens/`·`common/`·`assets/`·`data/`(runtime 제외)만 보여 줍니다. 포트를 바꾸려면 끝에 번호(`… serve_screens.py 8001`).
기본은 mock 데이터(`common/mock-data.json`)로 동작합니다(`common/data.js`의 `USE_MOCK`).
함수마다 따로 서버로 보내려면 `data.js`의 `SERVER_FNS`(또는 되돌릴 때 `MOCK_FNS`)에 함수 이름을 적습니다.
코드를 고치지 않고 확인할 때는 localhost에서 주소 끝에 `?server=all` 또는 `?server=sendMessage,getMessages`를 붙입니다. 그 탭에서만 기억하고(두 창 시연), `?server=`로 해제합니다. 서버로 가는 함수가 하나라도 있으면 로그인도 서버로 가므로 다시 로그인합니다. 서버(`functions/local_fn.py`)는 미리 PC에서만 켭니다.

## push 전 검사

push할 때 `.githooks/pre-push`가 `.py` 문법 검사와 `functions/test_*.py` 시험(약 5초)을 돌리고, 하나라도 실패하면 push를 막습니다. 오류를 고치지는 않고 어디가 실패했는지만 보여 줍니다.

- 켜기(PC마다 한 번, 저장소 폴더에서): `git config core.hooksPath .githooks`
- 검사만 따로 돌려 보기: `python -X utf8 .githooks/pre_push_check.py`
- 급할 때만 건너뛰기: `git push --no-verify`

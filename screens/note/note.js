// 해봤노트 화면 (작업 23) — 목록 + 노트 커버(1단계) / 노트 상세(2단계, ?id=노트번호)
// 기준: docs/design-rules.md 7-③·5-2·5-5·6-1~6-5·8절(해봤노트 상세), docs/spec-v1.md 4장 listNotes·getNote·scrapNote·reportStatement
// 규칙: 데이터는 common/data.js 함수로만, 화면 글은 textContent로만(innerHTML 금지), 색은 style.css 변수만.

import { currentUser, listNotes, getNote, scrapNote, saveQuestion, reportStatement } from "../../common/data.js";

// ---------------------------------------------------------------------------
// 0. 로그인 확인
// ---------------------------------------------------------------------------

const me = currentUser();
if (!me) location.replace("../login/");
if (me && me.status === "직원") document.getElementById("consoleBtn").hidden = false;

// 노트 종류(type) → 분야(3-3). 교환·파견은 국제교류, 인턴은 현장실습
const CATEGORY = { 교환: "global", 파견: "global", 인턴: "practice", 비교과: "extra" };
const CATEGORY_NAME = { global: "국제교류", practice: "현장실습", extra: "비교과" };
// 띠의 세부 분류: 종류 + 국가(spec [11/22] country). country가 null이면 종류만(비교과는 분야 태그와 같아 비움)
const KIND_NAME = { 교환: "교환학생", 파견: "파견", 인턴: "인턴", 비교과: "" };
const DASH = "–";
const LEARN_SECTION = "배운점";
// 출처 종류 표기(인터BOO와 같음). 근거 블록 머리줄의 보고서 이름은 노트 종류에 따라
const DOC_LABEL = { 귀국보고서: "보고서", 현장실습후기: "현장실습후기", 인터뷰: "선배 인터뷰" };
// 오래된 근거(6-1 v4.3): 칸의 근거가 모두 2년 넘은 연도
const OLD_YEARS = 2;

// 「질문함에 담기」(spec [11/22] saveQuestion): 그 노트의 한 칸을 질문함에 넣는다.
// 성공하면 응답 message를 토스트로, 버튼은 「질문함에 담았어요」(비활성). 같은 칸은 서버가 하나만 만든다(멱등).
// 탭을 바꿨다 돌아와도 담은 상태가 남게 노트·칸별로 기억한다.
const savedSections = new Set();
const sectionKey = (noteId, section) => `${noteId}|${section}`;

function setSaved(btn) {
  btn.textContent = "질문함에 담았어요";
  btn.disabled = true;
}

function askBoxButton(noteId, section) {
  const btn = el("button", { className: "btn btn--outline", text: "질문함에 담기", attrs: { type: "button" } });
  if (savedSections.has(sectionKey(noteId, section))) {
    setSaved(btn);
    return btn;
  }
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try {
      const res = await saveQuestion(noteId, section);
      if (!res || !res.ok) throw new Error((res && res.error) || "질문함에 담지 못했어요");
      savedSections.add(sectionKey(noteId, section));
      setSaved(btn);
      toast(res.message || "질문함에 담았어요");
    } catch (err) {
      console.error(err);
      btn.disabled = false;
      toast(err.message || "질문함에 담지 못했어요", "circle-alert");
    }
  });
  return btn;
}

function kindText(note) {
  const kind = KIND_NAME[note.type] ?? "";
  return note.country ? [kind, note.country].filter(Boolean).join(" · ") : kind;
}

// ---------------------------------------------------------------------------
// 1. 작은 도우미 — 요소 만들기(글은 textContent로만), 아이콘, 토스트, 학기
// ---------------------------------------------------------------------------

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  const { className, text, attrs } = props;
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (attrs) for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  for (const child of [].concat(children)) if (child !== null && child !== undefined && child !== false) node.append(child);
  return node;
}
const icon = (name) => el("i", { className: "icon", attrs: { "data-lucide": name } });
const drawIcons = () => window.lucide && window.lucide.createIcons({ attrs: { "stroke-width": 1.75 } });
const statusLabel = (kind, iconName, text) =>
  el("span", { className: `status-label status-label--${kind}` }, [iconName ? icon(iconName) : null, el("span", { text })]);

// 토스트(5-10): 3초
function toast(text, iconName = "check") {
  const host = document.getElementById("toastHost");
  host.replaceChildren(el("span", { className: "toast" }, [icon(iconName), el("span", { text })]));
  drawIcons();
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => host.replaceChildren(), 3000);
}

// 빈 값(null·undefined·빈 문자열)은 "–"
const orDash = (v) => (v === null || v === undefined || String(v).trim() === "" ? DASH : String(v));

// 학기 표기(1-2절): "2026-1" → "2026-1학기", "2025-여름" → "2025 하계방학", "2025-겨울" → "2025 동계방학"
function semesterText(s) {
  if (!s) return DASH;
  const [year, term] = String(s).split("-");
  if (term === "1" || term === "2") return `${year}-${term}학기`;
  if (term === "여름") return `${year} 하계방학`;
  if (term === "겨울") return `${year} 동계방학`;
  return String(s);
}
const SEM_ORDER = { 1: 1, 여름: 2, 2: 3, 겨울: 4 };
const semesterKey = (sem) => {
  const [year, part] = String(sem || "").split("-");
  return Number(year || 0) * 10 + (SEM_ORDER[part] || 0);
};
const yearOf = (sem) => String(sem || DASH).split("-")[0]; // 출처 칩은 연도만(v4.3)

// 안전한 링크만(공식 안내 URL): http·https만
function safeUrl(url) {
  try {
    const u = new URL(String(url || ""), location.href);
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// 2. 노트 커버 — 공통 부품 .note-card(7-③ 커버 5항목). 목록은 본문이 상세 링크, 상세에서는 링크 없음
// ---------------------------------------------------------------------------

// 스크랩 버튼(5-5 띠 오른쪽). 상태는 서버 응답의 scrapped로만 바꾼다(spec [11/22] scrapNote)
function setScrapState(btn, on) {
  btn.setAttribute("aria-pressed", String(on));
  btn.setAttribute("aria-label", on ? "스크랩 취소" : "스크랩");
}

function scrapButton(note) {
  const btn = el("button", { className: "icon-btn", attrs: { type: "button" } }, [icon("bookmark")]);
  setScrapState(btn, note.scrapped === true);
  btn.addEventListener("click", async () => {
    const want = btn.getAttribute("aria-pressed") !== "true";
    btn.disabled = true;
    try {
      const res = await scrapNote(note.id, want);
      if (!res || !res.ok) throw new Error((res && res.error) || "스크랩 실패");
      note.scrapped = res.scrapped === true;
      // 목록과 상세가 같은 노트를 보고 있으면 둘 다 맞춘다
      const inList = allNotes.find((n) => n.id === note.id);
      if (inList) inList.scrapped = note.scrapped;
      setScrapState(btn, note.scrapped);
      toast(note.scrapped ? "내 보관함 스크랩에 담았어요" : "스크랩을 해제했어요");
    } catch (err) {
      console.error(err);
      toast("스크랩하지 못했어요. 다시 시도해 주세요", "circle-alert");
    } finally {
      btn.disabled = false;
    }
  });
  return btn;
}

function noteCover(note, { link = true } = {}) {
  const cat = CATEGORY[note.type] || "global";

  const band = el("div", { className: "note-card__band" }, [
    el("span", { className: "category-tag", text: CATEGORY_NAME[cat] }),
    el("span", { className: "note-card__kind", text: kindText(note) }),
    scrapButton(note),
  ]);

  // 메타 줄: 근거 N건 · 최근 학기 · ★ 만족도 (비교과는 · 이수 N명 추가)
  const count = Number.isFinite(note.evidenceCount) ? note.evidenceCount : 0;
  const dot = () => el("span", { text: "·", attrs: { "aria-hidden": "true" } });
  const star = el("span", { className: "note-card__star", attrs: { "aria-label": `만족도 ${orDash(note.satisfaction)}` } },
    [icon("star"), el("span", { text: orDash(note.satisfaction) })]);
  const meta = el("p", { className: "note-card__meta" }, [
    el("span", { text: `근거 ${count}건` }), dot(),
    el("span", { text: `최근 ${semesterText(note.lastSemester)}` }), dot(),
    star,
  ]);
  if (note.type === "비교과") {
    const done = note.completedCount === null || note.completedCount === undefined ? DASH : `${note.completedCount}명`;
    meta.append(dot(), el("span", { text: `이수 ${done}` }));
  }

  const bodyChildren = [
    el(link ? "h3" : "h1", { className: "note-card__title", text: orDash(note.program) }),
    el("p", { className: "note-card__summary", text: orDash(note.oneLine) }),
    el("p", { className: "note-card__target", text: orDash(note.forWhom) }),
    meta,
  ];
  let body;
  if (link) {
    body = el("a", { className: "note-card__body", attrs: { href: `?id=${encodeURIComponent(note.id)}` } }, bodyChildren);
    body.addEventListener("click", (e) => {
      e.preventDefault();
      openDetail(note.id);
    });
  } else {
    body = el("div", { className: "note-card__body" }, bodyChildren);
  }

  return el("article", { className: `note-card cat-${cat}` }, [band, body]);
}

// ---------------------------------------------------------------------------
// 3. 목록 — 로딩(6-3) · 빈 화면(6-4) · 오류(6-5)
// ---------------------------------------------------------------------------

const listEl = document.getElementById("noteList");
const countEl = document.getElementById("noteCount");
let allNotes = [];
let currentCat = "";
let currentQuery = ""; // 검색창 글자(그대로) — 거를 때는 norm()으로
let loaded = false;
let listRequested = false;

function errorBox(onRetry) {
  const retry = el("button", { className: "btn btn--outline", text: "다시 시도", attrs: { type: "button" } });
  retry.addEventListener("click", onRetry);
  return el("div", { className: "state-box" }, [
    statusLabel("error", "circle-alert", "불러오지 못했어요"),
    el("p", { className: "sub", text: "잠시 뒤 다시 시도해 주세요." }),
    retry,
  ]);
}

// 검색(7-③, 11/24): 띄어쓰기·대소문자 무시하고 프로그램명·한 줄 요약·추천 대상·나라·기관유형·종류·분야 글자에 들어 있으면 남긴다.
// 서버 listNotes q와 같은 방식이지만, 분야 필터처럼 전체를 한 번 받아 화면에서 거른다(글자마다 서버를 부르지 않음, mock에서도 동작).
// 하나도 안 맞을 때만 서버에 묻는다(별칭·오타, 아래 serverSearch).
// 검색어를 굵게·밑줄로 강조하지 않는다(디자인 규칙 12절).
const norm = (s) => String(s || "").replace(/\s+/g, "").toLowerCase();
function matchesQuery(n, q) {
  if (!q) return true;
  const words = [n.program, n.oneLine, n.forWhom, n.country, n.kind, n.type, KIND_NAME[n.type], CATEGORY_NAME[CATEGORY[n.type]]];
  return words.some((w) => norm(w).includes(q));
}

// 별칭·오타(작업 121): 카드에는 별칭이 없으니, 화면에서 0개이고 검색어에 한글이 2글자 이상이면 잠시 뒤
// listNotes({ q })를 한 번 부른다. 결과는 검색어별로 담아 두고 지금 검색어의 것만 그린다(늦은 응답이 덮지 않게).
const SERVER_SEARCH_DELAY = 300;
const serverHits = new Map(); // 검색어(norm) → 서버가 맞다고 한 노트 id Set
let serverTimer = 0;

const needsServer = (q) => (q.match(/[가-힣]/g) || []).length >= 2 && !allNotes.some((n) => matchesQuery(n, q));

function serverSearch(q, raw) {
  clearTimeout(serverTimer);
  serverTimer = setTimeout(async () => {
    let ids = [];
    let failed = false;
    try {
      const res = await listNotes({ q: raw });
      const notes = Array.isArray(res && res.notes) ? res.notes : [];
      // mock은 q를 무시하고 전체를 준다 — 전체 목록과 같으면 맞는 것이 없는 것
      if (notes.length < allNotes.length) ids = notes.map((n) => n.id);
    } catch (err) {
      console.error(err);
      failed = true;
    }
    serverHits.set(q, new Set(ids));
    if (norm(currentQuery) === q) renderList();
    if (failed) serverHits.delete(q); // 실패는 담아 두지 않는다(다시 치면 다시 묻는다)
  }, SERVER_SEARCH_DELAY);
}

// [11/23 주제별 묶기] spec listNotes groups: 분야·검색으로 거른 뒤, 나라·기관 유형으로 거르기 전 카드로 센다
// (칩 하나를 눌러도 다른 칩이 그대로 보이게). 많은 순, 같으면 가나다순. 값이 null인 카드는 세지 않는다.
// 목록을 화면에서 거르므로(국제교류 = 교환 + 파견) 칩 수도 지금 받은 카드로 센다 — 보이는 카드 수와 늘 맞는다(9절)
// [Q-101] 국제교류는 권역 칩 → 그 권역의 나라 칩 2단, 현장실습은 기관 유형 상위 5개 + 「그 외 N곳」.
const GROUP_BY_CAT = { global: { key: "country" }, practice: { key: "kind" } }; // 칩으로 거르는 카드 값
// 권역 표: functions/askboo.py REGIONS(#375)와 같은 묶음. 칩은 한 나라가 한 곳에만 들어가야 해서
// 「동남아시아」는 따로 두지 않고 「아시아」에 넣는다. 겹치는 나라(몽골 등)는 앞 권역에 든다(askboo와 같은 순서).
const REGIONS = [
  ["유럽", ["프랑스", "이탈리아", "독일", "포르투갈", "스페인", "스웨덴", "벨기에", "네덜란드", "덴마크", "아일랜드",
    "체코", "영국", "오스트리아", "스위스", "핀란드", "노르웨이", "폴란드", "헝가리", "그리스", "루마니아",
    "불가리아", "세르비아", "크로아티아", "슬로바키아", "슬로베니아", "우크라이나", "튀르키예", "터키"]],
  ["러시아·중앙아시아", ["러시아", "카자흐스탄", "우즈베키스탄", "키르기스스탄", "몽골"]],
  ["아시아", ["일본", "중국", "대만", "홍콩", "싱가포르", "베트남", "태국", "인도네시아", "말레이시아", "필리핀", "인도",
    "미얀마", "캄보디아", "라오스"]],
  ["북미", ["미국", "캐나다"]],
  ["중남미", ["브라질", "멕시코", "아르헨티나", "칠레", "콜롬비아", "페루", "쿠바"]],
  ["중동", ["아랍에미리트", "사우디아라비아", "이란", "이스라엘", "요르단", "이집트", "카타르"]],
  ["아프리카", ["남아프리카공화국", "케냐", "탄자니아", "나이지리아", "모로코", "에티오피아"]],
  ["오세아니아", ["호주", "뉴질랜드"]],
];
const OTHER_REGION = "그 외 지역"; // 표에 없는 나라도 칩에서 사라지지 않게
const regionOf = (country) => (REGIONS.find(([, nations]) => nations.includes(country)) || [OTHER_REGION])[0];
const KIND_TOP = 5; // 접었을 때 보이는 기관 유형 수

const groupEl = document.getElementById("groupChips");
// 2단(권역 안 나라) 줄 — 1단 줄 바로 아래
const subGroupEl = el("div", { className: "filter-row", attrs: { role: "group", "aria-label": "나라 필터" } });
subGroupEl.hidden = true;
groupEl.after(subGroupEl);
let currentRegion = ""; // 국제교류에서 고른 권역(없으면 "")
let currentGroup = ""; // 고른 나라·기관 유형(없으면 "")
let kindsOpen = false; // 「그 외 N곳」을 펼쳤는지

// 값별 노트 수: 많은 순, 같으면 가나다순
function countBy(notes, valueOf) {
  const counts = new Map();
  for (const n of notes) {
    const v = valueOf(n);
    if (v) counts.set(v, (counts.get(v) || 0) + 1);
  }
  return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ko"));
}

function filterChip(text, pressed, onClick) {
  const b = el("button", { className: "choice-chip", text, attrs: { type: "button", "aria-pressed": String(pressed) } });
  b.addEventListener("click", onClick);
  return b;
}

// 칩을 다시 그려도 키보드 포커스는 같은 글자의 칩에 남긴다
function fillRow(row, chips) {
  const focused = row.contains(document.activeElement) ? document.activeElement.textContent : null;
  row.hidden = chips.length === 0;
  row.replaceChildren(...chips);
  if (focused !== null) {
    const same = chips.find((c) => c.textContent === focused);
    if (same) same.focus();
  }
}

function hideGroupChips() {
  groupEl.hidden = true;
  subGroupEl.hidden = true;
}

const inRegion = (notes, region) => notes.filter((n) => n.country && regionOf(n.country) === region);

// 고른 값(칩)에 맞는 카드만 남긴다
function applyGroup(base) {
  const g = GROUP_BY_CAT[currentCat];
  if (!g) return base;
  if (currentGroup) return base.filter((n) => n[g.key] === currentGroup);
  if (currentRegion) return inRegion(base, currentRegion);
  return base;
}

// 국제교류: 1단 권역, 권역을 고르면 2단에 그 권역의 나라
function renderRegionChips(base) {
  // 나라만 있고 권역이 없는 상태(주소로 들어온 경우)는 그 나라의 권역을 켠다
  if (currentGroup && !currentRegion) currentRegion = regionOf(currentGroup);
  const regions = countBy(base, (n) => (n.country ? regionOf(n.country) : null));
  if (currentRegion && !regions.some(([name]) => name === currentRegion)) currentRegion = ""; // 검색으로 사라진 칩은 풀어 준다
  const nations = currentRegion ? countBy(inRegion(base, currentRegion), (n) => n.country) : [];
  if (currentGroup && !nations.some(([name]) => name === currentGroup)) currentGroup = "";

  // 칩 줄이 바뀌어 누른 칩이 사라지므로 포커스는 새 줄의 해당 칩으로 옮긴다
  const pickRegion = (value, focusText) => {
    currentRegion = value;
    currentGroup = "";
    renderList();
    const next = [...groupEl.children].find((c) => c.textContent.startsWith(focusText));
    if (next) next.focus();
  };
  const regionChip = (value, text) => filterChip(text, currentRegion === value, () => pickRegion(value, value || text));
  let chips = [];
  if (currentRegion) {
    // 권역을 고르면 1단 줄은 「유럽 ×」 한 칩으로 접는다. ×를 누르면 권역 목록으로
    const name = currentRegion;
    const picked = el("button", { className: "choice-chip", attrs: { type: "button", "aria-pressed": "true", "aria-label": `${name} 선택 해제` } },
      [el("span", { text: name }), icon("x")]);
    picked.addEventListener("click", () => pickRegion("", name));
    chips = [picked];
  } else if (regions.length) {
    chips = [regionChip("", "권역 전체"), ...regions.map(([name, count]) => regionChip(name, `${name} ${count}`))];
  }
  groupEl.setAttribute("aria-label", "권역 필터");
  fillRow(groupEl, chips);

  const nationChip = (value, text) => filterChip(text, currentGroup === value, () => {
    currentGroup = value;
    renderList();
  });
  fillRow(subGroupEl, nations.length ? [nationChip("", `${currentRegion} 전체`), ...nations.map(([name, count]) => nationChip(name, `${name} ${count}`))] : []);
}

// 현장실습: 노트 많은 순 상위 5개 + 「그 외 N곳」. 접힌 쪽에서 고른 유형은 접어도 보인다
function renderKindChips(base) {
  const kinds = countBy(base, (n) => n.kind);
  if (currentGroup && !kinds.some(([name]) => name === currentGroup)) currentGroup = "";
  const chip = (value, text) => filterChip(text, currentGroup === value, () => {
    currentGroup = value;
    renderList();
  });
  const folds = kinds.length > KIND_TOP + 1; // 하나만 남으면 접지 않는다
  const shown = !folds || kindsOpen ? kinds : kinds.filter(([name], i) => i < KIND_TOP || name === currentGroup);
  const chips = kinds.length ? [chip("", "기관 유형 전체"), ...shown.map(([name, count]) => chip(name, `${name} ${count}`))] : [];
  // 펼침 칩은 거르는 칩이 아니라 aria-pressed 대신 aria-expanded
  let more = null;
  if (folds && (kindsOpen || shown.length < kinds.length)) {
    const text = kindsOpen ? "접기" : `그 외 ${kinds.length - shown.length}곳`;
    more = el("button", { className: "choice-chip", attrs: { type: "button", "aria-expanded": String(kindsOpen) } },
      [el("span", { text }), icon(kindsOpen ? "chevron-up" : "chevron-down")]);
    more.addEventListener("click", () => {
      kindsOpen = !kindsOpen;
      renderList();
      const next = groupEl.querySelector("[aria-expanded]");
      if (next) next.focus();
    });
    chips.push(more);
  }
  groupEl.setAttribute("aria-label", "기관 유형 필터");
  fillRow(groupEl, chips);
}

function renderGroupChips(base) {
  if (currentCat !== "global") {
    currentRegion = "";
    subGroupEl.hidden = true;
    subGroupEl.replaceChildren();
  }
  if (currentCat === "global") renderRegionChips(base);
  else if (currentCat === "practice") renderKindChips(base);
  else {
    currentGroup = "";
    groupEl.hidden = true;
    groupEl.replaceChildren();
  }
}

// 목록의 필터·검색어를 주소에 남긴다(새로고침·링크로 다시 열어도 같은 목록). 다른 값(?server= 등)은 그대로 둔다
const FILTER_PARAMS = { cat: () => currentCat, region: () => currentRegion, group: () => currentGroup, q: () => currentQuery.trim() };
function syncUrl() {
  const url = new URL(location.href);
  if (url.searchParams.has("id")) return; // 상세 주소는 건드리지 않는다
  url.searchParams.delete("type"); // 처음 들어올 때의 ?type=은 cat으로 바꿔 남긴다
  for (const [key, value] of Object.entries(FILTER_PARAMS)) {
    if (value()) url.searchParams.set(key, value());
    else url.searchParams.delete(key);
  }
  if (url.href !== location.href) history.replaceState(history.state, "", url);
}

function skeletons() {
  return [0, 1, 2].map(() => el("div", { className: "skeleton note-skeleton", attrs: { "aria-hidden": "true" } }));
}

function renderList() {
  clearTimeout(serverTimer);
  const q = norm(currentQuery);
  let matches = (n) => matchesQuery(n, q);
  if (needsServer(q)) {
    const ids = serverHits.get(q);
    if (!ids) {
      // 서버 답을 기다리는 동안은 로딩(6-3). 고른 나라·기관 유형 칩은 풀지 않는다
      listEl.setAttribute("aria-busy", "true");
      countEl.textContent = "";
      hideGroupChips();
      syncUrl();
      listEl.replaceChildren(...skeletons());
      serverSearch(q, currentQuery.trim());
      return;
    }
    matches = (n) => ids.has(n.id);
  }
  listEl.setAttribute("aria-busy", "false");
  const base = allNotes.filter((n) => (!currentCat || CATEGORY[n.type] === currentCat) && matches(n));
  renderGroupChips(base);
  drawIcons(); // 「그 외 N곳」 칩의 화살표
  syncUrl();
  const notes = applyGroup(base);
  countEl.textContent = `노트 ${notes.length}개`;

  if (!notes.length && q) {
    // 검색 결과 없음(6-4): 이름을 바꿔 찾거나, 노트에 없는 것은 BOO에게 묻도록
    listEl.replaceChildren(el("div", { className: "state-box" }, [
      el("img", { className: "boo-illust", attrs: { src: "../../assets/boo-portrait.png", alt: "BOO" } }),
      el("p", { className: "state-box__title", text: `「${currentQuery.trim()}」에 맞는 해봤노트가 없어요` }),
      el("p", { className: "sub", text: "다른 이름으로 찾아보거나, BOO에게 물어보세요." }),
      el("a", { className: "btn btn--secondary", text: "BOO에게 물어보기", attrs: { href: "../talk/?mode=ask" } }),
    ]));
    return;
  }
  if (!notes.length) {
    listEl.replaceChildren(el("div", { className: "state-box" }, [
      el("img", { className: "boo-illust", attrs: { src: "../../assets/boo-portrait.png", alt: "BOO" } }),
      el("p", { className: "state-box__title", text: "아직 이 분야의 해봤노트가 없어요" }),
      el("p", { className: "sub", text: "궁금한 점은 BOO에게 먼저 물어보세요." }),
      el("a", { className: "btn btn--secondary", text: "BOO에게 물어보기", attrs: { href: "../talk/" } }),
    ]));
    return;
  }
  listEl.replaceChildren(...notes.map((n) => noteCover(n)));
  drawIcons();
}

// 국제교류 = 교환 + 파견이라 서버 type 하나로 거를 수 없어서, 전체를 한 번 받아 화면에서 거른다
async function loadList() {
  listRequested = true;
  loaded = false;
  listEl.setAttribute("aria-busy", "true");
  countEl.textContent = "";
  listEl.replaceChildren(...skeletons());
  try {
    const res = await listNotes({});
    allNotes = Array.isArray(res && res.notes) ? res.notes : [];
    loaded = true;
    renderList();
  } catch (err) {
    console.error(err);
    listEl.setAttribute("aria-busy", "false");
    listEl.replaceChildren(errorBox(loadList));
    drawIcons();
  }
}

// 필터 칩 — 같은 화면 안 전환이라 하단 탭은 그대로(5-2)
document.getElementById("filters").addEventListener("click", (e) => {
  const chip = e.target.closest(".choice-chip");
  if (!chip) return;
  currentCat = chip.dataset.cat;
  currentRegion = ""; // 분야를 바꾸면 권역·나라·기관 유형 칩은 처음부터
  currentGroup = "";
  kindsOpen = false;
  for (const c of e.currentTarget.querySelectorAll(".choice-chip")) c.setAttribute("aria-pressed", String(c === chip));
  if (loaded) renderList(); // 불러오는 중이거나 오류면 그 화면을 그대로 둔다
  else syncUrl();
});

// 검색창 — 칠 때마다 바로 거른다(같은 화면 안 전환). Enter는 휴대폰 키보드만 내린다
const queryInput = document.getElementById("noteQuery");
const queryClear = document.getElementById("noteQueryClear");
function setQuery(value) {
  currentQuery = value;
  queryClear.hidden = value === "";
  if (loaded) renderList();
}
queryInput.addEventListener("input", () => setQuery(queryInput.value));
document.getElementById("noteSearch").addEventListener("submit", (e) => {
  e.preventDefault();
  queryInput.blur();
});
queryClear.addEventListener("click", () => {
  queryInput.value = "";
  setQuery("");
  queryInput.focus();
});

// ---------------------------------------------------------------------------
// 4. 근거/출처 블록 — 6-1 · 6-2 (칸마다)
// ---------------------------------------------------------------------------

// button: 「질문함에 담기」 버튼
function emptyEvidence(message, button, reportName = "보고서") {
  return el("div", { className: "evidence evidence--empty" }, [
    el("div", { className: "evidence__head" }, [
      el("span", { className: "evidence__summary" }, [
        icon("sparkles"),
        el("span", {}, ["근거 ", el("span", { className: "evidence__num", text: "0" }), `건 · ${reportName} – · 선배 인터뷰 – · 최근 –`]),
      ]),
    ]),
    el("div", { className: "evidence__empty-body" }, [el("p", { text: message }), button || null]),
  ]);
}

// lines: 칸 문장, sources: getNote.sources, reportName: 「보고서」 또는 「현장실습후기」
function evidenceBlock(lines, sources, reportName) {
  const items = lines.map((l) => ({ line: l, src: sources[l.sourceId] || {} }));
  const reports = items.filter((i) => i.src.docType && i.src.docType !== "인터뷰").length;
  const interviews = items.filter((i) => i.src.docType === "인터뷰").length;
  const latest = items.map((i) => i.src.semester).filter(Boolean).sort((a, b) => semesterKey(b) - semesterKey(a))[0];
  const num = (n) => (n > 0 ? el("span", { className: "evidence__num", text: n }) : DASH);

  // 근거 적음 라벨(6-1 v4.3): 1~2건이면 고정 문구 「선배 1명의 경험이에요」(lines.length로 판단, spec)
  // [11/26 #295] 문장 수 ≠ 선배 수(서버에 사람 수 없음)라 「선배 2명」으로 세지 않는다
  const few = lines.length <= 2 ? statusLabel("neutral", "user", "선배 1명의 경험이에요") : null;

  return el("details", { className: "evidence" }, [
    el("summary", { className: "evidence__head" }, [
      el("span", { className: "evidence__summary" }, [
        icon("sparkles"),
        el("span", {}, ["근거 ", num(lines.length), `건 · ${reportName} `, num(reports), " · 선배 인터뷰 ", num(interviews), ` · 최근 ${semesterText(latest)}`]),
      ]),
      el("span", { className: "evidence__side" }, [
        few,
        el("span", { className: "evidence__toggle" }, [
          el("span", { className: "evidence__toggle-closed", text: "펼치기" }),
          el("span", { className: "evidence__toggle-open", text: "접기" }),
          icon("chevron-down"),
        ]),
      ]),
    ]),
    // 출처 한 줄: 종류 | 연도만(v4.3). 자동 분류 문장은 끝에 「자동 분류」
    el("ul", { className: "evidence__list" }, items
      .slice()
      .sort((a, b) => semesterKey(b.src.semester) - semesterKey(a.src.semester))
      .map((i) => el("li", { className: "evidence__item" }, [
        DOC_LABEL[i.src.docType] || orDash(i.src.docType),
        " ", el("span", { className: "evidence__sep", text: "|" }), " ",
        yearOf(i.src.semester),
        i.line.autoClassified ? statusLabel("neutral", null, "자동 분류") : null,
      ]))),
  ]);
}

// ---------------------------------------------------------------------------
// 5. 칸 문장 — 원문 인용, 신고 버튼, 「개인 경험」·「자동 분류」 라벨
// ---------------------------------------------------------------------------

// 출처 칩: 「선배 인터뷰 · 2025」(연도만, v4.3).
// 배운점 문장에 senior가 있으면 「선배 A · 2025」(spec [11/22], 노트 안에서만 쓰는 글자, 학과 없음 — PRD 9-1)
function sourceChip(line, src) {
  const who = line.senior || DOC_LABEL[src.docType] || orDash(src.docType);
  return el("span", { text: `${who} · ${yearOf(src.semester)}` });
}

function reportButton(line) {
  const btn = el("button", { className: "icon-btn", attrs: { type: "button", "aria-label": "이 문장 신고" } }, [icon("flag")]);
  btn.addEventListener("click", () => openReportSheet(line));
  return btn;
}

function lineMeta(line, src) {
  return el("div", { className: "line__meta" }, [
    sourceChip(line, src),
    line.official ? statusLabel("neutral", "user", "개인 경험") : null,
    line.autoClassified ? statusLabel("neutral", null, "자동 분류") : null,
    // 후배 질문에 답한 문장(spec getNote [v2]): 질문의 칸에 일반 문장으로 들어오고 라벨만 붙인다. Q 원문은 보이지 않음
    line.answersQuestionId ? statusLabel("neutral", "message-circle", "후배 질문에 답한 문장") : null,
    reportButton(line),
  ]);
}

function lineCard(line, src, { quote = false } = {}) {
  // 배운점은 선배별 원문 인용 — 출처 칩이 「선배 A · 2025」(sourceChip)
  return el("div", { className: `line${quote ? " line--quote" : ""}` }, [
    el("p", { className: "line__text", text: line.text }),
    lineMeta(line, src),
  ]);
}

// ---------------------------------------------------------------------------
// 5-1. 칸별 요약(작업 78, spec getNote [v2] summary·[11/23] newLines·[11/26 칸유형])
//   소제목 → (비용 칸 stats 한 줄 + 분포 띠) → 요약 개조식(문장마다 한 줄 + 출처 연도 + 「보고서 N건」, official이면 「개인 경험」)
//   → 「새로 더해진 선배 이야기 N건」. 생활·지원 칸은 summary[].topic이 있으면 소주제 라벨로 묶는다.
//   [11/26 #321] 한 문단으로 이어 쓰던 것을 개조식으로 바꿈(국제처 피드백 「그래서 얼마인거지?」).
//   [11/25 #266] 「원문 N건 보기」 접기는 없앴다 — 근거는 요약 문장 끝 출처, 신고는 요약 문장에(5-2 신고 풍선).
//   summary가 없으면 이 부분을 안 쓰고 원문 목록 그대로. 배운점은 서버가 summary를 보내지 않는다.
// ---------------------------------------------------------------------------

const hasSummary = (section) =>
  section.name !== LEARN_SECTION && Array.isArray(section.summary) && section.summary.length > 0;

// lines 끝 newLines개가 요약 뒤 인터뷰로 붙은 문장. 0~lines.length 안으로만
function newLineCount(section) {
  const n = Number(section.newLines);
  const total = (section.lines || []).length;
  return Number.isFinite(n) && n > 0 ? Math.min(Math.floor(n), total) : 0;
}

// 문장 끝 출처: 「보고서 2025, 2026」, 인터뷰가 섞이면 「보고서 2025 · 선배 인터뷰 2026」
function summarySourceText(item, sources, reportName) {
  const byKind = new Map();
  for (const id of item.sources || []) {
    const src = sources[id];
    if (!src) continue;
    const kind = src.docType === "인터뷰" ? DOC_LABEL.인터뷰 : reportName;
    const year = Number(yearOf(src.semester));
    if (!byKind.has(kind)) byKind.set(kind, new Set());
    if (Number.isFinite(year)) byKind.get(kind).add(year);
  }
  // sources에서 학기를 못 찾으면 서버가 준 years로
  if (![...byKind.values()].some((s) => s.size) && Array.isArray(item.years) && item.years.length) {
    byKind.clear();
    byKind.set(reportName, new Set(item.years.map(Number).filter(Number.isFinite)));
  }
  return [...byKind.entries()]
    .map(([kind, years]) => [kind, ...(years.size ? [[...years].sort((a, b) => a - b).join(", ")] : [])].join(" "))
    .join(" · ");
}

// [11/26 칸유형] 생활 칸 소주제 순서(디자인 규칙 1-2, 민지 결정 5종). 다른 칸은 처음 나온 순서
const TOPIC_ORDER = { 생활: ["주거", "교통", "음식", "행정", "사람"] };

// 그 요약 문장 sources의 서로 다른 문서 수(spec getNote [11/26 칸유형], Q-38) — sourceId 앞부분(R149·I12)이 문서.
// R149-1-1·R149-1-3은 1명. 한 선배의 보고서와 인터뷰는 이을 칸이 없어 따로 센다
const docCount = (ids) => new Set((ids || []).map((id) => String(id).split("-")[0]).filter(Boolean)).size;

// 요약 문장 한 줄: 문장 + (출처 연도 · 「선배 N명」 · 「개인 경험」)
function summaryItem(item, sources, reportName) {
  const from = summarySourceText(item, sources, reportName);
  const count = docCount(item.sources);
  return el("li", { className: "summary__item" }, [
    summarySentence(item),
    el("span", { className: "summary__meta" }, [
      from ? el("span", { className: "summary__from", text: from }) : null,
      // 이 문장을 받치는 선배(문서) 수 — 코드 집계라 AI 표시색이 아닌 중립색. [11/26 #324] 「보고서 N건」 → 「선배 N명」
      count ? el("span", { className: "summary__count", text: `선배 ${count}명` }) : null,
      // 규정에 닿는 요약 문장(official) — 칸 문장과 같은 중립 라벨 「개인 경험」(디자인 규칙 8-1)
      item.official ? statusLabel("neutral", "user", "개인 경험") : null,
    ]),
  ]);
}

// 요약 개조식. topic이 하나라도 있으면 소주제별로 묶고, topic 없는 문장은 라벨 없이 맨 뒤
function summaryList(section, sources, reportName) {
  const items = section.summary;
  const list = (arr, extra = "") => el("ul", { className: `summary__list${extra}` }, arr.map((it) => summaryItem(it, sources, reportName)));
  const topicOf = (it) => (typeof it.topic === "string" && it.topic.trim() ? it.topic.trim() : null);
  if (!items.some(topicOf)) return [list(items)];

  const order = TOPIC_ORDER[section.name] || [];
  const groups = new Map();
  for (const it of items) {
    const t = topicOf(it);
    if (!t) continue;
    if (!groups.has(t)) groups.set(t, []);
    groups.get(t).push(it);
  }
  const rank = (t) => (order.includes(t) ? order.indexOf(t) : order.length);
  const names = [...groups.keys()].sort((a, b) => rank(a) - rank(b)); // 정렬은 안정적이라 목록 밖 라벨은 처음 나온 순서
  const out = names.map((t) =>
    el("div", { className: "summary__group" }, [el("h4", { className: "summary__topic", text: t }), list(groups.get(t))]));
  const rest = items.filter((it) => !topicOf(it));
  if (rest.length) out.push(list(rest, " summary__list--rest"));
  return out;
}

// [11/26 칸유형] 비용 칸 stats {min, max, median, n, years}(만 원, 코드 집계). 값이 이상하면 null → 표시 안 함
function validStats(stats) {
  if (!stats || typeof stats !== "object") return null;
  const { min, max, median, n } = stats;
  const nums = [min, max, median, n].map(Number);
  if (!nums.every(Number.isFinite) || nums[3] < 1 || nums[0] > nums[1] || nums[2] < nums[0] || nums[2] > nums[1]) return null;
  const years = (Array.isArray(stats.years) ? stats.years : []).map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  const values = (Array.isArray(stats.values) ? stats.values : []).map(Number).filter((v) => Number.isFinite(v) && v >= nums[0] && v <= nums[1]);
  return { min: nums[0], max: nums[1], median: nums[2], n: nums[3], years, values };
}

const manwon = (v) => `${Math.round(v).toLocaleString("ko-KR")}만 원`;

// 비용 한 줄 + 분포 띠(SVG, createElementNS — innerHTML 금지). AI가 만든 것이 아니므로 중립색만
function statsBlock(stats, reportName) {
  const range = stats.min === stats.max ? manwon(stats.min) : `${manwon(stats.min)} ~ ${manwon(stats.max)}`;
  const years = stats.years.length ? ` · ${[...new Set([stats.years[0], stats.years[stats.years.length - 1]])].join("–")}` : "";
  const line = el("p", { className: "stats__line" }, [
    el("span", { className: "stats__range num", text: `한 달 ${range}` }),
    el("span", { className: "stats__sub", text: `가운데 ${manwon(stats.median)} · ${reportName} ${stats.n}건${years}` }),
  ]);

  const NS = "http://www.w3.org/2000/svg";
  const svgEl = (tag, attrs) => {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
    return node;
  };
  // 가로로 늘어나도(preserveAspectRatio none) 점·선 굵기는 그대로(CSS vector-effect), 점은 길이 0인 둥근 선
  const W = 300, H = 28, PAD = 8, Y = 14;
  const x = (v) => (stats.max === stats.min ? W / 2 : PAD + ((v - stats.min) / (stats.max - stats.min)) * (W - PAD * 2));
  const svg = svgEl("svg", { class: "stats__strip", viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", role: "img",
    "aria-label": `한 달 비용 ${range}, 가운데 ${manwon(stats.median)}, ${reportName} ${stats.n}건` });
  svg.append(svgEl("line", { class: "stats__axis", x1: PAD, y1: Y, x2: W - PAD, y2: Y }));
  // 보고서별 금액(values)이 오면 점으로, 없으면 최소·최대 눈금만
  if (stats.values.length) stats.values.forEach((v) => svg.append(svgEl("line", { class: "stats__dot", x1: x(v), y1: Y, x2: x(v), y2: Y })));
  else [stats.min, stats.max].forEach((v) => svg.append(svgEl("line", { class: "stats__tick", x1: x(v), y1: Y - 6, x2: x(v), y2: Y + 6 })));
  svg.append(svgEl("line", { class: "stats__median", x1: x(stats.median), y1: Y - 9, x2: x(stats.median), y2: Y + 9 }));

  return el("div", { className: "stats" }, [
    line,
    svg,
    el("p", { className: "stats__ends num" }, [el("span", { text: manwon(stats.min) }), el("span", { text: manwon(stats.max) })]),
  ]);
}

// 요약 문장 하나. lineId(「S-…」)가 있으면 신고할 수 있다 — 선택하면 풍선(5-2), 키보드는 Tab → Enter
const sentenceItem = new WeakMap(); // 문장 span → summary 항목
function summarySentence(item) {
  const span = el("span", { className: "summary__sentence", text: item.text });
  if (item.lineId) {
    sentenceItem.set(span, item);
    span.tabIndex = 0;
    span.setAttribute("aria-label", `${item.text} — Enter를 누르면 이 문장을 신고할 수 있어요`);
    span.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); pickSentence(span, { bubble: false }); openReportSheet({ ...item, kind: "summary" }); }
    });
  }
  return span;
}

function summaryBlock(section, sources, reportName) {
  const lines = section.lines || [];
  const fresh = newLineCount(section);
  const added = lines.slice(lines.length - fresh);
  const stats = validStats(section.stats);
  const out = [
    el("div", { className: "summary" }, [
      el("h3", { className: "summary__title", text: section.name }),
      stats ? statsBlock(stats, reportName) : null,
      ...summaryList(section, sources, reportName),
      el("p", { className: "summary__hint" }, [icon("flag"), el("span", { text: "문장을 길게 누르거나 드래그하면 복사하거나 신고할 수 있어요" })]),
    ]),
  ];
  if (added.length) {
    out.push(el("h4", { className: "summary-new__title" }, [icon("message-circle-plus"), el("span", { text: `새로 더해진 선배 이야기 ${added.length}건` })]));
    out.push(...added.map((l) => lineCard(l, sources[l.sourceId] || {})));
  }
  return out;
}

// 신고한 요약 문장만 뺀다(원문 lines는 그대로, spec reportStatement). 하나도 안 남으면 그 칸은 원문 목록으로
function hideSummaryInSection(section, lineId) {
  if (!Array.isArray(section.summary)) return;
  section.summary = section.summary.filter((s) => s.lineId !== lineId);
  if (!section.summary.length) {
    delete section.summary;
    delete section.newLines;
  }
}

// 신고로 숨긴 문장을 요약·newLines에도 맞춘다(서버 규칙과 같게: 그 문장을 sources에 든 요약 문장은 뺀다)
function hideLineInSection(section, line) {
  const lines = section.lines || [];
  const idx = lines.findIndex((l) => l.lineId === line.lineId);
  if (idx < 0) return;
  const fresh = newLineCount(section);
  section.lines = lines.filter((l) => l.lineId !== line.lineId);
  if (!Array.isArray(section.summary)) return;
  if (idx >= lines.length - fresh) section.newLines = fresh - 1;
  section.summary = section.summary.filter((s) => !(s.sources || []).includes(line.sourceId));
  if (!section.summary.length) {
    delete section.summary;
    delete section.newLines;
  }
}

// ---------------------------------------------------------------------------
// 6. 상세 화면 — 커버 → 노트 틀 탭 → 칸 문장 + 근거 블록 → 닮은선배
// ---------------------------------------------------------------------------

const viewList = document.getElementById("viewList");
const viewDetail = document.getElementById("viewDetail");
const detailBody = document.getElementById("detailBody");
const detailTitle = document.getElementById("detailTitle");
let detailNote = null;
let currentSection = 0;
let listScrollY = 0;
let cameFromList = false; // 목록에서 눌러 들어왔으면 ←는 브라우저 뒤로(스크롤·필터 유지)

function renderSection(panel) {
  const note = detailNote;
  const section = note.sections[currentSection];
  const sources = note.sources || {};
  const lines = section.lines || [];
  const reportName = note.type === "인턴" ? "현장실습후기" : "보고서"; // [11/25 #274] 화면 용어 「결과보고서」 → 「보고서」

  const children = [];
  const askBtn = () => askBoxButton(note.id, section.name);
  if (!lines.length) {
    // [작업 123] 비교과는 후기 데이터가 없어(11/27 결정) 빈 칸에서 무엇을 할 수 있는지까지 말한다. 6-2 틀은 그대로
    const emptyText = note.type === "비교과"
      ? "아직 경험담이 없어요. 질문을 남기면 선배에게 전달돼요."
      : "아직 이 항목을 경험한 선배의 이야기가 없어요.";
    const empty = emptyEvidence(emptyText, askBtn(), reportName);
    empty.querySelector("p").style.wordBreak = "keep-all"; // 390px에서 「전달돼 / 요」처럼 끊기지 않게
    children.push(empty);
  } else {
    if (hasSummary(section)) children.push(...summaryBlock(section, sources, reportName));
    else children.push(...lines.map((l) => lineCard(l, sources[l.sourceId] || {}, { quote: section.name === LEARN_SECTION })));
    children.push(evidenceBlock(lines, sources, reportName));

    // 블록 아래 줄: 오래된 근거 · 공식 안내(6-1)
    const after = [];
    const years = lines.map((l) => Number(yearOf((sources[l.sourceId] || {}).semester))).filter(Number.isFinite);
    const thisYear = new Date().getFullYear();
    if (years.length && years.every((y) => thisYear - y > OLD_YEARS)) {
      after.push(statusLabel("info", "info", "최근 경험이 없어요"), askBtn());
    }
    const url = safeUrl(note.officialUrl);
    if (lines.some((l) => l.official) && url) {
      after.push(el("a", { className: "link-more", text: "공식 안내 보기 ›", attrs: { href: url, target: "_blank", rel: "noopener" } }));
    }
    if (after.length) children.push(el("div", { className: "evidence-after" }, after));
  }
  panel.replaceChildren(...children);
  drawIcons();
}

// 고른 탭이 화면 밖으로 잘려 있으면 탭 줄을 밀어 다 보이게 한다(다음 탭도 살짝 보이도록 한 칸 여유).
// 탭 줄만 옆으로 움직이고 화면 전체는 위아래로 움직이지 않게 scrollTo를 쓴다.
function revealTab(tabs, tab) {
  const pad = 48;
  const left = tab.offsetLeft; // .section-tabs가 position: relative라 탭 줄 기준 위치
  const right = left + tab.offsetWidth;
  let target = null;
  if (right + pad > tabs.scrollLeft + tabs.clientWidth) target = right + pad - tabs.clientWidth;
  else if (left - pad < tabs.scrollLeft) target = left - pad;
  if (target === null) return;
  const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  tabs.scrollTo({ left: Math.max(0, target), behavior: smooth ? "smooth" : "auto" });
}

function renderDetail() {
  const note = detailNote;
  detailTitle.textContent = orDash(note.program);
  document.title = `${orDash(note.program)} · 해봤노트`;
  if (currentSection >= note.sections.length) currentSection = 0;

  // 노트 틀 탭: 칸 순서는 getNote가 준 순서 그대로(data/frames.json)
  const tabs = el("div", { className: "section-tabs", attrs: { role: "tablist", "aria-label": "노트 틀" } });
  const panel = el("div", { className: "section-panel", attrs: { role: "tabpanel", id: "sectionPanel" } });
  note.sections.forEach((s, i) => {
    const tab = el("button", {
      className: "choice-chip",
      text: s.name,
      attrs: { type: "button", role: "tab", "aria-selected": String(i === currentSection), "aria-controls": "sectionPanel" },
    });
    tab.addEventListener("click", () => {
      currentSection = i;
      for (const t of tabs.children) t.setAttribute("aria-selected", String(t === tab));
      revealTab(tabs, tab);
      renderSection(panel);
    });
    tabs.append(tab);
  });

  const seniors = el("a", {
    className: "btn btn--secondary btn--block",
    text: "이 노트를 경험한 닮은선배 보기",
    attrs: { href: `../senior/?noteId=${encodeURIComponent(note.id)}` },
  });

  detailBody.setAttribute("aria-busy", "false");
  detailBody.replaceChildren(noteCover(note, { link: false }), tabs, panel, seniors);
  renderSection(panel);
}

// 최근에 본 노트(PR #232 원우 요청): 닮은선배 탭이 관심 경험의 세부 활동 칩으로 쓴다(senior.js collectActivities).
// 이 탭의 sessionStorage에만, 사람별, 최근이 앞, 30개까지(두 창 시연이 섞이지 않게)
// 11/27: [{ id, at(ISO), from }] — from = "search"(검색어가 있는 목록에서 연 노트) | "view". 검색어만 친 것은 남기지 않는다(활동이 아님).
//        예전 모양(id 문자열)이 섞여 있어도 읽고, 새로 쓸 때 이 모양으로 바꾼다.
const VIEWED_MAX = 30;
let openFrom = "view"; // 목록 카드를 누를 때 정한다(openDetail). 주소로 바로 들어온 상세는 "view"
function rememberViewed(id, from = "view") {
  if (!me || !id) return;
  const key = `viewedNotes:${me.colreg_no}`;
  try {
    const old = JSON.parse(sessionStorage.getItem(key) || "[]");
    const prev = (Array.isArray(old) ? old : []).map((x) => (typeof x === "string" ? { id: x } : x)).filter((x) => x && x.id && x.id !== id);
    const list = [{ id, at: new Date().toISOString(), from }, ...prev].slice(0, VIEWED_MAX);
    sessionStorage.setItem(key, JSON.stringify(list));
  } catch {
    // 저장 공간이 막혀 있으면 기억하지 않는다
  }
}

async function loadDetail(id) {
  detailNote = null;
  currentSection = 0;
  detailTitle.textContent = "해봤노트";
  detailBody.setAttribute("aria-busy", "true");
  detailBody.replaceChildren(...[0, 1, 2].map(() => el("div", { className: "skeleton detail-skeleton", attrs: { "aria-hidden": "true" } })));
  try {
    const res = await getNote(id);
    if (!res || res.error || !Array.isArray(res.sections)) throw new Error((res && res.error) || "노트 없음");
    detailNote = res;
    rememberViewed(id, openFrom);
    openFrom = "view";
    renderDetail();
  } catch (err) {
    console.error(err);
    detailBody.setAttribute("aria-busy", "false");
    detailBody.replaceChildren(errorBox(() => loadDetail(id)));
    drawIcons();
  }
}

// ---------------------------------------------------------------------------
// 7. 화면 전환 — 주소 ?id=노트번호 이면 상세. 브라우저 뒤로가기도 같이 동작
// ---------------------------------------------------------------------------

function showList() {
  viewDetail.hidden = true;
  viewList.hidden = false;
  document.title = "해봤노트 · 외대人사이드";
  if (!listRequested) loadList();
  window.scrollTo(0, listScrollY);
}

function showDetail(id) {
  viewList.hidden = true;
  viewDetail.hidden = false;
  window.scrollTo(0, 0);
  loadDetail(id);
}

function openDetail(id) {
  listScrollY = window.scrollY;
  cameFromList = true;
  openFrom = currentQuery.trim() ? "search" : "view"; // 검색 결과에서 연 노트는 닮은선배 활동 칩의 「검색」 이력
  history.pushState({ noteId: id }, "", `?id=${encodeURIComponent(id)}`);
  showDetail(id);
}

// 처음 들어올 때 주소의 필터를 되살린다: ?cat=&region=&group=&q= (syncUrl이 남긴 것).
// ?type=인턴처럼 들어오면(인터BOO chat 칩 「다른 노트 보기」) 그 분야 필터를 켠다.
// 목록에 없는 값은 renderList가 칩을 그리며 풀어 준다
function restoreFilters(params) {
  const saved = params.get("cat") || "";
  const cat = Object.hasOwn(CATEGORY_NAME, saved) ? saved : CATEGORY[params.get("type")] || "";
  currentCat = cat;
  currentRegion = (cat === "global" && params.get("region")) || "";
  currentGroup = (GROUP_BY_CAT[cat] && params.get("group")) || "";
  for (const c of document.querySelectorAll("#filters .choice-chip")) c.setAttribute("aria-pressed", String(c.dataset.cat === cat));
  queryInput.value = (params.get("q") || "").slice(0, queryInput.maxLength);
  currentQuery = queryInput.value;
  queryClear.hidden = currentQuery === "";
}

function route() {
  const params = new URLSearchParams(location.search);
  const id = params.get("id");
  if (id) showDetail(id);
  else showList();
}

// 주소의 필터는 처음 들어올 때 한 번만 — 뒤로가기(popstate)로 목록에 오면 사용자가 고른 필터를 그대로 둔다
restoreFilters(new URLSearchParams(location.search));

document.getElementById("detailBack").addEventListener("click", () => {
  if (cameFromList) {
    cameFromList = false;
    history.back(); // popstate → route() → 목록(필터·스크롤 그대로)
  } else {
    // 인터BOO 링크 등으로 바로 들어온 경우: 목록으로
    history.replaceState(null, "", location.pathname);
    showList();
  }
});
window.addEventListener("popstate", () => {
  cameFromList = false;
  route();
});

// ---------------------------------------------------------------------------
// 8. 신고 바텀시트 — 사유 고르기 → reportStatement → 그 문장 숨김
// ---------------------------------------------------------------------------

const REPORT_REASONS = ["사실과 달라요", "개인 정보가 보여요", "불쾌한 표현이 있어요", "기타"];
const sheet = document.getElementById("reportSheet");
const reasonsEl = document.getElementById("reportReasons");
const submitBtn = document.getElementById("reportSubmit");
const reasonHint = document.getElementById("reportReason");
const reportQuote = document.getElementById("reportQuote");
let reportTarget = null;
let reportChoice = null;
let lastFocus = null;

// target: 원문 문장(line, lineId 「L-…」) 또는 요약 문장({ lineId 「S-…」, text, kind: "summary" })
function openReportSheet(line) {
  hideReportBubble();
  reportTarget = line;
  reportChoice = null;
  lastFocus = document.activeElement;
  reportQuote.textContent = line.text || "";
  reportQuote.hidden = !line.text;
  reasonsEl.replaceChildren(...REPORT_REASONS.map((r) => {
    const chip = el("button", { className: "choice-chip", text: r, attrs: { type: "button", "aria-pressed": "false" } });
    chip.addEventListener("click", () => {
      reportChoice = r;
      for (const c of reasonsEl.children) c.setAttribute("aria-pressed", String(c === chip));
      submitBtn.disabled = false;
      reasonHint.hidden = true;
    });
    return chip;
  }));
  submitBtn.disabled = true;
  reasonHint.hidden = false;
  sheet.hidden = false;
  document.body.classList.add("sheet-open");
  sheet.querySelector(".sheet").focus();
}

function closeReportSheet() {
  clearPicked();
  sheet.hidden = true;
  document.body.classList.remove("sheet-open");
  reportTarget = null;
  if (lastFocus && lastFocus.isConnected) lastFocus.focus();
}

submitBtn.addEventListener("click", async () => {
  if (!reportTarget || !reportChoice || !detailNote) return;
  submitBtn.disabled = true;
  try {
    const res = await reportStatement(reportTarget.lineId, reportChoice);
    if (!res || !res.ok) throw new Error((res && res.error) || "신고 실패");
    // 신고한 문장은 바로 숨긴다(spec: 즉시 숨김). 요약 문장이면 그 요약 문장만
    for (const s of detailNote.sections) {
      if (reportTarget.kind === "summary") hideSummaryInSection(s, reportTarget.lineId);
      else hideLineInSection(s, reportTarget);
    }
    closeReportSheet();
    renderSection(document.getElementById("sectionPanel"));
    toast("신고했어요. 이 문장은 숨겼어요");
  } catch (err) {
    console.error(err);
    submitBtn.disabled = false;
    toast("신고하지 못했어요. 다시 시도해 주세요", "circle-alert");
  }
});
document.getElementById("reportCancel").addEventListener("click", closeReportSheet);
sheet.querySelector(".sheet-scrim").addEventListener("click", closeReportSheet);
sheet.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeReportSheet();
});

// ---------------------------------------------------------------------------
// 8-1. 요약 문장 고르기 → 「복사」·「신고하기」 풍선(spec reportStatement 화면, 디자인 규칙 8-1 ③) — 11/25 #266, 11/26 문장 단위
//   [11/26 민지] 길게 누르면 단어만 잡히던 것을 문장 하나 전체로 고른다. 고른 문장은 빨간 글자 + 빨간 밑줄(여러 줄이어도 전체).
//   - 휴대폰: 요약 문장은 브라우저 글자 선택을 끄고(index.html) 0.5초 길게 누르기를 직접 잰다.
//   - PC: 문장 위에서 드래그를 시작하면 그 문장 하나 전체를 고른다(브라우저 글자 선택은 끔 — 여러 문장에 걸치지 않게). 0.5초 누르고 있어도 같다.
//   - 브라우저 선택 대신 문장을 고르므로 복사는 풍선의 「복사」(그 문장 전체). 「신고하기」 버튼·신고 시트는 그대로.
//   - 다른 곳을 누르거나 Esc·화면 크기 바뀜·시트 닫기(취소)면 선택을 푼다.
//   - 신고·복사 대상은 고른 문장 span에 묶인 summary 항목(sentenceItem) — 화면 문장 = 시트 인용 = reportStatement(lineId).
// ---------------------------------------------------------------------------

const bubble = el("button", { className: "report-bubble", attrs: { type: "button" } }, [icon("flag"), el("span", { text: "신고하기" })]);
const copyBtn = el("button", { className: "copy-bubble", attrs: { type: "button" } }, [icon("copy"), el("span", { text: "복사" })]);
const pop = el("div", { className: "sentence-pop" }, [copyBtn, bubble]);
pop.hidden = true;
document.body.append(pop);
let bubbleItem = null;
let pickedSpan = null;

function sentenceOf(node) {
  const elNode = node && (node.nodeType === 1 ? node : node.parentElement);
  const span = elNode && elNode.closest(".summary__sentence");
  return span && sentenceItem.has(span) ? span : null;
}

function hideReportBubble() {
  pop.hidden = true;
}

function clearPicked() {
  if (pickedSpan) pickedSpan.classList.remove("summary__sentence--picked");
  pickedSpan = null;
  bubbleItem = null;
  hideReportBubble();
}

// 문장 하나 전체를 고른다. bubble: false면 표시만(키보드 Enter → 바로 시트)
function pickSentence(span, { bubble: showPop = true } = {}) {
  if (pickedSpan && pickedSpan !== span) pickedSpan.classList.remove("summary__sentence--picked");
  pickedSpan = span;
  span.classList.add("summary__sentence--picked");
  bubbleItem = sentenceItem.get(span);
  if (!showPop || viewDetail.hidden) return;
  pop.hidden = false;
  drawIcons();
  // 고른 문장의 마지막 줄 오른쪽 끝 아래 8px. 화면 밖으로 나가지 않게 좌우 16px 안으로
  const rects = span.getClientRects();
  const last = rects[rects.length - 1] || span.getBoundingClientRect();
  const w = pop.offsetWidth;
  const left = Math.min(Math.max(16, last.right - w), document.documentElement.clientWidth - w - 16);
  pop.style.left = `${left + window.scrollX}px`;
  pop.style.top = `${last.bottom + window.scrollY + 8}px`;
}

// 길게 누르기(휴대폰 손가락·PC 마우스 모두): 0.5초, 10px 넘게 움직이면 취소(휴대폰은 스크롤).
// PC 마우스로 문장 위에서 끌면(10px 넘게) 드래그를 시작한 문장 하나만 바로 고른다 — 여러 문장을 한 번에 고르지 않는다(11/26)
const LONG_PRESS_MS = 500;
let press = null;
function cancelPress() {
  if (press) clearTimeout(press.timer);
  press = null;
}
document.addEventListener("pointerdown", (e) => {
  if (pop.contains(e.target) || !sheet.hidden) return;
  const span = sentenceOf(e.target);
  // 문장 밖을 누르면 선택을 푼다
  if (!span) { if (pickedSpan) clearPicked(); return; }
  if (pickedSpan && pickedSpan !== span) clearPicked();
  cancelPress();
  press = { x: e.clientX, y: e.clientY, span, mouse: e.pointerType === "mouse", timer: setTimeout(() => { press = null; pickSentence(span); }, LONG_PRESS_MS) };
});
document.addEventListener("pointermove", (e) => {
  if (!press || Math.hypot(e.clientX - press.x, e.clientY - press.y) <= 10) return;
  const { span, mouse } = press;
  cancelPress();
  if (mouse) pickSentence(span);
});
for (const type of ["pointerup", "pointercancel"]) document.addEventListener(type, cancelPress);
window.addEventListener("scroll", cancelPress, { passive: true });
// 안드로이드 길게 누르기의 기본 메뉴(복사·공유 등)는 요약 문장에서만 막는다 — 대신 풍선이 뜬다
document.addEventListener("contextmenu", (e) => {
  if (sentenceOf(e.target)) e.preventDefault();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && pickedSpan && sheet.hidden) clearPicked();
});

// 풍선을 누를 때 포커스·선택이 풀려 풍선이 먼저 사라지지 않게 기본 동작을 막는다
pop.addEventListener("mousedown", (e) => e.preventDefault());
bubble.addEventListener("click", () => {
  if (!bubbleItem) return;
  // 시트가 열려 있는 동안 문장 표시는 남기고, 시트를 닫으면(취소 포함) 푼다
  openReportSheet({ ...bubbleItem, kind: "summary" });
});
copyBtn.addEventListener("click", async () => {
  if (!bubbleItem) return;
  const text = bubbleItem.text || "";
  try {
    await copyText(text);
    toast("문장을 복사했어요");
  } catch (err) {
    console.error(err);
    toast("복사하지 못했어요. 다시 시도해 주세요", "circle-alert");
  }
  clearPicked();
});

// 클립보드 API가 없거나 막힌 브라우저는 숨긴 입력칸으로 복사(글자만)
async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
  const area = el("textarea", { className: "copy-scratch", attrs: { readonly: "", "aria-hidden": "true" } });
  area.value = text;
  document.body.append(area);
  area.select();
  const ok = document.execCommand("copy");
  area.remove();
  if (!ok) throw new Error("copy failed");
}
// 화면 폭이 바뀌면(회전 등) 풍선 자리가 어긋나므로 푼다. 휴대폰 주소줄이 접히며 높이만 바뀌는 것은 무시
let lastWidth = window.innerWidth;
window.addEventListener("resize", () => {
  if (window.innerWidth === lastWidth) return;
  lastWidth = window.innerWidth;
  clearPicked();
});

// ---------------------------------------------------------------------------
// 9. 시작
// ---------------------------------------------------------------------------

drawIcons();
if (me) route();

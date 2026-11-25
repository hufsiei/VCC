// 탭1 수요 현황(PRD 5-2, 작업 68) — getAdminOverview 응답을 그린다. 수치는 모두 서버 집계, 화면은 그리기만.
import { el, icon, statusLabel, fmt } from "./ui.js";

// 칸 → 분야. 원본은 data/frames.json(교환·파견 = 국제교류, 인턴 = 현장실습, 비교과).
// 화면 코드는 데이터 파일을 직접 읽지 않으므로(코드 규칙) 여기 적는다. 두 분야 이상에 있는 칸(배운점)은 「여러 분야 공통」.
// 서버가 sectionsByField(PR #242)를 주면 배운점도 분야별로 나눈다(sectionGroups).
const FIELD_SECTIONS = [
  { field: "국제교류", cat: "cat-global", sections: ["지원", "학점", "비용", "생활", "팁"] },
  { field: "현장실습", cat: "cat-practice", sections: ["지원동기", "업무내용", "지원·선발", "근무조건"] },
  { field: "비교과", cat: "cat-extra", sections: ["활동내용"] },
];
const COMMON = "여러 분야 공통";
const LEARNED = "배운점";
const CAT = { 국제교류: "cat-global", 현장실습: "cat-practice", 비교과: "cat-extra" };

const TOP_PROGRAMS = 10;
const TOP_COLLEGES = 8;

const KPIS = [
  { key: "questions", name: "질문 수", icon: "message-circle" },
  { key: "unanswered", name: "미답변 질문", icon: "clock", goodWhenDown: true },
  { key: "newDemand", name: "신규 수요", icon: "info" },
  { key: "improvements", name: "개선 요청", icon: "triangle-alert" },
];

// ---------------------------------------------------------------------------
// 로딩(6-3): 스켈레톤
// ---------------------------------------------------------------------------
export function renderDemandLoading(panel) {
  const sk = (cls) => el("div", { className: `skeleton ${cls}`, attrs: { "aria-hidden": "true" } });
  panel.setAttribute("aria-busy", "true");
  panel.replaceChildren(
    el("div", { className: "kpi-row" }, [sk("kpi--skeleton"), sk("kpi--skeleton"), sk("kpi--skeleton"), sk("kpi--skeleton")]),
    el("div", { className: "pc-only" }, sk("block--skeleton")),
  );
}

// ---------------------------------------------------------------------------
// 그리기
// ---------------------------------------------------------------------------
export function renderDemand(panel, data, { dept }) {
  const basis = (data.period && data.period.type) === "month" ? "전월 대비" : "전 학기 대비";
  panel.replaceChildren(
    kpiRow(data.kpi || {}, basis),
    el("div", { className: "pc-only console-panel" }, [
      programBlock(data.programs || [], dept === "ALL" ? data.unclassified : 0),
      sectionBlock(data.sections || {}, data.sectionsByField),
      el("div", { className: "grid-2" }, [collegeBlock(data.colleges || []), notesBlock(data.notes || {})]),
    ]),
  );
  panel.removeAttribute("aria-busy");
}

// 1. KPI 카드 4개 ---------------------------------------------------------------
function kpiRow(kpi, basis) {
  return el("div", { className: "kpi-row" }, KPIS.map((k) => {
    const v = kpi[k.key] || {};
    return el("div", { className: "card kpi" }, [
      el("p", { className: "kpi__name" }, [icon(k.icon), el("span", { text: k.name })]),
      el("p", { className: "kpi__value" }, [el("span", { text: fmt(v.value) }), el("span", { className: "kpi__unit", text: "건" })]),
      k.key === "unanswered" ? el("p", { className: "kpi__sub", text: `보류율 ${fmt(v.holdRate)}%` }) : null,
      deltaBadge(v.delta, basis, k.goodWhenDown),
    ]);
  }));
}

// 증감 배지(3-4): 기본 중립색. 미답변 질문이 줄었을 때만 긍정색. 비교할 값이 없으면 「비교 없음」
function deltaBadge(delta, basis, goodWhenDown) {
  if (delta === null || delta === undefined || !Number.isFinite(delta)) return statusLabel("neutral", "minus", "비교 없음");
  if (delta === 0) return statusLabel("neutral", "minus", `0% ${basis}`);
  const down = delta < 0;
  const kind = goodWhenDown && down ? "success" : "neutral";
  const badge = statusLabel(kind, down ? "arrow-down" : "arrow-up", `${Math.abs(delta)}% ${basis}`);
  badge.setAttribute("aria-label", `${basis} ${Math.abs(delta)}% ${down ? "감소" : "증가"}`);
  return badge;
}

// 2. 프로그램별 질문 순위 Top 10 + 오른쪽 칸 분포 ---------------------------------
function programBlock(programs, unclassified) {
  const top = [...programs].sort((a, b) => (b.questions || 0) - (a.questions || 0)).slice(0, TOP_PROGRAMS);
  const block = el("div", { className: "card block" }, [
    el("div", { className: "block__head" }, [
      el("h2", { className: "section-title", text: `프로그램별 질문 순위 Top ${TOP_PROGRAMS}` }),
      el("p", { className: "block__note", text: "행을 누르면 칸별 질문을 볼 수 있어요" }),
    ]),
  ]);
  if (!top.length) {
    block.append(empty("message-circle", "이 기간에 들어온 질문이 없어요"));
    return block;
  }
  const max = Math.max(...top.map((p) => p.questions || 0), unclassified || 0, 1);
  const list = el("div", { className: "rank-list" });
  const detail = el("div", { className: "detail-panel", attrs: { "aria-live": "polite" } });

  const rows = top.map((p, i) => {
    const row = el("button", { className: "rank-row", attrs: { type: "button", "aria-pressed": i === 0 ? "true" : "false" } }, [
      el("span", { className: "rank-row__no", text: i + 1 }),
      el("span", { className: "rank-row__name", text: p["프로그램명"], attrs: { title: p["프로그램명"] } }),
      bar(p.questions, max),
      el("span", { className: "bar-value", text: `${fmt(p.questions)}건` }),
    ]);
    row.addEventListener("click", () => {
      rows.forEach((r) => r.setAttribute("aria-pressed", String(r === row)));
      showProgram(detail, p);
    });
    return row;
  });
  list.append(...rows);
  if (unclassified > 0) {
    list.append(el("div", { className: "rank-row rank-row--static" }, [
      el("span", { className: "rank-row__no", text: "–" }),
      el("span", { className: "rank-row__name", text: "분류 안 됨" }),
      bar(unclassified, max),
      el("span", { className: "bar-value", text: `${fmt(unclassified)}건` }),
    ]));
  }
  showProgram(detail, top[0]);
  block.append(el("div", { className: "grid-2" }, [list, detail]));
  return block;
}

function showProgram(detail, p) {
  const field = p["분야"];
  const secs = p.sections || {};
  const frame = FIELD_SECTIONS.find((f) => f.field === field);
  // 그 분야 노트 틀 순서 + 배운점. 질문이 0건인 칸도 보여 줘야 빈 칸이 보인다. 틀에 없는 칸이 오면 뒤에 붙인다
  const order = frame ? [...frame.sections, LEARNED] : [];
  for (const k of Object.keys(secs)) if (!order.includes(k)) order.push(k);
  const max = Math.max(...order.map((k) => secs[k] || 0), 1);
  detail.replaceChildren(
    el("p", { className: "detail-panel__title", text: p["프로그램명"] }),
    el("p", { className: "detail-panel__meta" }, [
      CAT[field] ? el("span", { className: `category-tag ${CAT[field]}`, text: field }) : null,
      el("span", { text: `질문 ${fmt(p.questions)}건 · 보류 ${fmt(p.hold)}건` }),
    ]),
    ...order.map((k) => secRow(k, secs[k] || 0, max)),
  );
}

// 3. 칸별 질문 비율 — 분야별 묶음(11/25 민지 확정) --------------------------------
// sectionsByField(PR #242)가 오면 배운점도 분야별로 나눈다. 서버는 sections와 같은 질문으로 세므로
// 칸마다 「sections − 세 분야 합」 = 분야를 모르는 질문 → 「여러 분야 공통」. 필드가 없으면(mock) 예전처럼.
function sectionGroups(sections, byField) {
  const label = (f) => el("span", { className: `category-tag ${f.cat}`, text: f.field });
  const commonLabel = () => el("span", { className: "field-group__common", text: COMMON });
  if (byField && typeof byField === "object" && Object.keys(byField).length) {
    const groups = FIELD_SECTIONS.map((f) => ({ label: label(f), counts: { ...(byField[f.field] || {}) } }));
    const rest = {};
    for (const [k, n] of Object.entries(sections)) {
      const left = (n || 0) - groups.reduce((s, g) => s + (g.counts[k] || 0), 0);
      if (left > 0) rest[k] = left;
    }
    groups.push({ label: commonLabel(), counts: rest });
    return { groups, note: "분야를 알 수 없는 질문은 「여러 분야 공통」에 모았어요." };
  }
  const known = new Set([...FIELD_SECTIONS.flatMap((f) => f.sections), LEARNED]);
  const pick = (keys) => Object.fromEntries(keys.filter((k) => sections[k]).map((k) => [k, sections[k]]));
  const groups = FIELD_SECTIONS.map((f) => ({ label: label(f), counts: pick(f.sections) }));
  // 배운점 + 틀에 없는 칸 → 여러 분야 공통
  groups.push({ label: commonLabel(), counts: pick([LEARNED, ...Object.keys(sections).filter((k) => !known.has(k))]) });
  return { groups, note: "배운점은 세 분야 노트에 모두 있는 칸이라 따로 모았어요." };
}

function sectionBlock(sections, byField) {
  const total = Object.values(sections).reduce((s, n) => s + (n || 0), 0);
  const block = el("div", { className: "card block" }, [
    el("div", { className: "block__head" }, [
      el("h2", { className: "section-title", text: "칸별 질문 비율" }),
      el("p", { className: "block__note", text: `전체 ${fmt(total)}건` }),
    ]),
  ]);
  if (!total) {
    block.append(empty("message-circle", "이 기간에 들어온 질문이 없어요"));
    return block;
  }
  const { groups, note } = sectionGroups(sections, byField);
  const max = Math.max(...groups.flatMap((g) => Object.values(g.counts)), 1);
  for (const g of groups) {
    const keys = Object.keys(g.counts).filter((k) => g.counts[k] > 0).sort((a, b) => g.counts[b] - g.counts[a]);
    if (!keys.length) continue; // 그 부서에 없는 분야는 묶음째 뺀다
    block.append(el("div", { className: "field-group" }, [
      el("div", { className: "field-group__label" }, g.label),
      el("div", { className: "field-group__rows" }, keys.map((k) => secRow(k, g.counts[k], max, total))),
    ]));
  }
  block.append(el("p", { className: "block__note", text: note }));
  return block;
}

// 4. 학과별 질문 분포 — 상위 8 + 그 외 -------------------------------------------
function collegeBlock(colleges) {
  // 서버가 이미 「그 외」 행을 줄 수 있다(mock) → 맨 아래에 그대로 두고, 나머지만 상위 8개로 자른다
  const REST = "그 외";
  const given = colleges.filter((c) => c["학과"] === REST);
  const sorted = colleges.filter((c) => c["학과"] !== REST).sort((a, b) => (b.questions || 0) - (a.questions || 0));
  const top = sorted.slice(0, TOP_COLLEGES);
  const rest = [...sorted.slice(TOP_COLLEGES), ...given];
  const block = el("div", { className: "card block" }, el("h2", { className: "section-title", text: "학과별 질문 분포" }));
  if (!top.length) {
    block.append(empty("users", "학과별로 볼 질문이 없어요"));
    return block;
  }
  const row = (name, q, rate, cls) => el("tr", { className: cls || "" }, [
    el("td", { text: name }),
    el("td", { className: "is-num", text: `${fmt(q)}건` }),
    el("td", { className: "is-num", text: `${fmt(rate)}%` }),
  ]);
  const body = el("tbody", {}, top.map((c) => row(c["학과"], c.questions, c.holdRate)));
  if (rest.length) {
    // 그 외: 질문 수는 합, 보류율은 질문 수 가중 평균
    const q = rest.reduce((s, c) => s + (c.questions || 0), 0);
    const held = rest.reduce((s, c) => s + (c.questions || 0) * (c.holdRate || 0), 0);
    const only = rest.length === 1 ? rest[0] : null; // 한 행뿐이면 서버 값을 그대로
    body.append(row(REST, q, only ? only.holdRate : (q ? Math.round(held / q) : 0), "is-rest"));
  }
  block.append(el("table", { className: "dept-table" }, [
    el("thead", {}, el("tr", {}, [
      el("th", { text: "학과", attrs: { scope: "col" } }),
      el("th", { className: "is-num", text: "질문 수", attrs: { scope: "col" } }),
      el("th", { className: "is-num", text: "보류율", attrs: { scope: "col" } }),
    ])),
    body,
  ]));
  return block;
}

// 5. 노트 현황 — 작은 수치 4개 ---------------------------------------------------
function notesBlock(notes) {
  const items = [
    ["해봤노트", `${fmt(notes.count)}개`],
    ["근거 문단", `${fmt(notes.evidence)}개`],
    ["선배 인터뷰", `${fmt(notes.interviews)}건`],
    ["공개 동의율", `${fmt(notes.consentRate)}%`],
  ];
  return el("div", { className: "card block" }, [
    el("h2", { className: "section-title", text: "노트 현황" }),
    el("div", { className: "mini-row" }, items.map(([name, value]) => el("div", { className: "mini" }, [
      el("span", { className: "mini__name", text: name }),
      el("span", { className: "mini__value", text: value }),
    ]))),
  ]);
}

// 작은 부품 ----------------------------------------------------------------------
function bar(value, max) {
  const pct = Math.max(0, Math.min(100, ((value || 0) / max) * 100));
  return el("span", { className: "bar-track", attrs: { "aria-hidden": "true" } }, el("span", { className: "bar-fill", attrs: { style: `width:${pct}%` } }));
}

function secRow(name, n, max, total) {
  const label = total ? `${fmt(n)}건 · ${Math.round((n / total) * 100)}%` : `${fmt(n)}건`;
  return el("div", { className: "sec-row" }, [
    el("span", { className: "sec-row__name", text: name }),
    bar(n, max),
    el("span", { className: "bar-value", text: label }),
  ]);
}

function empty(iconName, title) {
  return el("div", { className: "empty" }, [icon(iconName), el("p", { className: "empty__title", text: title })]);
}

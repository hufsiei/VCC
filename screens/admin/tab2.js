// 탭2 개선 제안(PRD 5-3, 작업 68) — getAdminSuggestions 응답을 카드 목록으로 그린다.
// 제안 문장은 사전 생성(data/suggestions.json)이라 시연 중 AI 호출이 없다. 화면은 그리기 + 상태 바꾸기만.
// 「신고된 진술」 섹션(reported)은 작업 33에서 미리가 이 탭 아래에 붙인다(11/25 재계획).
import { setSuggestionStatus } from "../../common/data.js";
import { el, icon, statusLabel, fmt, toast, drawIcons } from "./ui.js";

const STATUSES = ["새로 옴", "검토 중", "반영됨", "보류"];

// 유형 라벨(3-4): 신규 수요 = 정보, 안내 보강·검토 필요 = 주의
const TYPES = {
  "신규 수요": { kind: "info", icon: "info" },
  "안내 보강": { kind: "warning", icon: "triangle-alert" },
  "검토 필요": { kind: "warning", icon: "triangle-alert" },
};

// ---------------------------------------------------------------------------
// 로딩(6-3): 스켈레톤
// ---------------------------------------------------------------------------
export function renderSuggestLoading(panel) {
  const sk = () => el("div", { className: "skeleton sugg--skeleton", attrs: { "aria-hidden": "true" } });
  panel.setAttribute("aria-busy", "true");
  panel.replaceChildren(el("div", { className: "pc-only sugg-list" }, [sk(), sk(), sk()]));
}

// ---------------------------------------------------------------------------
// 그리기
// deptNames: { 부서코드: 부서명 } — 카드의 「담당 부서」
// onChanged: 상태를 바꾼 뒤 부른다(탭1 KPI 「개선 요청」 = 새로 옴 건수가 바뀌므로)
// ---------------------------------------------------------------------------
export function renderSuggest(panel, data, { deptNames = {}, onChanged } = {}) {
  const list = Array.isArray(data.suggestions) ? data.suggestions : [];
  // 정렬: 새로 옴 → 근거 질문 많은 순 → 최근 순(PRD 5-3). 상태를 바꿔도 다시 불러오기 전까지 자리는 그대로
  const sorted = [...list].sort((a, b) =>
    (b.status === "새로 옴") - (a.status === "새로 옴")
    || (b.count || 0) - (a.count || 0)
    || String(b.lastAt || "").localeCompare(String(a.lastAt || "")));
  const note = el("p", { className: "block__note" });
  const countFresh = () => {
    const fresh = list.filter((s) => s.status === "새로 옴").length;
    note.textContent = `새로 옴 ${fmt(fresh)}건 · 새로 온 제안부터, 근거 질문이 많은 순`;
  };
  countFresh();
  const changed = (s) => { countFresh(); if (onChanged) onChanged(s); };

  const head = el("div", { className: "block__head" }, [
    el("h2", { className: "section-title", text: `개선 제안 ${fmt(list.length)}건` }),
    note,
  ]);
  const wrap = el("div", { className: "pc-only sugg-list" }, [head]);

  // 시연 중 새로 생긴 보류·규정 질문: 제안은 다음 집계 때(PRD 5-3)
  if (data.pendingNew > 0) {
    wrap.append(el("p", {}, statusLabel("info", "info", `새 질문 ${fmt(data.pendingNew)}건 — 다음 집계 때 제안 생성`)));
  }

  if (!sorted.length) {
    wrap.append(el("div", { className: "card empty" }, [
      icon("inbox"),
      el("p", { className: "empty__title", text: "이 기간에 개선 제안이 없어요" }),
      el("p", { className: "sub", text: "같은 프로그램·칸에 질문이 3건 이상 쌓이면 제안이 만들어져요." }),
    ]));
  } else {
    wrap.append(...sorted.map((s) => card(s, deptNames, changed)));
  }
  panel.replaceChildren(wrap);
  panel.removeAttribute("aria-busy");
}

// 카드 하나 -------------------------------------------------------------------
function card(s, deptNames, onChanged) {
  const type = TYPES[s["유형"]] || { kind: "neutral", icon: null };
  const dept = deptNames[s["부서코드"]] || s["부서코드"] || "–";
  const titleId = `sugg-${s.id}`;

  const top = el("div", { className: "sugg__top" }, [
    statusLabel(type.kind, type.icon, s["유형"] || "제안"),
    el("span", { className: "sugg__dept", text: `담당 부서 ${dept}` }),
  ]);

  // AI 제안 문장(✦ HUFS GREEN) — 비었거나 검증에 걸려 버려졌으면 제목만 둔다(PRD 5-3·10장)
  const ai = s["제안"]
    ? el("p", { className: "sugg__ai" }, [
      el("span", { className: "ai-mark", attrs: { role: "img", "aria-label": "AI 제안", title: "AI가 쓴 제안" } }, icon("sparkles")),
      el("span", { text: s["제안"] }),
    ])
    : null;

  // 근거 질문 N건 · 최근 YYYY-MM + 펼치기
  const questions = Array.isArray(s.questions) ? s.questions : [];
  const qList = el("ul", { className: "sugg__questions", attrs: { id: `${titleId}-q` } }, questions.map(questionRow));
  qList.hidden = true;
  const toggle = el("button", {
    className: "btn btn--text sugg__toggle",
    attrs: { type: "button", "aria-expanded": "false", "aria-controls": `${titleId}-q` },
  });
  const setToggle = (open) => {
    toggle.setAttribute("aria-expanded", String(open));
    toggle.replaceChildren(el("span", { text: open ? "접기" : "펼치기" }), icon(open ? "chevron-up" : "chevron-down"));
    qList.hidden = !open;
    drawIcons();
  };
  toggle.addEventListener("click", () => setToggle(toggle.getAttribute("aria-expanded") !== "true"));
  setToggle(false);
  if (!questions.length) toggle.hidden = true;

  const meta = el("p", { className: "sugg__meta", text: `근거 질문 ${fmt(s.count)}건 · 최근 ${month(s.lastAt)}` });

  // 상태 선택: 바꾸면 바로 저장(되돌릴 수 있는 동작이라 확인 대화상자 없음, 5-10)
  const selectId = `${titleId}-status`;
  const select = el("select", { className: "input sugg__select", attrs: { id: selectId } },
    STATUSES.map((st) => el("option", { text: st, attrs: { value: st } })));
  select.value = STATUSES.includes(s.status) ? s.status : "새로 옴";
  select.addEventListener("change", async () => {
    const before = s.status;
    const next = select.value;
    select.disabled = true;
    const res = await setSuggestionStatus(s.id, next);
    select.disabled = false;
    if (res && res.ok) {
      s.status = next;
      toast(`상태를 「${next}」(으)로 바꿨어요`);
      if (onChanged) onChanged(s);
    } else {
      select.value = before;
      toast((res && res.error) || "상태를 바꾸지 못했어요. 다시 시도해 주세요", "circle-alert");
    }
  });
  const statusField = el("div", { className: "sugg__status" }, [
    el("label", { className: "field__label", text: "상태", attrs: { for: selectId } }),
    select,
  ]);

  return el("article", { className: "card sugg", attrs: { "aria-labelledby": titleId } }, [
    top,
    el("h3", { className: "sugg__title", text: s["제목"] || "–", attrs: { id: titleId } }),
    ai,
    el("div", { className: "sugg__foot" }, [el("div", { className: "sugg__evidence" }, [meta, toggle]), statusField]),
    qList,
  ]);
}

// 근거 질문 한 줄: 날짜 · 학과 · 칸 + 질문 원문(학번 없음, PRD 5-3)
function questionRow(q) {
  const metaBits = [day(q.at), q["학과"], q["칸"]].filter(Boolean).join(" · ");
  return el("li", { className: "sugg__q" }, [
    el("p", { className: "sugg__q-meta", text: metaBits || "–" }),
    el("p", { className: "sugg__q-text", text: q["질문"] || "–" }),
  ]);
}

// "2026-10-21T20:41:04+09:00" → "2026-10-21" / "2026-10"
const day = (iso) => (/^\d{4}-\d{2}-\d{2}/.exec(String(iso || "")) || [""])[0];
const month = (iso) => (/^\d{4}-\d{2}/.exec(String(iso || "")) || ["–"])[0];

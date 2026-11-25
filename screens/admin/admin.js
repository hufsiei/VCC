// 관리자 콘솔 공통(PRD 5-1, 작업 68): 직원 확인 · 부서·기간 · 탭 전환 · 다시 불러오기.
// 데이터는 common/data.js 함수로만 받는다(fetch 직접 금지).
import { currentUser, logout, getDepartments, getAdminOverview, getAdminSuggestions } from "../../common/data.js";
import { el, drawIcons, errorBox } from "./ui.js";
import { renderDemand, renderDemandLoading } from "./tab1.js";
import { renderSuggest, renderSuggestLoading } from "./tab2.js";
import { loadReport } from "./tab3.js";

const $ = (id) => document.getElementById(id);
const me = currentUser();

$("gateLogin").addEventListener("click", () => {
  logout(); // 학생으로 로그인돼 있으면 로그인 화면이 인터BOO로 돌려보내므로 먼저 로그아웃
  location.href = "../login/";
});

if (!me || me.status !== "직원") {
  $("gate").hidden = false;
} else {
  start();
}
drawIcons();

async function start() {
  const isDept = me["권한"] === "부서";
  $("who").textContent = isDept ? `${me["부서명"] || "부서"} 담당자` : "총괄 관리자";
  $("logoutBtn").hidden = false;
  $("logoutBtn").addEventListener("click", () => {
    logout();
    location.href = "../login/";
  });
  $("main").hidden = false;

  // seq: 탭마다 마지막 요청 번호(부서를 빨리 바꿔도 마지막 선택만 그린다) / stale: 다시 불러와야 하는 탭
  const state = { dept: "ALL", period: readPeriod(), tab: "demand", seq: {}, stale: { demand: true, suggest: true, report: true } };

  // 부서 드롭다운: 「전체」 + 부서 목록. 부서 담당자는 자기 부서로 고정(비활성 + 이유, 5-4)
  const deptSelect = $("deptSelect");
  const res = await getDepartments();
  const departments = (res && Array.isArray(res.departments)) ? res.departments : [];
  const fixed = (res && res.fixed) || (isDept ? me["부서코드"] : null);
  if (fixed) {
    const d = departments.find((x) => x["부서코드"] === fixed);
    deptSelect.append(el("option", { text: (d && d["부서명"]) || me["부서명"] || fixed, attrs: { value: fixed } }));
    deptSelect.disabled = true;
    $("deptReason").hidden = false;
    state.dept = fixed;
  } else {
    deptSelect.append(el("option", { text: "전체", attrs: { value: "ALL" } }));
    for (const d of departments) deptSelect.append(el("option", { text: d["부서명"], attrs: { value: d["부서코드"] } }));
  }
  const deptNames = Object.fromEntries(departments.map((d) => [d["부서코드"], d["부서명"]]));
  if (fixed && !deptNames[fixed] && me["부서명"]) deptNames[fixed] = me["부서명"];

  // 부서·기간이 바뀌면 모든 탭이 낡는다 → 지금 탭만 바로, 나머지는 열 때 불러온다
  const refresh = () => {
    state.stale = { demand: true, suggest: true, report: true };
    load(state.tab);
  };
  deptSelect.addEventListener("change", () => { state.dept = deptSelect.value; refresh(); });
  $("periodSelect").addEventListener("change", () => { state.period = readPeriod(); refresh(); });

  // 탭 전환(같은 화면 안)
  const tabs = [...document.querySelectorAll(".console-tab")];
  for (const t of tabs) {
    t.addEventListener("click", () => {
      state.tab = t.dataset.tab;
      for (const x of tabs) {
        const on = x === t;
        x.setAttribute("aria-selected", String(on));
        $(x.getAttribute("aria-controls")).hidden = !on;
      }
      if (state.stale[state.tab]) load(state.tab);
    });
  }

  function load(tab) {
    if (tab === "demand") return loadDemand();
    if (tab === "suggest") return loadSuggest();
    if (tab === "report") return loadReportTab();
  }

  async function loadDemand() {
    const my = state.seq.demand = (state.seq.demand || 0) + 1;
    state.stale.demand = false;
    const panel = $("panel-demand");
    renderDemandLoading(panel);
    const data = await getAdminOverview(state.dept, state.period);
    if (my !== state.seq.demand) return;
    if (!data || data.error || !data.kpi) {
      panel.removeAttribute("aria-busy");
      panel.replaceChildren(errorBox(data && data.error, loadDemand));
      $("computedAt").textContent = "";
    } else {
      renderDemand(panel, data, { dept: state.dept });
      $("computedAt").textContent = data.computedAt ? `마지막 집계 ${timeText(data.computedAt)}` : "";
    }
    drawIcons();
  }

  async function loadSuggest() {
    const my = state.seq.suggest = (state.seq.suggest || 0) + 1;
    state.stale.suggest = false;
    const panel = $("panel-suggest");
    renderSuggestLoading(panel);
    const data = await getAdminSuggestions(state.dept, state.period);
    if (my !== state.seq.suggest) return;
    if (!data || data.error || !Array.isArray(data.suggestions)) {
      panel.removeAttribute("aria-busy");
      panel.replaceChildren(errorBox(data && data.error, loadSuggest));
    } else {
      // 상태를 바꾸면 탭1 KPI 「개선 요청」(새로 옴 건수)이 달라진다 → 탭1을 다음에 열 때 다시 불러온다
      renderSuggest(panel, data, { deptNames, onChanged: () => { state.stale.demand = true; } });
    }
    drawIcons();
  }

  // 탭3: 발행 설정·이력은 부서별(기간은 「지금 발행」에만 쓰임). 부서 담당자는 받은 리포트만
  function loadReportTab() {
    const my = state.seq.report = (state.seq.report || 0) + 1;
    state.stale.report = false;
    const sel = $("periodSelect");
    const ctx = {
      dept: state.dept,
      deptName: state.dept === "ALL" ? "전체" : (deptNames[state.dept] || state.dept),
      deptNames,
      period: state.period,
      periodLabel: sel.selectedOptions[0] ? sel.selectedOptions[0].textContent : "",
      isDept,
    };
    return loadReport($("panel-report"), ctx, () => my === state.seq.report);
  }

  load("demand");
}

function readPeriod() {
  const [type, value] = $("periodSelect").value.split(":");
  return { type, value };
}

// "2026-11-21T10:00:00+09:00" → "2026-11-21 10:00"
function timeText(iso) {
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(String(iso));
  return m ? `${m[1]} ${m[2]}` : String(iso);
}

// 관리자 콘솔 공통(PRD 5-1, 작업 68): 직원 확인 · 부서·기간 · 탭 전환 · 다시 불러오기.
// 데이터는 common/data.js 함수로만 받는다(fetch 직접 금지).
import { currentUser, logout, getDepartments, getAdminOverview } from "../../common/data.js";
import { el, icon, drawIcons, errorBox } from "./ui.js";
import { renderDemand, renderDemandLoading } from "./tab1.js";

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

  const state = { dept: "ALL", period: readPeriod(), tab: "demand", seq: 0 };

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
  deptSelect.addEventListener("change", () => { state.dept = deptSelect.value; load(); });
  $("periodSelect").addEventListener("change", () => { state.period = readPeriod(); load(); });

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
      if (state.tab !== "demand") renderLater($(t.getAttribute("aria-controls")), t.textContent);
    });
  }

  async function load() {
    const my = ++state.seq; // 부서를 빨리 바꿔도 마지막 선택만 그린다
    const panel = $("panel-demand");
    renderDemandLoading(panel);
    const data = await getAdminOverview(state.dept, state.period);
    if (my !== state.seq) return;
    if (!data || data.error || !data.kpi) {
      panel.removeAttribute("aria-busy");
      panel.replaceChildren(errorBox(data && data.error, load));
      $("computedAt").textContent = "";
    } else {
      renderDemand(panel, data, { dept: state.dept });
      $("computedAt").textContent = data.computedAt ? `마지막 집계 ${timeText(data.computedAt)}` : "";
    }
    drawIcons();
  }

  load();
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

// 탭2·3은 다음 작업(11/26~) — 자리만
function renderLater(panel, name) {
  if (panel.childElementCount) return;
  panel.append(el("div", { className: "card empty" }, [
    icon("clock"),
    el("p", { className: "empty__title", text: `${name} 화면을 만들고 있어요` }),
    el("p", { className: "sub", text: "수요 현황 탭에서 부서별 질문을 먼저 볼 수 있어요." }),
  ]));
  drawIcons();
}

const tg = window.Telegram?.WebApp;

const STORAGE_KEY = "marcus-memento-app:v2";
const LIFE_EXPECTANCY_YEARS = 90;
const WEEKS_PER_YEAR = 52;
const TOTAL_LIFE_WEEKS = LIFE_EXPECTANCY_YEARS * WEEKS_PER_YEAR;
const MS_PER_WEEK = 7 * 24 * 60 * 60 * 1000;
const todayKey = getLocalDateKey();

const agents = {
  aurelius: {
    icon: "♜",
    name: "Марк Аврелий",
    role: "Мудрец-психолог",
    description: "Спокойная мудрость",
    advice: "Отдели факт от суждения. Затем выбери поступок, которым сможешь уважать себя.",
  },
  machiavelli: {
    icon: "♞",
    name: "Макиавелли",
    role: "Бизнес-тактик",
    description: "Холодная стратегия",
    advice: "Назови цель, рычаг влияния и следующий ход. Тактика начинается с позиции.",
  },
  jung: {
    icon: "◐",
    name: "Карл Юнг",
    role: "Аналитик тени",
    description: "Глубокая тень",
    advice: "Спроси, какую часть себя ты не хочешь видеть. Там часто начинается рост.",
  },
};

const state = loadState();
applyRegistrationParams();
const initialView = getInitialView();

const elements = {
  agentRail: document.querySelector("#agentRail"),
  askForm: document.querySelector("#askForm"),
  askInput: document.querySelector("#askInput"),
  assistantName: document.querySelector("#assistantName"),
  assistantSheet: document.querySelector("#assistantSheet"),
  assistantText: document.querySelector("#assistantText"),
  birthDateInput: document.querySelector("#birthDateInput"),
  closeGoalButton: document.querySelector("#closeGoalButton"),
  diaryCount: document.querySelector("#diaryCount"),
  diaryForm: document.querySelector("#diaryForm"),
  diaryInput: document.querySelector("#diaryInput"),
  diaryList: document.querySelector("#diaryList"),
  goalForm: document.querySelector("#goalForm"),
  goalInput: document.querySelector("#goalInput"),
  goalStatus: document.querySelector("#goalStatus"),
  lifeGrid: document.querySelector("#lifeGrid"),
  lifePercent: document.querySelector("#lifePercent"),
  mementoAge: document.querySelector("#mementoAge"),
  mementoForm: document.querySelector("#mementoForm"),
  mementoText: document.querySelector("#mementoText"),
  mementoTitle: document.querySelector("#mementoTitle"),
  memoryList: document.querySelector("#memoryList"),
  profileCompletion: document.querySelector("#profileCompletion"),
  profileLanguage: document.querySelector("#profileLanguage"),
  profilePlan: document.querySelector("#profilePlan"),
  profileProgressBar: document.querySelector("#profileProgressBar"),
  profileSheet: document.querySelector("#profileSheet"),
  profileSheetBody: document.querySelector("#profileSheetBody"),
  profileSheetTitle: document.querySelector("#profileSheetTitle"),
  subscriptionBadge: document.querySelector("#subscriptionBadge"),
  startAgentDialogButton: document.querySelector("#startAgentDialogButton"),
  tokenCount: document.querySelector("#tokenCount"),
  profileAgent: document.querySelector("#profileAgent"),
  weeksLeft: document.querySelector("#weeksLeft"),
  weeksLived: document.querySelector("#weeksLived"),
};

tg?.ready();
tg?.expand();
tg?.setHeaderColor?.("#070706");
tg?.setBackgroundColor?.("#070706");

elements.birthDateInput.max = todayKey;
renderAll();
bindEvents();
openView(initialView);

function bindEvents() {
  document.body.addEventListener("click", (event) => {
    const tabButton = event.target.closest("[data-tab]");
    const actionButton = event.target.closest("[data-action]");

    if (tabButton) {
      openView(tabButton.dataset.tab);
      haptic("selection");
      return;
    }

    if (!actionButton) return;
    runAction(actionButton.dataset.action, actionButton);
  });

  elements.mementoForm.addEventListener("submit", (event) => {
    event.preventDefault();
    state.birthDate = elements.birthDateInput.value;
    saveState();
    renderAll();
    haptic("impact");
  });

  elements.goalForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = elements.goalInput.value.trim();
    if (!text) return;

    state.goal = {
      id: createId(),
      text,
      createdAt: new Date().toISOString(),
      status: "active",
    };
    elements.goalInput.value = "";
    saveState();
    sendGoalToBot("goal_set", state.goal);
    renderAll();
    showAnswer("Цель поставлена. Я буду напоминать о ней каждый день, пока ты ее не закроешь.");
  });

  elements.diaryForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = elements.diaryInput.value.trim();
    if (!text) return;

    state.diary = [
      {
        id: createId(),
        text,
        createdAt: new Date().toISOString(),
      },
      ...(state.diary ?? []),
    ].slice(0, 30);

    elements.diaryInput.value = "";
    saveState();
    renderDiary();
    showAnswer("Запись сохранена. Это уже не просто мысль в голове, а след твоего пути.");
  });

  elements.askForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const question = elements.askInput.value.trim();
    elements.askInput.value = "";
    requestAgentAdvice(question);
  });
}

function runAction(action, button) {
  const actions = {
    close: () => tg?.close?.(),
    "close-sheet": () => closeSheet(),
    "close-profile-sheet": () => closeProfileSheet(),
    "close-goal": () => closeGoal(),
    "delete-diary-entry": () => deleteDiaryEntry(button.dataset.id),
    "diary-prompt": () => applyDiaryPrompt(button.dataset.prompt),
    "open-sheet": () => openProfileSheet(button.dataset.sheet),
    "select-agent": () => selectAgent(button.dataset.agent),
    "start-agent-dialog": () => startAgentDialog(),
    "agent-advice": () => requestAgentAdvice(),
  };

  actions[action]?.();
}

function openView(viewName) {
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("is-active", view.dataset.view === viewName);
  });

  document.querySelectorAll(".bottom-nav [data-tab]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.tab === viewName);
  });
}

function renderAll() {
  renderAgents();
  renderMemento();
  renderGoal();
  renderDiary();
  renderProfile();
}

function renderAgents() {
  elements.agentRail.innerHTML = Object.entries(agents)
    .map(([id, agent]) => {
      const activeClass = state.activeAgent === id ? " is-active" : "";
      return `
        <article class="quote-card agent-card${activeClass}" data-action="select-agent" data-agent="${id}">
          <span class="agent-mark">${agent.icon}</span>
          <h3>${agent.name}</h3>
          <small>${agent.role}</small>
        </article>
      `;
    })
    .join("");
}

function renderMemento() {
  elements.birthDateInput.value = state.birthDate || "";

  if (!state.birthDate) {
    updateMementoSummary({ weeksLived: 0, weeksLeft: TOTAL_LIFE_WEEKS, percent: 0, age: 0 });
    elements.mementoTitle.textContent = "Дата рождения придет из регистрации";
    elements.mementoText.textContent = `Если даты еще нет, введи ее здесь. Всего ${TOTAL_LIFE_WEEKS} недель до ${LIFE_EXPECTANCY_YEARS} лет.`;
    renderLifeGrid(0);
    return;
  }

  const stats = calculateLifeStats(state.birthDate);
  updateMementoSummary(stats);
  renderLifeGrid(stats.weeksLived);

  if (stats.isFutureDate) {
    elements.mementoTitle.textContent = "Дата еще не наступила";
    elements.mementoText.textContent = "Выбери дату рождения в прошлом, чтобы увидеть календарь жизни.";
    return;
  }

  if (stats.weeksLeft <= 0) {
    elements.mementoTitle.textContent = "90-летний горизонт пройден";
    elements.mementoText.textContent = "Каждый следующий день уже сверх плана. Используй его честно.";
    return;
  }

  elements.mementoTitle.textContent = `${stats.weeksLeft.toLocaleString("ru")} недель до 90 лет`;
  elements.mementoText.textContent = `Примерная дата 90-летия: ${formatDateOnly(stats.ninetiethBirthday)}.`;
}

function renderGoal() {
  const activeGoal = state.goal?.status === "active" ? state.goal : null;
  elements.goalStatus.textContent = activeGoal
    ? `Активная цель: ${activeGoal.text}`
    : "Активной цели пока нет.";
  elements.closeGoalButton.hidden = !activeGoal;
}

function renderDiary() {
  if (!elements.diaryList) return;
  const entries = state.diary ?? [];
  elements.diaryCount.textContent = String(entries.length);

  if (!entries.length) {
    elements.diaryList.innerHTML = `
      <article class="diary-empty">
        <strong>Пока нет записей</strong>
        <p>Начни с одного честного наблюдения: что сегодня заслуживает твоего времени?</p>
      </article>
    `;
    return;
  }

  elements.diaryList.innerHTML = entries
    .map((entry) => {
      const date = formatDiaryDate(entry.createdAt);
      return `
        <article class="diary-card">
          <div>
            <span>${date}</span>
            <button type="button" data-action="delete-diary-entry" data-id="${escapeAttr(entry.id)}" aria-label="Удалить запись">×</button>
          </div>
          <p>${escapeHtml(entry.text)}</p>
        </article>
      `;
    })
    .join("");
}

function applyDiaryPrompt(prompt = "") {
  if (!elements.diaryInput) return;
  elements.diaryInput.value = prompt;
  elements.diaryInput.focus();
}

function deleteDiaryEntry(id) {
  state.diary = (state.diary ?? []).filter((entry) => entry.id !== id);
  saveState();
  renderDiary();
}

function getProfileCompletion() {
  const fields = [
    state.name,
    state.gender,
    getAgeLabel(),
    state.birthDate,
    state.location || state.country,
    state.activity,
    state.interests,
    state.mainGoal || activeGoalText(),
    state.currentProblem,
  ];
  const filled = fields.filter(Boolean).length;
  return Math.round((filled / fields.length) * 100);
}

function getAgeLabel() {
  if (state.manualAge) return state.manualAge;
  if (!state.birthDate) return "";
  return String(calculateLifeStats(state.birthDate).age);
}

function activeGoalText() {
  return state.goal?.status === "active" ? state.goal.text : "";
}

function renderProfile() {
  const agent = getActiveAgent();
  const completion = getProfileCompletion();

  if (elements.profileAgent) {
    elements.profileAgent.textContent = `${agent.icon} Агент: ${agent.name}`;
  }
  elements.profileLanguage.textContent = state.language === "en" ? "English" : "Русский";
  elements.profilePlan.textContent = state.plan;
  elements.subscriptionBadge.textContent = state.plan;
  elements.tokenCount.textContent = String(state.tokens);
  elements.profileCompletion.textContent = `${completion}%`;
  elements.profileProgressBar.style.width = `${completion}%`;

  renderMemoryList();
}

function renderMemoryList() {
  const rows = [
    ["Имя", state.name],
    ["Пол", state.gender],
    ["Возраст", getAgeLabel()],
    ["Дата рождения", formatBirthDateLabel(state.birthDate)],
    ["Локация", state.location || state.country],
    ["Вид деятельности", state.activity],
    ["Интересы", state.interests],
    ["Главная цель", state.mainGoal || activeGoalText()],
    ["Текущая проблема", state.currentProblem],
  ];

  elements.memoryList.innerHTML = rows
    .map(([label, value]) => {
      const filled = Boolean(value);
      return `
        <article class="${filled ? "" : "is-empty"}">
          <span>${label}</span>
          <strong>${filled ? escapeHtml(String(value)) : "Не указано"}</strong>
          ${filled ? "" : "<small>Добавьте, чтобы Marcus давал точнее советы</small>"}
        </article>
      `;
    })
    .join("");
}

function openProfileSheet(sheetName) {
  const renderers = {
    about: renderAboutSheet,
    language: () => renderSimpleSheet("Язык", "Язык интерфейса синхронизируется с регистрацией в боте. Сейчас выбран: " + elements.profileLanguage.textContent),
    "profile-menu": () => renderSimpleSheet("Меню", "Здесь позже появятся настройки безопасности, экспорт данных и история решений."),
    subscription: renderSubscriptionSheet,
    tokens: () => renderSimpleSheet("Мои токены", `Доступно токенов: ${state.tokens}. Токены расходуются на глубокие разборы и расширенную память.`),
  };

  renderers[sheetName]?.();
  elements.profileSheet.hidden = false;
}

function closeProfileSheet() {
  elements.profileSheet.hidden = true;
}

function renderSimpleSheet(title, text) {
  elements.profileSheetTitle.textContent = title;
  elements.profileSheetBody.innerHTML = `<p class="sheet-copy">${text}</p>`;
}

function renderSubscriptionSheet() {
  elements.profileSheetTitle.textContent = "Подписка";
  elements.profileSheetBody.innerHTML = `
    <div class="sheet-stack">
      <p class="sheet-copy">Текущий тариф: <strong>${state.plan}</strong></p>
      <button class="sheet-primary" type="button" data-sheet-save="plan">Улучшить до Pro</button>
    </div>
  `;
  elements.profileSheetBody.querySelector("[data-sheet-save='plan']").addEventListener("click", () => {
    state.plan = "Pro";
    saveState();
    renderProfile();
    closeProfileSheet();
  });
}

function renderAboutSheet() {
  elements.profileSheetTitle.textContent = "О вас";
  elements.profileSheetBody.innerHTML = `
    <form class="sheet-form" id="aboutForm">
      <label>Имя<input name="name" value="${escapeAttr(state.name)}" /></label>
      <label>Пол<input name="gender" value="${escapeAttr(state.gender)}" /></label>
      <label>Возраст<input name="age" value="${escapeAttr(getAgeLabel())}" /></label>
      <label>Локация<input name="location" value="${escapeAttr(state.location || state.country)}" /></label>
      <label>Деятельность<input name="activity" value="${escapeAttr(state.activity)}" /></label>
      <label>Интересы<textarea name="interests">${escapeHtml(state.interests)}</textarea></label>
      <label>Цели<textarea name="mainGoal">${escapeHtml(state.mainGoal)}</textarea></label>
      <label>Проблемы<textarea name="currentProblem">${escapeHtml(state.currentProblem)}</textarea></label>
      <button type="submit">Сохранить память</button>
    </form>
  `;
  elements.profileSheetBody.querySelector("#aboutForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    state.name = form.get("name").trim();
    state.gender = form.get("gender").trim();
    state.manualAge = form.get("age").trim();
    state.location = form.get("location").trim();
    state.activity = form.get("activity").trim();
    state.interests = form.get("interests").trim();
    state.mainGoal = form.get("mainGoal").trim();
    state.currentProblem = form.get("currentProblem").trim();
    saveState();
    renderProfile();
    closeProfileSheet();
  });
}

async function requestAgentAdvice(question = "") {
  const agent = getActiveAgent();

  if (state.activeAgent !== "aurelius") {
    showAnswer(agent.advice);
    return;
  }

  showAnswer("Марк Аврелий размышляет...");

  try {
    const response = await fetch("/api/agent/aurelius", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: question || "Дай мне короткий стоический совет на сегодня.",
        profile: {
          name: state.name,
          age: getAgeLabel(),
          location: state.location || state.country,
          interests: state.interests,
          mainGoal: state.mainGoal || activeGoalText(),
          currentProblem: state.currentProblem,
        },
        diary: (state.diary ?? []).slice(0, 3).map((entry) => entry.text),
      }),
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Gemini request failed");
    }

    showAnswer(data.answer || agent.advice);
  } catch (error) {
    console.warn(error);
    showAnswer(`Gemini пока недоступен. ${agent.advice}`);
  }
}

function selectAgent(agentId) {
  if (!agents[agentId]) return;
  state.activeAgent = agentId;
  saveState();
  renderAll();
  showAnswer(`${agents[agentId].name} выбран. Начни диалог, и общение продолжится в Telegram-боте.`, {
    canStartDialog: true,
  });
}

function startAgentDialog() {
  void startAgentDialogFromMiniApp();
}

async function startAgentDialogFromMiniApp() {
  const agent = getActiveAgent();
  const payload = {
    agentId: state.activeAgent,
    initData: tg?.initData || "",
  };

  try {
    if (!payload.initData) {
      throw new Error("Telegram initData is unavailable");
    }

    const response = await fetch("/api/start-agent-dialog", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Could not start agent dialog");
    }

    showAnswer(`Диалог с ${agent.name} открыт в Telegram-боте.`);
    if (data.botUsername && tg?.openTelegramLink) {
      setTimeout(() => tg.openTelegramLink(`https://t.me/${data.botUsername}`), 450);
    } else {
      setTimeout(() => tg?.close?.(), 450);
    }
  } catch (error) {
    console.warn(error);
    showAnswer("Диалог можно начать только внутри Telegram Mini App, открытого из этого бота.");
  }
}

function closeGoal() {
  if (!state.goal) return;
  state.goal.status = "closed";
  state.goal.closedAt = new Date().toISOString();
  saveState();
  sendGoalToBot("goal_close", state.goal);
  renderAll();
  showAnswer("Цель закрыта. Напоминания остановлены.");
}

function sendGoalToBot(type, goal) {
  const payload = {
    type,
    goalId: goal.id,
    goalText: goal.text,
    createdAt: goal.createdAt,
    closedAt: goal.closedAt || "",
  };

  try {
    tg?.sendData?.(JSON.stringify(payload));
  } catch {
    // In browser preview outside Telegram this is intentionally unavailable.
  }
}

function showAnswer(text, options = {}) {
  const agent = getActiveAgent();
  elements.assistantName.textContent = agent.name;
  elements.assistantText.textContent = text;
  elements.startAgentDialogButton.hidden = !options.canStartDialog;
  elements.assistantSheet.hidden = false;
  haptic("impact");
}

function closeSheet() {
  elements.assistantSheet.hidden = true;
}

function getActiveAgent() {
  return agents[state.activeAgent] ?? agents.aurelius;
}

function updateMementoSummary({ weeksLived, weeksLeft, percent, age }) {
  elements.weeksLived.textContent = weeksLived.toLocaleString("ru");
  elements.weeksLeft.textContent = weeksLeft.toLocaleString("ru");
  elements.lifePercent.textContent = `${percent}%`;
  elements.mementoAge.textContent = age;
}

function renderLifeGrid(weeksLived) {
  const currentWeek = Math.min(Math.max(weeksLived, 0), TOTAL_LIFE_WEEKS - 1);
  let markup = "";

  for (let startYear = 0; startYear < LIFE_EXPECTANCY_YEARS; startYear += 5) {
    const endYear = Math.min(startYear + 5, LIFE_EXPECTANCY_YEARS);
    const startWeek = startYear * WEEKS_PER_YEAR;
    const endWeek = endYear * WEEKS_PER_YEAR;
    let weekMarkup = "";

    for (let week = startWeek; week < endWeek; week += 1) {
      const className = week < weeksLived ? "life-week is-lived" : week === currentWeek ? "life-week is-current" : "life-week";
      const year = Math.floor(week / WEEKS_PER_YEAR) + 1;
      const weekInYear = (week % WEEKS_PER_YEAR) + 1;
      weekMarkup += `<span class="${className}" title="Год ${year}, неделя ${weekInYear}"></span>`;
    }

    markup += `
      <div class="life-era">
        <div class="life-era-grid">${weekMarkup}</div>
        <span class="life-era-age">${endYear}</span>
      </div>
    `;
  }

  elements.lifeGrid.innerHTML = markup;
}

function calculateLifeStats(birthDateValue) {
  const birthDate = parseLocalDate(birthDateValue);
  const now = new Date();
  const isFutureDate = birthDate > now;
  const rawWeeksLived = isFutureDate ? 0 : Math.floor((now - birthDate) / MS_PER_WEEK);
  const weeksLived = clamp(rawWeeksLived, 0, TOTAL_LIFE_WEEKS);
  const weeksLeft = Math.max(TOTAL_LIFE_WEEKS - weeksLived, 0);
  const percent = Math.min(100, Math.round((weeksLived / TOTAL_LIFE_WEEKS) * 100));
  const age = isFutureDate ? 0 : calculateAge(birthDate, now);
  const ninetiethBirthday = new Date(birthDate);
  ninetiethBirthday.setFullYear(ninetiethBirthday.getFullYear() + LIFE_EXPECTANCY_YEARS);

  return { age, isFutureDate, ninetiethBirthday, percent, weeksLeft, weeksLived };
}

function applyRegistrationParams() {
  const params = new URLSearchParams(window.location.search);
  const registration = {
    birthDate: params.get("birthDate") || "",
    country: params.get("country") || "",
    language: params.get("lang") || "",
    manualAge: params.get("age") || "",
    name: params.get("name") || "",
  };

  Object.entries(registration).forEach(([key, value]) => {
    if (value) state[key] = value;
  });

  if (registration.country) {
    state.location = registration.country;
  }

  if (Object.values(registration).some(Boolean)) {
    saveState();
  }
}

function formatBirthDateLabel(value) {
  if (!value) return "";
  return formatDateOnly(parseLocalDate(value));
}

function getInitialView() {
  const view = new URLSearchParams(window.location.search).get("view");
  return ["home", "calendar", "profile"].includes(view) ? view : "home";
}

function loadState() {
  const defaults = {
    activeAgent: "aurelius",
    birthDate: "",
    country: "",
    activity: "",
    currentProblem: "",
    diary: [],
    gender: "",
    goal: null,
    interests: "",
    language: "ru",
    location: "",
    mainGoal: "",
    manualAge: "",
    name: "",
    plan: "Basic",
    tokens: 120,
  };

  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return { ...defaults, ...saved };
  } catch {
    return defaults;
  }
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function createId() {
  return crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getInitial(name) {
  return (name.trim()[0] || "M").toUpperCase();
}

function getLocalDateKey() {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDateOnly(value) {
  return new Intl.DateTimeFormat("ru", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  }).format(value);
}

function formatDiaryDate(value) {
  const date = new Date(value);
  return new Intl.DateTimeFormat("ru", {
    day: "2-digit",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function parseLocalDate(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function calculateAge(birthDate, now) {
  let age = now.getFullYear() - birthDate.getFullYear();
  const hasBirthdayPassed =
    now.getMonth() > birthDate.getMonth() ||
    (now.getMonth() === birthDate.getMonth() && now.getDate() >= birthDate.getDate());

  if (!hasBirthdayPassed) age -= 1;
  return Math.max(age, 0);
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    };
    return entities[char];
  });
}

function escapeAttr(value = "") {
  return escapeHtml(value);
}

function haptic(type) {
  if (type === "selection") {
    tg?.HapticFeedback?.selectionChanged();
    return;
  }
  tg?.HapticFeedback?.impactOccurred("light");
}

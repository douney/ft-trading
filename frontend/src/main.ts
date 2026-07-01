type RuntimeName = "trading" | "recording";
type TabName = RuntimeName | "backtest";

type RuntimeStatus = {
  name: string;
  connected: boolean;
  mode: string | null;
  instruments: string[];
  instrument_labels?: Record<string, string>;
  subscriptions: Array<{
    instrument: string;
    instrument_label?: string;
    timeframe: string;
  }>;
};

type TradingStatus = RuntimeStatus & {
  open_positions: number;
  day_balance: number;
  last_trade_balance: number;
};

type BacktestStatus = {
  name: string;
  running: boolean;
  available: boolean;
};

type Health = {
  broker: {
    connected: boolean;
    mode: string | null;
  };
  open_positions: number;
  day_balance: number;
  last_trade_balance: number;
  subscriptions: Array<{
    instrument: string;
    instrument_label?: string;
    timeframe: string;
  }>;
  trading: TradingStatus;
  recording: RuntimeStatus;
  backtest: BacktestStatus;
};

type Price = {
  runtime: string;
  instrument: string;
  instrument_label?: string;
  bid: number;
  ask: number;
  spread?: number;
  mid: number;
  timestamp_ms: number;
};

type Position = {
  id: string;
  instrument: string;
  instrument_label?: string;
  status: string;
  direction: string;
  level: number;
  size: number;
  currency: string;
  stop_level: number | null;
  limit_level: number | null;
  entry_level: number;
  timestamp_ms: number;
  pnl: number | null;
  max_gain: number;
  max_loss: number;
  stop_out: number | null;
  stop_profit: number | null;
  last_tick: {
    bid: number;
    ask: number;
    mid: number;
    timestamp_ms: number;
  } | null;
};

const pollMs = 1000;
const authTokenKey = "ftTradingAuthToken";
const modeBlockedMessage = "Veuillez vous deconnecter avant de passer a un autre mode.";

let activeTab: TabName = "trading";
let lastHealth: Health | null = null;
let authWaiter: Promise<boolean> | null = null;
let resolveAuthWaiter: ((accepted: boolean) => void) | null = null;
let passphraseWaiter: Promise<string | null> | null = null;
let resolvePassphraseWaiter: ((passphrase: string | null) => void) | null = null;

const els = {
  topbarTime: byId("topbar-time"),
  authPanel: byId("auth-panel"),
  authForm: byId("auth-form") as HTMLFormElement,
  authToken: byId("auth-token") as HTMLInputElement,
  authError: byId("auth-error"),
  messageModal: byId("message-modal"),
  messageTitle: byId("message-title"),
  messageText: byId("message-text"),
  messageClose: byId("message-close") as HTMLButtonElement,
  passphraseModal: byId("passphrase-modal"),
  passphraseForm: byId("passphrase-form") as HTMLFormElement,
  livePassphrase: byId("live-passphrase") as HTMLInputElement,
  passphraseError: byId("passphrase-error"),
  passphraseCancel: byId("passphrase-cancel") as HTMLButtonElement,
  connectionForm: byId("connection-form") as HTMLFormElement,
  brokerMode: byId("broker-mode") as HTMLSelectElement,
  connectionToggle: byId("connection-toggle") as HTMLButtonElement,
  metricOpen: byId("metric-open"),
  metricDay: byId("metric-day"),
  metricLast: byId("metric-last"),
  positions: byId("positions"),
  positionsCount: byId("positions-count"),
  tradingPrices: byId("trading-prices"),
  tradingPricesCount: byId("trading-prices-count"),
  recordingPrices: byId("recording-prices"),
  recordingPricesCount: byId("recording-prices-count"),
  recorderStatus: byId("recorder-status"),
  recorderInstruments: byId("recorder-instruments"),
  backtestStatus: byId("backtest-status"),
};

const tabButtons = Array.from(document.querySelectorAll<HTMLButtonElement>(".tab"));
const tabPages = Array.from(document.querySelectorAll<HTMLElement>(".tab-page"));

function byId(id: string): HTMLElement {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element;
}

function money(value: number | null, currency = ""): string {
  if (value === null || Number.isNaN(value)) {
    return "-";
  }
  return `${value.toFixed(2)} ${currency}`.trim();
}

function numberValue(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  return value.toFixed(2);
}

function spreadValue(price: Price): number | null {
  if (typeof price.spread === "number" && Number.isFinite(price.spread)) {
    return price.spread;
  }
  return price.ask - price.bid;
}

function instrumentLabel(symbol: string, label?: string | null): string {
  return label || symbol;
}

function runtimeInstrumentLabel(runtime: RuntimeStatus, symbol: string): string {
  return instrumentLabel(symbol, runtime.instrument_labels?.[symbol]);
}

function timeValue(timestampMs: number | null): string {
  if (!timestampMs) {
    return "-";
  }
  return new Date(timestampMs).toLocaleTimeString();
}

function runtimeLabel(runtime: RuntimeStatus): string {
  return runtime.connected ? runtime.mode?.toUpperCase() ?? "On" : "Stopped";
}

function updateClock(): void {
  els.topbarTime.textContent = new Date().toLocaleTimeString();
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetchWithAuth(path, init);
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `${path} failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const payload = await response.json() as { detail?: unknown };
    return typeof payload.detail === "string" ? payload.detail : "";
  } catch {
    return "";
  }
}

async function postDistance(path: string, distance: number | null): Promise<void> {
  await fetchJson(path, {
    method: "POST",
    body: JSON.stringify({ distance }),
  });
  await refresh();
}

async function refresh(): Promise<void> {
  const [health, prices, positions] = await Promise.all([
    fetchJson<Health>("/api/health"),
    fetchJson<Price[]>("/api/prices"),
    fetchJson<Position[]>("/api/positions"),
  ]);

  lastHealth = health;

  const connectedRuntime = getConnectedRuntime();
  if (connectedRuntime !== null && activeTab !== connectedRuntime) {
    setActiveTab(connectedRuntime, true);
  }

  renderHealth(health);
  renderPrices(prices);
  renderPositions(positions);
  renderConnectionControls();
}

async function fetchWithAuth(path: string, init?: RequestInit, retried = false): Promise<Response> {
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");

  const token = sessionStorage.getItem(authTokenKey);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(path, { ...init, headers });
  if (response.status === 401 && !retried) {
    sessionStorage.removeItem(authTokenKey);
    if (await requestAuthToken()) {
      return fetchWithAuth(path, init, true);
    }
  }

  return response;
}

async function initAuth(): Promise<boolean> {
  const status = await fetch("/api/auth/status");
  if (!status.ok) {
    throw new Error("Unable to read authentication status");
  }

  const payload = await status.json() as { required?: boolean };
  if (!payload.required || sessionStorage.getItem(authTokenKey)) {
    return true;
  }

  return requestAuthToken();
}

function requestAuthToken(): Promise<boolean> {
  if (authWaiter !== null) {
    return authWaiter;
  }

  els.authToken.value = "";
  els.authError.textContent = "";
  els.authPanel.classList.remove("is-hidden");
  els.authToken.focus();

  authWaiter = new Promise<boolean>((resolve) => {
    resolveAuthWaiter = resolve;
  });

  return authWaiter.finally(() => {
    authWaiter = null;
  });
}

function acceptAuthToken(): void {
  const token = els.authToken.value.trim();
  if (!token) {
    els.authError.textContent = "Token required";
    return;
  }

  sessionStorage.setItem(authTokenKey, token);
  els.authPanel.classList.add("is-hidden");
  els.authError.textContent = "";

  if (resolveAuthWaiter !== null) {
    resolveAuthWaiter(true);
    resolveAuthWaiter = null;
  }
}

function renderHealth(health: Health): void {
  els.metricOpen.textContent = String(health.open_positions);
  els.metricDay.textContent = money(health.day_balance);
  els.metricLast.textContent = money(health.last_trade_balance);
  els.recorderStatus.textContent = runtimeLabel(health.recording);
  els.backtestStatus.textContent = health.backtest.available ? "Available" : "Not available";

  renderRecorderInstruments(health.recording);
}

function renderPrices(prices: Price[]): void {
  renderPriceTable(
    els.tradingPrices,
    els.tradingPricesCount,
    prices.filter((price) => price.runtime === "trading"),
  );
  renderPriceTable(
    els.recordingPrices,
    els.recordingPricesCount,
    prices.filter((price) => price.runtime === "recording"),
  );
}

function renderPriceTable(body: HTMLElement, count: HTMLElement, prices: Price[]): void {
  count.textContent = `${prices.length} instruments`;
  body.innerHTML = "";

  if (prices.length === 0) {
    const row = document.createElement("tr");
    row.innerHTML = `<td colspan="6" class="empty">No prices yet</td>`;
    body.append(row);
    return;
  }

  for (const price of prices) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td title="${price.instrument}">${instrumentLabel(price.instrument, price.instrument_label)}</td>
      <td>${numberValue(price.bid)}</td>
      <td>${numberValue(price.ask)}</td>
      <td>${numberValue(spreadValue(price))}</td>
      <td>${numberValue(price.mid)}</td>
      <td>${timeValue(price.timestamp_ms)}</td>
    `;
    body.append(row);
  }
}

function renderRecorderInstruments(recording: RuntimeStatus): void {
  els.recorderInstruments.innerHTML = "";

  for (const instrument of recording.instruments) {
    const item = document.createElement("div");
    const subscribed = recording.subscriptions.some((sub) => sub.instrument === instrument);
    item.className = `instrument-item ${subscribed ? "is-active" : ""}`.trim();
    item.innerHTML = `
      <span title="${instrument}">${runtimeInstrumentLabel(recording, instrument)}</span>
      <strong>${subscribed ? "Subscribed" : "Waiting"}</strong>
    `;
    els.recorderInstruments.append(item);
  }
}

function renderPositions(positions: Position[]): void {
  els.positionsCount.textContent = `${positions.length} open`;
  els.positions.innerHTML = "";

  if (positions.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No open positions";
    els.positions.append(empty);
    return;
  }

  for (const position of positions) {
    els.positions.append(renderPosition(position));
  }
}

function renderPosition(position: Position): HTMLElement {
  const card = document.createElement("article");
  card.className = "position-card";

  const pnlClass = position.pnl !== null && position.pnl >= 0 ? "pnl-positive" : "pnl-negative";
  card.innerHTML = `
    <div class="position-header">
      <h3 title="${position.instrument}">${instrumentLabel(position.instrument, position.instrument_label)}</h3>
      <span class="badge">${position.direction}</span>
    </div>
    <div class="grid">
      ${field("Status", position.status)}
      ${field("Opened", timeValue(position.timestamp_ms))}
      ${field("Level", numberValue(position.level))}
      ${field("Size", numberValue(position.size))}
      ${field("PnL", `<span class="${pnlClass}">${money(position.pnl, position.currency)}</span>`)}
      ${field("Max Gain", money(position.max_gain, position.currency))}
      ${field("Max Loss", money(position.max_loss, position.currency))}
      ${field("Stop Out", numberValue(position.stop_out))}
      ${field("Stop", numberValue(position.stop_level))}
      ${field("Limit", numberValue(position.limit_level))}
    </div>
  `;

  const controls = document.createElement("div");
  controls.className = "controls";
  controls.append(
    controlRow("Limit", [10, 20, 50, null], (value) => postDistance(`/api/positions/${position.id}/limit`, value)),
    controlRow("Profit", [1, 2, 4, 6, -50, null], (value) => postDistance(`/api/positions/${position.id}/stop-profit`, value), "profit"),
  );

  const actions = document.createElement("div");
  actions.className = "actions";
  const close = document.createElement("button");
  close.className = "danger";
  close.type = "button";
  close.textContent = "Close";
  close.addEventListener("click", async () => {
    await fetchJson(`/api/positions/${position.id}/close`, { method: "POST" });
    await refresh();
  });
  actions.append(close);

  card.append(controls, actions);
  return card;
}

function field(label: string, value: string): string {
  return `
    <div class="field">
      <span>${label}</span>
      <strong>${value}</strong>
    </div>
  `;
}

function controlRow(
  label: string,
  values: Array<number | null>,
  onClick: (value: number | null) => Promise<void>,
  className = "",
): HTMLElement {
  const row = document.createElement("div");
  row.className = "control-row";

  const rowLabel = document.createElement("label");
  rowLabel.textContent = label;

  const group = document.createElement("div");
  group.className = `button-group ${className}`.trim();

  for (const value of values) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = value === null ? "None" : value < 0 ? `${Math.abs(value)}%` : String(value);
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await onClick(value);
      } finally {
        button.disabled = false;
      }
    });
    group.append(button);
  }

  row.append(rowLabel, group);
  return row;
}

async function toggleActiveRuntime(): Promise<void> {
  if (activeTab === "backtest") {
    return;
  }

  const runtime = activeTab;
  const status = getRuntimeStatus(runtime);
  if (status.connected) {
    await stopRuntime(runtime);
  } else {
    await startRuntime(runtime);
  }
}

async function startRuntime(runtime: RuntimeName): Promise<void> {
  const connectedRuntime = getConnectedRuntime();
  if (connectedRuntime !== null && connectedRuntime !== runtime) {
    showModeBlocked();
    return;
  }

  const mode = els.brokerMode.value;
  const passphrase = await getPassphrase(mode);
  if (mode === "live" && passphrase === null) {
    return;
  }

  await fetchJson(`/api/${runtime}/connect`, {
    method: "POST",
    body: JSON.stringify({
      mode,
      passphrase,
    }),
  });

  await refresh();
}

async function stopRuntime(runtime: RuntimeName): Promise<void> {
  await fetchJson(`/api/${runtime}/stop`, { method: "POST" });
  await refresh();
}

function getRuntimeStatus(runtime: RuntimeName): RuntimeStatus {
  if (lastHealth === null) {
    return {
      name: runtime,
      connected: false,
      mode: null,
      instruments: [],
      subscriptions: [],
    };
  }

  return lastHealth[runtime];
}

function getConnectedRuntime(): RuntimeName | null {
  if (lastHealth?.trading.connected) {
    return "trading";
  }
  if (lastHealth?.recording.connected) {
    return "recording";
  }
  return null;
}

async function getPassphrase(mode: string): Promise<string | null> {
  if (mode !== "live") {
    return null;
  }

  return requestLivePassphrase();
}

function requestLivePassphrase(): Promise<string | null> {
  if (passphraseWaiter !== null) {
    return passphraseWaiter;
  }

  els.livePassphrase.value = "";
  els.passphraseError.textContent = "";
  els.passphraseModal.classList.remove("is-hidden");
  els.livePassphrase.focus();

  passphraseWaiter = new Promise<string | null>((resolve) => {
    resolvePassphraseWaiter = resolve;
  });

  return passphraseWaiter.finally(() => {
    passphraseWaiter = null;
  });
}

function acceptLivePassphrase(): void {
  const passphrase = els.livePassphrase.value;
  if (!passphrase) {
    els.passphraseError.textContent = "Passphrase required";
    return;
  }

  closePassphraseModal(passphrase);
}

function closePassphraseModal(passphrase: string | null): void {
  els.livePassphrase.value = "";
  els.passphraseModal.classList.add("is-hidden");
  els.passphraseError.textContent = "";

  if (resolvePassphraseWaiter !== null) {
    resolvePassphraseWaiter(passphrase);
    resolvePassphraseWaiter = null;
  }
}

function requestTab(tab: TabName): void {
  if (tab === activeTab) {
    return;
  }

  const connectedRuntime = getConnectedRuntime();
  if (connectedRuntime !== null) {
    showModeBlocked();
    return;
  }

  setActiveTab(tab);
}

function setActiveTab(tab: TabName, force = false): void {
  if (!force && getConnectedRuntime() !== null && tab !== activeTab) {
    showModeBlocked();
    return;
  }

  activeTab = tab;

  for (const button of tabButtons) {
    button.classList.toggle("is-active", button.dataset.tab === tab);
  }

  for (const page of tabPages) {
    page.classList.toggle("is-active", page.id === `page-${tab}`);
  }

  renderConnectionControls();
}

function renderConnectionControls(): void {
  const runtime = activeTab === "backtest" ? null : getRuntimeStatus(activeTab);
  const isConnected = Boolean(runtime?.connected);

  if (runtime?.mode !== null && runtime?.mode !== undefined) {
    els.brokerMode.value = runtime.mode;
  }

  els.brokerMode.disabled = activeTab === "backtest" || isConnected;
  els.connectionToggle.disabled = activeTab === "backtest";
  els.connectionToggle.textContent = isConnected ? "Disconnect" : "Connect";
  els.connectionToggle.classList.toggle("danger", isConnected);
  els.connectionToggle.classList.toggle("primary", !isConnected && activeTab !== "backtest");
}

function showModeBlocked(): void {
  showMessage("Mode verrouille", modeBlockedMessage);
}

function showMessage(title: string, text: string): void {
  els.messageTitle.textContent = title;
  els.messageText.textContent = text;
  els.messageModal.classList.remove("is-hidden");
}

function closeMessage(): void {
  els.messageModal.classList.add("is-hidden");
}

async function withBusy(button: HTMLButtonElement, action: () => Promise<void>): Promise<void> {
  button.disabled = true;
  try {
    await action();
  } catch (error: unknown) {
    showMessage("Action failed", error instanceof Error ? error.message : "Action failed");
  } finally {
    renderConnectionControls();
  }
}

els.connectionForm.addEventListener("submit", (event) => {
  event.preventDefault();
  void withBusy(els.connectionToggle, toggleActiveRuntime);
});
els.authForm.addEventListener("submit", (event) => {
  event.preventDefault();
  acceptAuthToken();
});
els.passphraseForm.addEventListener("submit", (event) => {
  event.preventDefault();
  acceptLivePassphrase();
});
els.passphraseCancel.addEventListener("click", () => closePassphraseModal(null));
els.messageClose.addEventListener("click", closeMessage);

for (const button of tabButtons) {
  button.addEventListener("click", () => {
    const tab = button.dataset.tab;
    if (tab === "trading" || tab === "recording" || tab === "backtest") {
      requestTab(tab);
    }
  });
}

init();

async function init(): Promise<void> {
  updateClock();
  window.setInterval(updateClock, 1000);

  try {
    if (!await initAuth()) {
      return;
    }

    await refresh();
    window.setInterval(() => {
      refresh().catch((error: unknown) => {
        console.error(error);
      });
    }, pollMs);
  } catch (error: unknown) {
    showMessage("Connection failed", error instanceof Error ? error.message : "Connection failed");
  }
}

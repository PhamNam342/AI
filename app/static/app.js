const authView = document.querySelector("#auth-view");
const appView = document.querySelector("#app-view");
const authForm = document.querySelector("#auth-form");
const loginTab = document.querySelector("#login-tab");
const registerTab = document.querySelector("#register-tab");
const authSubmit = document.querySelector("#auth-submit");
const authTitle = document.querySelector("#auth-title");
const authUsername = document.querySelector("#auth-username");
const authPassword = document.querySelector("#auth-password");
const authMessage = document.querySelector("#auth-message");
const accountName = document.querySelector("#account-name");
const logoutButton = document.querySelector("#logout-button");
const form = document.querySelector("#recommendation-form");
const topNInput = document.querySelector("#top-n");
const topNOutput = document.querySelector("#top-n-output");
const trainButton = document.querySelector("#train-button");
const statusNode = document.querySelector("#status");
const resultsTitle = document.querySelector("#results-title");
const strategyLabel = document.querySelector("#strategy-label");
const recommendationsNode = document.querySelector("#recommendations");
const modelChip = document.querySelector("#model-chip");
const dataWarning = document.querySelector("#data-warning");
const trainRun = document.querySelector("#train-run");

const formatNumber = new Intl.NumberFormat("en-US");
let currentUser = null;
let authMode = "login";
let summaryLoaded = false;

function setStatus(text, tone = "neutral") {
  statusNode.textContent = text;
  statusNode.dataset.tone = tone;
}

function setAuthMode(mode) {
  authMode = mode;
  loginTab.classList.toggle("active", mode === "login");
  registerTab.classList.toggle("active", mode === "register");
  authTitle.textContent = mode === "login" ? "Sign in" : "Create account";
  authSubmit.textContent = mode === "login" ? "Login" : "Create account";
  authPassword.autocomplete = mode === "login" ? "current-password" : "new-password";
  authMessage.textContent = "";
}

function showAuth() {
  currentUser = null;
  authView.hidden = false;
  appView.hidden = true;
  recommendationsNode.innerHTML = "";
}

async function showApp(user) {
  currentUser = user;
  authView.hidden = true;
  appView.hidden = false;
  accountName.textContent = `${user.display_name} · ID ${user.user_id}`;
  resultsTitle.textContent = `Top picks for ${user.display_name}`;

  if (!summaryLoaded) {
    await loadSummary();
    summaryLoaded = true;
  }
  await loadRecommendations();
}

async function loadCurrentUser() {
  const response = await fetch("/api/auth/me");
  const payload = await response.json();
  if (payload.user) {
    await showApp(payload.user);
  } else {
    showAuth();
    await loadSummaryForAuth();
  }
}

async function submitAuth(event) {
  event.preventDefault();
  authSubmit.disabled = true;
  authMessage.textContent = authMode === "login" ? "Signing in..." : "Creating your account...";

  try {
    const response = await fetch(`/api/auth/${authMode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: authUsername.value,
        password: authPassword.value,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Authentication failed.");
    }

    authForm.reset();
    authMessage.textContent = "";
    await showApp(payload.user);
    setStatus("Signed in", "good");
  } catch (error) {
    authMessage.textContent = error.message;
  } finally {
    authSubmit.disabled = false;
  }
}

async function logout() {
  await fetch("/api/auth/logout", { method: "POST" });
  showAuth();
  await loadSummaryForAuth();
}

function renderRecommendations(payload) {
  const items = payload.recommendations || [];
  const userRatings = payload.user_ratings || {};
  resultsTitle.textContent = `Top picks for ${currentUser?.display_name || `user ${payload.user_id}`}`;
  strategyLabel.textContent = payload.strategy_label || "Recommendation strategy";

  if (!items.length) {
    recommendationsNode.innerHTML = '<div class="empty">No recommendations found.</div>';
    return;
  }

  recommendationsNode.innerHTML = items
    .map((item, index) => {
      const ratingCount = item.rating_count
        ? `<span class="rating-count">${formatNumber.format(item.rating_count)} ratings</span>`
        : "";

      return `
        <article class="movie-card">
          <div class="rank">${index + 1}</div>
          <div class="movie-copy">
            <h3 class="movie-title">${escapeHtml(item.title)}</h3>
            <div class="genres">${escapeHtml(item.genres || "Unknown genre")}</div>
            ${item.reason ? `<div class="reason">${escapeHtml(item.reason)}</div>` : ""}
          </div>
          <div class="movie-actions">
            <div class="rating">
              <span>${formatRating(item.predicted_rating)}</span>
              <small>Predicted</small>
              ${ratingCount}
            </div>
            <label class="rating-picker">
              <select data-movie-id="${item.movieId}" aria-label="Rate ${escapeHtml(item.title)}">
                ${renderRatingOptions(userRatings[item.movieId])}
              </select>
            </label>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderRatingOptions(currentRating) {
  const values = ["", "0.5", "1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5"];
  return values
    .map((value) => {
      const label = value ? value : "Rate";
      const selected = value && Number(value) === Number(currentRating) ? "selected" : "";
      return `<option value="${value}" ${selected}>${label}</option>`;
    })
    .join("");
}

async function saveRating(movieId, rating) {
  setStatus("Saving", "busy");

  const requestPayload = {
    movie_id: movieId,
    rating,
  };

  const response = await fetch("/api/ratings", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(requestPayload),
  });
  const responsePayload = await response.json();

  if (!response.ok) {
    throw new Error(responsePayload.error || "Could not save rating.");
  }

  setStatus(responsePayload.storage === "local+postgres" ? "Saved to DB" : "Saved", "good");
}

async function loadSummaryForAuth() {
  try {
    const response = await fetch("/api/summary");
    const summary = await response.json();
    document.querySelector("#auth-rmse").textContent = summary.metrics?.rmse
      ? Number(summary.metrics.rmse).toFixed(3)
      : "--";
    document.querySelector("#auth-source").textContent = (summary.data_source || "csv").toUpperCase();
  } catch {
    document.querySelector("#auth-rmse").textContent = "--";
    document.querySelector("#auth-source").textContent = "--";
  }
}

async function loadSummary() {
  const response = await fetch("/api/summary");
  const summary = await response.json();

  document.querySelector("#movie-count").textContent = formatNumber.format(summary.movie_count);
  document.querySelector("#user-count").textContent = formatNumber.format(summary.user_count);
  document.querySelector("#rating-count").textContent = formatNumber.format(summary.rating_count);
  document.querySelector("#rmse").textContent = summary.metrics?.rmse
    ? Number(summary.metrics.rmse).toFixed(3)
    : "--";
  document.querySelector("#data-source").textContent = (summary.data_source || "csv").toUpperCase();
  document.querySelector("#algorithm").textContent = summary.algorithm || "SVD";
  modelChip.textContent = summary.model_exists ? "Model ready" : "Train model";
  modelChip.dataset.ready = summary.model_exists ? "true" : "false";

  document.querySelector("#auth-rmse").textContent = summary.metrics?.rmse
    ? Number(summary.metrics.rmse).toFixed(3)
    : "--";
  document.querySelector("#auth-source").textContent = (summary.data_source || "csv").toUpperCase();

  if (summary.data_warning) {
    dataWarning.hidden = false;
    dataWarning.textContent = summary.data_warning;
  } else {
    dataWarning.hidden = true;
    dataWarning.textContent = "";
  }

  renderTrainingRun(summary.training_runs?.[0]);
}

function renderTrainingRun(run) {
  if (!run) {
    trainRun.hidden = true;
    trainRun.textContent = "";
    return;
  }

  trainRun.hidden = false;
  const status = run.status === "succeeded" ? "Last train succeeded" : "Last train failed";
  const metricText = run.metrics?.rmse ? `RMSE ${Number(run.metrics.rmse).toFixed(3)}` : run.error_message;
  trainRun.textContent = `${status} · ${metricText}`;
}

async function loadRecommendations() {
  const params = new URLSearchParams({ top_n: topNInput.value });
  setStatus("Loading", "busy");

  try {
    const response = await fetch(`/api/recommendations?${params}`);
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail || payload.error || "Could not load recommendations.");
    }

    renderRecommendations(payload);
    setStatus("Ready", "good");
  } catch (error) {
    recommendationsNode.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
    setStatus("Needs attention", "warn");
  }
}

async function retrainModel() {
  setStatus("Training", "busy");
  trainButton.disabled = true;

  try {
    const response = await fetch("/api/train", { method: "POST" });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail || payload.error || "Training failed.");
    }

    document.querySelector("#rmse").textContent = Number(payload.metrics.rmse).toFixed(3);
    document.querySelector("#auth-rmse").textContent = Number(payload.metrics.rmse).toFixed(3);
    renderTrainingRun(payload.training_runs?.[0]);
    setStatus("Model trained", "good");
    await loadRecommendations();
  } catch (error) {
    setStatus("Train failed", "warn");
    recommendationsNode.insertAdjacentHTML(
      "afterbegin",
      `<div class="empty">${escapeHtml(error.message)}</div>`,
    );
  } finally {
    trainButton.disabled = false;
  }
}

function formatRating(value) {
  return Number(value).toFixed(2);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

topNInput.addEventListener("input", () => {
  topNOutput.value = topNInput.value;
});

loginTab.addEventListener("click", () => setAuthMode("login"));
registerTab.addEventListener("click", () => setAuthMode("register"));
authForm.addEventListener("submit", submitAuth);
logoutButton.addEventListener("click", logout);

form.addEventListener("submit", (event) => {
  event.preventDefault();
  loadRecommendations();
});

trainButton.addEventListener("click", retrainModel);

recommendationsNode.addEventListener("change", async (event) => {
  const select = event.target.closest("select[data-movie-id]");
  if (!select || !select.value) {
    return;
  }

  try {
    select.disabled = true;
    await saveRating(select.dataset.movieId, select.value);
    await loadRecommendations();
  } catch (error) {
    setStatus("Needs attention", "warn");
    select.disabled = false;
    recommendationsNode.insertAdjacentHTML(
      "afterbegin",
      `<div class="empty">${escapeHtml(error.message)}</div>`,
    );
  }
});

loadCurrentUser().catch(() => {
  showAuth();
  loadSummaryForAuth();
});

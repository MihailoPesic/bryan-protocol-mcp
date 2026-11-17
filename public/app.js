const queryInput = document.getElementById("query-input");
const searchForm = document.getElementById("search-form");
const dossierOut = document.getElementById("dossier-output");
const stancesGrid = document.getElementById("stances-grid");
const sourcesList = document.getElementById("sources-list");
const statsPills = document.getElementById("stats-pills");

let allStances = [];
let allSources = [];
let activeStanceFilter = "all";
let activeTierFilter = "all";

function esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function statusClass(status) {
  const s = (status || "").toLowerCase();
  if (["active", "stopped", "avoid", "conditional", "experimental"].includes(s)) return `badge-${s}`;
  return "badge-conditional";
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === `tab-${name}`));
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    switchTab(btn.dataset.tab);
    if (btn.dataset.tab === "sources" && allSources.length === 0) loadSources();
  });
});

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.json();
}

function renderStanceCard(s) {
  const links = (s.sources || [])
    .map((src) => `<a class="link-pill" href="${esc(src.url)}" target="_blank" rel="noopener">${esc(src.title)}</a>`)
    .join("");
  const receiptText = `${s.topic} [${s.status.toUpperCase()}]: ${s.summary}${s.sources?.[0] ? ` (${s.sources[0].url})` : ""}`;
  return `
    <article class="card">
      <div class="card-top">
        <span class="badge ${statusClass(s.status)}">${esc(s.status)}</span>
        <span class="meta-line">${esc(s.changed_at || "")}</span>
      </div>
      <h3>${esc(s.topic)}</h3>
      <p>${esc(s.summary)}</p>
      ${s.dosage_or_rule ? `<div class="rule"><strong>Protocol / Rule:</strong> ${esc(s.dosage_or_rule)}</div>` : ""}
      ${s.rationale ? `<p class="muted-text">${esc(s.rationale)}</p>` : ""}
      <div class="links-row">
        ${links}
        <button class="btn btn-outline btn-sm copy-receipt-btn" data-receipt="${esc(receiptText)}" type="button">Copy Receipt</button>
      </div>
    </article>
  `;
}

function renderDossier(data) {
  const stances = data.explicit_stances || [];
  const tier1 = data.tier1_official_protocol || [];
  const tier2Docs = data.tier2_official_articles_and_videos?.documents || [];
  const tier2Quotes = data.tier2_official_articles_and_videos?.timestamped_quotes || [];
  const tier3Quotes = data.tier3_external_podcasts || [];

  const shareUrl = `${window.location.origin}/?q=${encodeURIComponent(data.question)}`;
  let html = `
    <div class="section-head">
      <h2>Ground Truth for "${esc(data.question)}"</h2>
      <button class="btn btn-outline btn-sm copy-receipt-btn" data-receipt="${esc(shareUrl)}" type="button">Copy Share Link</button>
    </div>
  `;

  if (stances.length > 0) {
    html += `<div class="card-grid">${stances.map(renderStanceCard).join("")}</div>`;
  }

  if (tier1.length > 0) {
    html += `<div class="section-head"><h2>Tier 1: Official Protocol (protocol.bryanjohnson.com)</h2></div>`;
    html += tier1.map((d) => `
      <div class="quote-card">
        <div class="quote-head">
          <strong>${esc(d.title)}</strong>
          <span class="meta-line">Updated ${esc(d.updated_at || "n/a")}</span>
        </div>
        <p class="quote-text">${esc(d.excerpt)}</p>
        <div class="links-row">
          <a class="link-pill" href="${esc(d.url)}" target="_blank" rel="noopener">Official Page</a>
          <button class="btn btn-outline btn-sm open-doc-btn" data-doc-id="${esc(d.doc_id)}" type="button">Read Full Section</button>
        </div>
      </div>
    `).join("");
  }

  if (tier2Docs.length > 0) {
    html += `<div class="section-head"><h2>Tier 2: Blueprint Articles &amp; @BryanJohnson Videos</h2></div>`;
    html += tier2Docs.map((d) => `
      <div class="quote-card">
        <div class="quote-head">
          <strong>${esc(d.title)}</strong>
          <span class="meta-line">${esc(d.source_type)} | ${esc(d.published_at || "n/a")}</span>
        </div>
        <p class="quote-text">${esc(d.excerpt)}</p>
        <div class="links-row">
          <a class="link-pill" href="${esc(d.url)}" target="_blank" rel="noopener">Open Source</a>
          <button class="btn btn-outline btn-sm open-doc-btn" data-doc-id="${esc(d.doc_id)}" type="button">Read Full Text</button>
        </div>
      </div>
    `).join("");
  }

  const allQuotes = [...tier2Quotes, ...tier3Quotes];
  if (allQuotes.length > 0) {
    html += `<div class="section-head"><h2>Timestamped Video &amp; Podcast Receipts</h2></div>`;
    html += allQuotes.map((q) => {
      const receipt = `"${q.text}" - Bryan Johnson on ${q.channel} (${q.published_at}) ${q.deep_link}`;
      return `
        <div class="quote-card">
          <div class="quote-head">
            <strong>${esc(q.title)}</strong>
            <span class="meta-line">${esc(q.channel)} | ${esc(q.published_at || "")} @ ${esc(q.timestamp)}</span>
          </div>
          <p class="quote-text">"${esc(q.text)}"</p>
          <div class="links-row">
            <a class="link-pill" href="${esc(q.deep_link)}" target="_blank" rel="noopener">Watch @ ${esc(q.timestamp)}</a>
            <button class="btn btn-outline btn-sm open-doc-btn" data-doc-id="${esc(q.doc_id)}" type="button">Full Transcript</button>
            <button class="btn btn-outline btn-sm copy-receipt-btn" data-receipt="${esc(receipt)}" type="button">Copy Quote + Timestamp</button>
          </div>
        </div>
      `;
    }).join("");
  }

  if (stances.length === 0 && tier1.length === 0 && tier2Docs.length === 0 && allQuotes.length === 0) {
    html += `<div class="quote-card"><p class="muted-text">No direct matches found for "${esc(data.question)}". Try broader keywords like sleep, olive oil, sauna, metformin, or stem cells.</p></div>`;
  }

  dossierOut.innerHTML = html;
}

function renderLandingDossier() {
  const featuredIds = new Set([
    "stance:rapamycin",
    "stance:coffee-caffeine",
    "stance:cold-plunge",
    "stance:seed-oils-vs-evoo",
    "stance:hgh-thymus",
    "stance:testosterone-trt",
  ]);
  const featured = allStances.filter((s) => featuredIds.has(s.id));
  dossierOut.innerHTML = `
    <div class="section-head">
      <h2>Most Misunderstood &amp; Changed Protocol Rules</h2>
      <span class="meta-line">Click any topic above or search any supplement/habit</span>
    </div>
    <div class="card-grid">${(featured.length ? featured : allStances.slice(0, 6)).map(renderStanceCard).join("")}</div>
  `;
}

async function runQuery(q) {
  const clean = (q || "").trim();
  if (!clean) {
    renderLandingDossier();
    return;
  }
  switchTab("dossier");
  queryInput.value = clean;
  const nextUrl = `${window.location.pathname}?q=${encodeURIComponent(clean)}`;
  window.history.replaceState(null, "", nextUrl);
  dossierOut.innerHTML = `<div class="quote-card"><p class="muted-text">Searching 266 sources and 11,870 timestamps...</p></div>`;
  try {
    const data = await fetchJson(`/api/query?q=${encodeURIComponent(clean)}`);
    renderDossier(data);
  } catch (err) {
    dossierOut.innerHTML = `<div class="quote-card"><p class="muted-text">Error: ${esc(err.message)}</p></div>`;
  }
}

function renderStances() {
  const list = activeStanceFilter === "all"
    ? allStances
    : allStances.filter((s) => s.status === activeStanceFilter);
  stancesGrid.innerHTML = list.map(renderStanceCard).join("");
}

async function loadSources() {
  sourcesList.innerHTML = `<div class="quote-card"><p class="muted-text">Loading sources...</p></div>`;
  const data = await fetchJson("/api/sources?limit=200&offset=0");
  allSources = data.items || [];
  if ((data.total || 0) > allSources.length) {
    const page2 = await fetchJson(`/api/sources?limit=200&offset=${allSources.length}`);
    allSources = allSources.concat(page2.items || []);
  }
  renderSources();
}

function renderSources() {
  const list = activeTierFilter === "all"
    ? allSources
    : allSources.filter((s) => String(s.tier) === activeTierFilter);
  sourcesList.innerHTML = list.map((s) => `
    <div class="source-row">
      <div>
        <strong>${esc(s.title)}</strong>
        <div class="meta-line">Tier ${esc(s.tier)} | ${esc(s.source_type)} | ${esc(s.channel_or_site)} | ${esc(s.published_at || s.updated_at || "")}</div>
      </div>
      <div class="links-row">
        <a class="link-pill" href="${esc(s.url)}" target="_blank" rel="noopener">Original</a>
        <button class="btn btn-outline btn-sm open-doc-btn" data-doc-id="${esc(s.id)}" type="button">Inspect</button>
      </div>
    </div>
  `).join("");
}

document.addEventListener("click", async (e) => {
  const chip = e.target.closest(".chip");
  if (chip) {
    runQuery(chip.dataset.q);
    return;
  }

  const copyReceipt = e.target.closest(".copy-receipt-btn");
  if (copyReceipt) {
    await navigator.clipboard.writeText(copyReceipt.dataset.receipt || "");
    const old = copyReceipt.textContent;
    copyReceipt.textContent = "Copied!";
    setTimeout(() => { copyReceipt.textContent = old; }, 1400);
    return;
  }

  const copyTarget = e.target.closest("[data-copy-target]");
  if (copyTarget) {
    const el = document.getElementById(copyTarget.dataset.copyTarget);
    if (el) {
      await navigator.clipboard.writeText(el.textContent || "");
      const old = copyTarget.textContent;
      copyTarget.textContent = "Copied!";
      setTimeout(() => { copyTarget.textContent = old; }, 1400);
    }
    return;
  }

  const openDoc = e.target.closest(".open-doc-btn");
  if (openDoc) {
    const docId = openDoc.dataset.docId;
    const modal = document.getElementById("doc-modal");
    document.getElementById("doc-modal-title").textContent = "Loading...";
    document.getElementById("doc-modal-body").textContent = "";
    modal.showModal();
    const doc = await fetchJson(`/api/document?id=${encodeURIComponent(docId)}`);
    document.getElementById("doc-modal-badge").className = "badge badge-conditional";
    document.getElementById("doc-modal-badge").textContent = `TIER ${doc.tier} / ${doc.source_type}`;
    document.getElementById("doc-modal-title").textContent = doc.title;
    document.getElementById("doc-modal-meta").innerHTML =
      `${esc(doc.channel_or_site)} | ${esc(doc.published_at || doc.updated_at || "")} | <a href="${esc(doc.url)}" target="_blank" rel="noopener">${esc(doc.url)}</a>`;
    document.getElementById("doc-modal-body").textContent = doc.content;
  }
});

document.querySelectorAll("#stance-filters .filter-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    activeStanceFilter = btn.dataset.status;
    document.querySelectorAll("#stance-filters .filter-btn").forEach((b) => b.classList.toggle("active", b === btn));
    renderStances();
  });
});

document.querySelectorAll("#source-filters .filter-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    activeTierFilter = btn.dataset.tier;
    document.querySelectorAll("#source-filters .filter-btn").forEach((b) => b.classList.toggle("active", b === btn));
    renderSources();
  });
});

searchForm.addEventListener("submit", (e) => {
  e.preventDefault();
  runQuery(queryInput.value);
});

const mcpModal = document.getElementById("mcp-modal");
document.getElementById("open-mcp-btn").addEventListener("click", () => {
  const mcpUrl = `${window.location.origin}/mcp`;
  document.getElementById("mcp-endpoint-url").textContent = mcpUrl;
  document.getElementById("claude-code-cmd").textContent = `claude mcp add --transport http bryan-protocol ${mcpUrl}`;
  document.getElementById("cursor-mcp-json").textContent = JSON.stringify({
    mcpServers: {
      "bryan-protocol": {
        url: mcpUrl,
      },
    },
  }, null, 2);
  mcpModal.showModal();
});
document.getElementById("close-mcp-btn").addEventListener("click", () => mcpModal.close());
document.getElementById("close-doc-btn").addEventListener("click", () => document.getElementById("doc-modal").close());

async function init() {
  const [overview, stancesPayload] = await Promise.all([
    fetchJson("/api/overview"),
    fetchJson("/api/stances"),
  ]);
  allStances = stancesPayload.stances || [];
  const docTotal = (overview.document_counts || []).reduce((acc, r) => acc + r.count, 0);
  statsPills.innerHTML = `
    <span class="pill">${docTotal} indexed sources</span>
    <span class="pill">${Number(overview.segment_count || 0).toLocaleString()} video timestamps</span>
    <span class="pill">${allStances.length} verified stances</span>
  `;
  renderStances();

  const urlQ = new URLSearchParams(window.location.search).get("q");
  if (urlQ) {
    await runQuery(urlQ);
  } else {
    renderLandingDossier();
  }
}

init().catch((err) => {
  dossierOut.innerHTML = `<div class="quote-card"><p class="muted-text">Failed to initialize archive: ${esc(err.message)}</p></div>`;
});

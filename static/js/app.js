/* ============================================================
   LaTeX Quellen Manager - Frontend Logic  v4.1
   ============================================================ */

"use strict";

// ============================================================
// STATE
// ============================================================
const state = {
  entryTypes:     {},    // { key: { label, icon, fields } }
  settings:       {},    // aktuelle Einstellungen
  selectedType:   null,  // aktuell gewählter Typ
  fieldValues:    {},    // { fieldKey: value }
  citeKey:        "",
  filename:       "",
  autoPreview:    true,
  previewDebounce: null,

  // Library
  libraryFiles:   [],    // alle geladenen .bib-Einträge
  libView:        "grid",// "grid" | "list"

  // Editor
  editorFile:     null,  // { path, name }
  editorCM:       null,  // CodeMirror Instanz
  editorDirty:    false, // ungespeicherte Änderungen

  // Modal
  modalResolve:   null,
};

// ============================================================
// THEME
// ============================================================
const THEMES = ["light", "dark", "ocean", "forest", "rose"];

function applyTheme(theme) {
  if (!THEMES.includes(theme)) theme = "light";
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("lqm-theme", theme);

  // CodeMirror Theme anpassen
  const isDark = (theme === "dark");
  if (state.editorCM) {
    state.editorCM.setOption("theme", isDark ? "dracula" : "default");
  }

  // Settings cards sync
  document.querySelectorAll(".theme-card").forEach(c => {
    c.classList.toggle("active", c.dataset.theme === theme);
  });
}

function setupTheme() {
  const saved = localStorage.getItem("lqm-theme") || "light";
  applyTheme(saved);

  // Nur Settings-Karten (kein Sidebar-Switcher mehr)
  document.querySelectorAll(".theme-card").forEach(btn => {
    btn.addEventListener("click", () => applyTheme(btn.dataset.theme));
  });
}

// ============================================================
// INIT
// ============================================================
document.addEventListener("DOMContentLoaded", async () => {
  setupTheme();
  await Promise.all([loadEntryTypes(), loadSettings()]);
  setupNavigation();
  setupFormActions();
  setupSettingsPanel();
  renderTypeGrid();
  updateSectionSelect();
  setupEditorPanel();
  setupModal();
});

// ============================================================
// API HELPERS
// ============================================================
async function api(path, method = "GET", body = null) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  return res.json();
}

async function loadEntryTypes() {
  state.entryTypes = await api("/api/entry-types");
}

async function loadSettings() {
  state.settings = await api("/api/settings");
  state.autoPreview = state.settings.auto_update_preview ?? true;
  document.getElementById("auto-preview-checkbox").checked = state.autoPreview;
}

// ============================================================
// NAVIGATION
// ============================================================
function setupNavigation() {
  document.querySelectorAll(".nav-item").forEach(btn => {
    btn.addEventListener("click", () => {
      const view = btn.dataset.view;
      document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
      document.getElementById(`view-${view}`).classList.add("active");
      if (view === "library")  loadLibrary();
      if (view === "history")  loadHistory();
      if (view === "settings") populateSettingsForm();
    });
  });
}

// ============================================================
// TYPE GRID
// ============================================================
function renderTypeGrid() {
  const grid = document.getElementById("type-grid");
  grid.innerHTML = "";
  for (const [key, type] of Object.entries(state.entryTypes)) {
    const btn = document.createElement("button");
    btn.className = "type-btn";
    btn.dataset.type = key;
    btn.innerHTML = `<i class="${type.icon}"></i><span>${type.label}</span>`;
    btn.addEventListener("click", () => selectType(key));
    grid.appendChild(btn);
  }

  const lastType = state.settings.last_entry_type || "online";
  if (state.entryTypes[lastType]) selectType(lastType);
}

function selectType(key) {
  state.selectedType = key;
  state.fieldValues  = {};

  document.querySelectorAll(".type-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.type === key);
  });

  const type = state.entryTypes[key];
  document.getElementById("form-card-header").innerHTML =
    `<i class="${type.icon}" style="color:var(--accent)"></i> ${type.label} – Felder ausfüllen`;

  renderFields(key);

  document.getElementById("key-card").style.display    = "";
  document.getElementById("action-bar").style.display  = "";

  const sections    = state.settings.bib_placement_sections || [];
  const hasSections = sections.length > 0 && state.settings.latex_main_path;
  document.getElementById("section-assign-wrap").style.display = hasSections ? "" : "none";

  updateCiteKeyFromFields();
  api("/api/settings", "POST", { last_entry_type: key });
}

// ============================================================
// FELDER RENDERN
// ============================================================
function renderFields(typeKey) {
  const container = document.getElementById("fields-container");
  container.innerHTML = "";

  const type = state.entryTypes[typeKey];
  if (!type) {
    container.innerHTML = `<div class="placeholder-msg"><i class="bi bi-question-circle"></i>Unbekannter Typ.</div>`;
    return;
  }

  const grid = document.createElement("div");
  grid.className = "fields-grid";

  type.fields.forEach(field => {
    const isFullWidth = ["title", "url", "note"].includes(field.key);
    const wrapper = document.createElement("div");
    if (isFullWidth) wrapper.className = "field-full";

    const label = document.createElement("label");
    label.className = "form-label";
    if (field.required) {
      label.innerHTML = `<span class="required-dot" title="Pflichtfeld"></span> ${field.label}`;
    } else {
      label.textContent = field.label;
    }

    let input;
    if (field.type === "date" || field.type === "year") {
      const wrap = document.createElement("div");
      wrap.className = "date-field-wrap";

      input = document.createElement("input");
      input.type = "text";
      input.className = "form-control";
      input.placeholder = field.placeholder || "";
      input.dataset.fieldKey = field.key;

      const todayBtn = document.createElement("button");
      todayBtn.className = "btn-today";
      todayBtn.type = "button";
      todayBtn.title = "Heute einfügen";
      todayBtn.innerHTML = '<i class="bi bi-calendar-date"></i>';
      todayBtn.addEventListener("click", () => {
        const now = new Date();
        input.value = (field.type === "year")
          ? now.getFullYear().toString()
          : now.toISOString().slice(0, 10);
        onFieldChange(field.key, input.value);
      });

      wrap.appendChild(input);
      wrap.appendChild(todayBtn);
      wrapper.appendChild(label);
      wrapper.appendChild(wrap);
    } else {
      input = document.createElement("input");
      input.type = "text";
      input.className = "form-control";
      input.placeholder = field.placeholder || "";
      input.dataset.fieldKey = field.key;
      wrapper.appendChild(label);
      wrapper.appendChild(input);
    }

    if (field.key === "urldate") {
      const today = new Date().toISOString().slice(0, 10);
      input.value = today;
      state.fieldValues["urldate"] = today;
    }

    input.addEventListener("input", () => onFieldChange(field.key, input.value));
    grid.appendChild(wrapper);
  });

  container.appendChild(grid);
}

function onFieldChange(key, value) {
  state.fieldValues[key] = value;
  if (["title", "author", "date"].includes(key)) {
    updateCiteKeyFromFields();
  }
  if (state.autoPreview) {
    clearTimeout(state.previewDebounce);
    state.previewDebounce = setTimeout(refreshPreview, 450);
  }
}

async function updateCiteKeyFromFields() {
  const res = await api("/api/cite-key", "POST", {
    title:  state.fieldValues.title  || "",
    author: state.fieldValues.author || "",
    date:   state.fieldValues.date   || "",
  });
  state.citeKey  = res.cite_key;
  state.filename = res.filename.replace(/\.bib$/, "");

  const keyInput = document.getElementById("cite-key-input");
  const fnInput  = document.getElementById("filename-input");
  if (!keyInput.dataset.manualEdit) keyInput.value = state.citeKey;
  if (!fnInput.dataset.manualEdit)  fnInput.value  = state.filename;
}

// ============================================================
// AKTIONS-BUTTONS (Create View)
// ============================================================
function setupFormActions() {
  document.getElementById("btn-regen-key").addEventListener("click", () => {
    delete document.getElementById("cite-key-input").dataset.manualEdit;
    delete document.getElementById("filename-input").dataset.manualEdit;
    updateCiteKeyFromFields();
  });

  document.getElementById("cite-key-input").addEventListener("input", function () {
    this.dataset.manualEdit = "1";
    state.citeKey = this.value;
  });

  document.getElementById("filename-input").addEventListener("input", function () {
    this.dataset.manualEdit = "1";
    state.filename = this.value;
  });

  document.getElementById("auto-preview-checkbox").addEventListener("change", function () {
    state.autoPreview = this.checked;
    api("/api/settings", "POST", { auto_update_preview: this.checked });
    if (this.checked) refreshPreview();
  });

  document.getElementById("btn-preview-refresh").addEventListener("click", refreshPreview);

  document.getElementById("btn-copy-preview").addEventListener("click", () => {
    const text = document.getElementById("bibtex-preview").innerText;
    navigator.clipboard.writeText(text).then(() => toast("In Zwischenablage kopiert!", "success"));
  });

  document.getElementById("btn-clear").addEventListener("click", () => {
    if (!confirm("Alle Felder wirklich leeren?")) return;
    document.querySelectorAll("#fields-container input, #fields-container textarea").forEach(el => {
      el.value = "";
    });
    state.fieldValues = {};
    delete document.getElementById("cite-key-input").dataset.manualEdit;
    delete document.getElementById("filename-input").dataset.manualEdit;
    document.getElementById("cite-key-input").value = "";
    document.getElementById("filename-input").value = "";
    document.getElementById("bibtex-preview").innerHTML =
      '<span class="preview-placeholder">Vorschau erscheint hier&hellip;</span>';
  });

  document.getElementById("btn-save").addEventListener("click", saveEntry);
}

async function refreshPreview() {
  if (!state.selectedType) return;
  const citeKey = document.getElementById("cite-key-input").value || state.citeKey;
  const res = await api("/api/preview", "POST", {
    entry_type: state.selectedType,
    fields:     state.fieldValues,
    cite_key:   citeKey,
  });
  renderBibtexPreview(res.bibtex, "bibtex-preview");
}

function renderBibtexPreview(raw, targetId = "bibtex-preview") {
  const el = document.getElementById(targetId);
  if (!el || !raw) return;
  let html = escapeHtml(raw);
  html = html.replace(/^(@\w+)\{([^,]+),/m,
    (_, t, k) => `<span class="bib-type">${t}</span>{<span class="bib-key">${k}</span>,`);
  html = html.replace(/^(\s+)(\w+)(\s+=\s+)\{([^}]*)\}(,?)$/gm,
    (_, sp, f, eq, v, comma) =>
      `${sp}<span class="bib-field">${f}</span>${eq}{<span class="bib-value">${v}</span>}${comma}`);
  html = html.replace(/(^%[^\n]*)/gm, '<span class="bib-comment">$1</span>');
  el.innerHTML = html;
}

function escapeHtml(s) {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

async function saveEntry() {
  if (!state.selectedType) {
    toast("Bitte zuerst einen Quellentyp auswählen.", "warning");
    return;
  }

  const citeKey  = document.getElementById("cite-key-input").value || state.citeKey;
  const filename = (document.getElementById("filename-input").value || state.filename).replace(/\.bib$/, "");
  const sectionId= document.getElementById("section-select")?.value || "";

  if (!citeKey) { toast("Zitierschlüssel fehlt.", "warning"); return; }

  const type    = state.entryTypes[state.selectedType];
  const missing = type.fields
    .filter(f => f.required && !(state.fieldValues[f.key] || "").trim())
    .map(f => f.label);
  if (missing.length > 0) {
    toast(`Pflichtfelder fehlen: ${missing.join(", ")}`, "warning");
    return;
  }

  const btn = document.getElementById("btn-save");
  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Speichere…';

  const res = await api("/api/save", "POST", {
    entry_type: state.selectedType,
    fields:     state.fieldValues,
    cite_key:   citeKey,
    filename,
    section_id: sectionId,
  });

  btn.disabled = false;
  btn.innerHTML = '<i class="bi bi-floppy"></i> Quelle speichern';

  if (!res.ok) { toast(`Fehler: ${res.error}`, "error"); return; }

  let msg = `Gespeichert: ${res.filename}`;
  if (res.latex_updated) msg += " · LaTeX-Datei aktualisiert";
  if (res.latex_error)   toast(`LaTeX-Warnung: ${res.latex_error}`, "warning");
  toast(msg, "success");
}

// ============================================================
// SECTION SELECT (in create view)
// ============================================================
function updateSectionSelect() {
  const sel = document.getElementById("section-select");
  if (!sel) return;
  const sections = state.settings.bib_placement_sections || [];
  while (sel.options.length > 1) sel.remove(1);
  sections.forEach(s => {
    const opt = document.createElement("option");
    opt.value = s.id;
    opt.textContent = s.label;
    sel.appendChild(opt);
  });
  if (state.settings.default_section_id) {
    sel.value = state.settings.default_section_id;
  }
}

// ============================================================
// LIBRARY VIEW
// ============================================================
async function loadLibrary() {
  const grid = document.getElementById("lib-grid");
  grid.innerHTML = `<div class="empty-state"><i class="bi bi-hourglass-split spin"></i><p>Bibliothek wird geladen…</p></div>`;

  const res = await api("/api/library");
  state.libraryFiles = res.files || [];

  // Filter-Dropdowns befüllen
  populateLibraryFilters(state.libraryFiles);
  renderLibrary();

  // Refresh-Button
  document.getElementById("btn-refresh-library").onclick = loadLibrary;
}

function populateLibraryFilters(files) {
  const typeFilter = document.getElementById("lib-type-filter");
  const yearFilter = document.getElementById("lib-year-filter");

  const savedType = typeFilter.value;
  const savedYear = yearFilter.value;

  // Zählt Einträge pro Typ
  const typeCounts = {};
  files.forEach(f => { if (f.type) typeCounts[f.type] = (typeCounts[f.type] || 0) + 1; });

  // ALLE 21 Typen aus entryTypes anzeigen (mit Anzahl)
  typeFilter.innerHTML = `<option value="">Alle Typen (${files.length})</option>`;
  for (const [key, type] of Object.entries(state.entryTypes)) {
    const count = typeCounts[key] || 0;
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = count > 0 ? `${type.label} (${count})` : type.label;
    if (count === 0) opt.style.color = "var(--text-muted)";
    typeFilter.appendChild(opt);
  }
  typeFilter.value = savedType;

  // Jahre: nur vorhandene anzeigen (absteigend)
  const years = [...new Set(files.map(f => f.year).filter(Boolean))].sort((a, b) => b - a);
  yearFilter.innerHTML = `<option value="">Alle Jahre</option>`;
  years.forEach(y => {
    const opt = document.createElement("option");
    opt.value = y;
    opt.textContent = y;
    yearFilter.appendChild(opt);
  });
  yearFilter.value = savedYear;
}

function getFilteredLibrary() {
  const query   = (document.getElementById("lib-search")?.value || "").toLowerCase().trim();
  const selType = document.getElementById("lib-type-filter")?.value || "";
  const selYear = document.getElementById("lib-year-filter")?.value || "";
  const sort    = document.getElementById("lib-sort")?.value || "modified";

  let files = state.libraryFiles.slice();

  if (query) {
    files = files.filter(f =>
      (f.title  || "").toLowerCase().includes(query) ||
      (f.author || "").toLowerCase().includes(query) ||
      (f.key    || "").toLowerCase().includes(query) ||
      (f.publisher || "").toLowerCase().includes(query) ||
      (f.name   || "").toLowerCase().includes(query)
    );
  }
  if (selType) files = files.filter(f => f.type === selType);
  if (selYear) files = files.filter(f => f.year === selYear);

  files.sort((a, b) => {
    switch (sort) {
      case "title":     return (a.title || "").localeCompare(b.title || "");
      case "author":    return (a.author || "").localeCompare(b.author || "");
      case "year-desc": return (b.year || "0").localeCompare(a.year || "0");
      case "year-asc":  return (a.year || "0").localeCompare(b.year || "0");
      default:          return 0; // modified (already sorted by server)
    }
  });

  return files;
}

function renderLibrary() {
  const grid  = document.getElementById("lib-grid");
  const files = getFilteredLibrary();

  // Stats
  document.getElementById("lib-count").textContent =
    `${files.length} ${files.length === 1 ? "Eintrag" : "Einträge"}`;

  // View class
  grid.classList.toggle("list-view", state.libView === "list");

  if (files.length === 0) {
    grid.innerHTML = `<div class="empty-state"><i class="bi bi-inbox"></i><p>${
      state.libraryFiles.length === 0
        ? "Noch keine .bib-Dateien im Zielverzeichnis."
        : "Keine Einträge gefunden."
    }</p></div>`;
    return;
  }

  grid.innerHTML = "";
  files.forEach(f => grid.appendChild(buildEntryCard(f)));
}

function buildEntryCard(f) {
  const card = document.createElement("div");
  card.className = "entry-card";
  card.title = f.path;

  const typeLabel = ENTRY_TYPE_LABEL(f.type);
  const typeIcon  = ENTRY_TYPE_ICON(f.type);

  // ── Smart Cover ──────────────────────────────────────────
  // Priorität: 1) ISBN → Open Library  2) URL → Favicon  3) Platzhalter
  const isbnClean = (f.isbn || "").replace(/[-\s]/g, "");
  const hasIsbn   = isbnClean.length >= 10;
  const hasUrl    = !!(f.url || "").trim();

  let coverUrl    = null;
  let isFavicon   = false;

  if (hasIsbn) {
    coverUrl = `https://covers.openlibrary.org/b/isbn/${isbnClean}-M.jpg`;
  } else if (hasUrl) {
    try {
      const domain = new URL(f.url.trim()).hostname;
      coverUrl  = `https://www.google.com/s2/favicons?domain=${domain}&sz=128`;
      isFavicon = true;
    } catch { /* ungültige URL */ }
  }

  // Cover section
  const cover = document.createElement("div");
  cover.className = "entry-card-cover";

  if (coverUrl) {
    const img = document.createElement("img");
    img.alt     = f.title || "";
    img.loading = "lazy";
    if (isFavicon) img.classList.add("is-favicon");
    img.src = coverUrl;
    img.addEventListener("error", () => {
      img.remove();
      cover.appendChild(buildCoverPlaceholder(typeIcon));
    });
    cover.appendChild(img);
  } else {
    cover.appendChild(buildCoverPlaceholder(typeIcon));
  }

  // Body
  const body = document.createElement("div");
  body.className = "entry-card-body";

  const badge = document.createElement("span");
  badge.className = "entry-type-badge";
  badge.innerHTML = `<i class="${typeIcon}"></i> ${typeLabel}`;

  const title = document.createElement("div");
  title.className = "entry-title";
  title.textContent = f.title || f.name;

  const author = document.createElement("div");
  author.className = "entry-author";
  author.textContent = f.author || "";

  const meta = document.createElement("div");
  meta.className = "entry-meta";
  if (f.year) {
    meta.innerHTML += `<span class="entry-meta-item"><i class="bi bi-calendar3"></i>${escapeHtml(f.year)}</span>`;
  }
  if (f.publisher) {
    meta.innerHTML += `<span class="entry-meta-item"><i class="bi bi-building"></i>${escapeHtml(f.publisher)}</span>`;
  }
  if (f.journal) {
    meta.innerHTML += `<span class="entry-meta-item"><i class="bi bi-journal-text"></i>${escapeHtml(f.journal)}</span>`;
  }
  if (hasUrl && !f.publisher && !f.journal) {
    try {
      const domain = new URL(f.url.trim()).hostname.replace(/^www\./, "");
      meta.innerHTML += `<span class="entry-meta-item"><i class="bi bi-globe"></i>${escapeHtml(domain)}</span>`;
    } catch { /* ignore */ }
  }

  const key = document.createElement("div");
  key.className = "entry-key";
  key.textContent = f.key || f.name;
  key.title = f.key;

  const actions = document.createElement("div");
  actions.className = "entry-actions";
  actions.innerHTML = `
    <button class="entry-action-btn" title="Bearbeiten"><i class="bi bi-pencil"></i><span>Bearbeiten</span></button>
    <button class="entry-action-btn danger" title="Löschen"><i class="bi bi-trash"></i><span>Löschen</span></button>
  `;

  const [editBtn, deleteBtn] = actions.querySelectorAll(".entry-action-btn");
  editBtn.addEventListener("click",   (e) => { e.stopPropagation(); openEditor(f); });
  deleteBtn.addEventListener("click", (e) => { e.stopPropagation(); confirmDeleteFile(f); });

  card.addEventListener("click", () => openEditor(f));

  body.append(badge, title, author, meta, key, actions);
  card.append(cover, body);
  return card;
}

function buildCoverPlaceholder(icon) {
  const ph = document.createElement("div");
  ph.className = "cover-placeholder";
  ph.innerHTML = `<i class="${icon}"></i>`;
  return ph;
}

// Type → Label/Icon lookup (Fallback wenn entryTypes noch nicht geladen)
function ENTRY_TYPE_LABEL(type) {
  return state.entryTypes[type]?.label || (type ? type.charAt(0).toUpperCase() + type.slice(1) : "?");
}
function ENTRY_TYPE_ICON(type) {
  return state.entryTypes[type]?.icon || "bi-file-earmark-text";
}

// Library Filter-Events
document.addEventListener("DOMContentLoaded", () => {
  const libSearch  = document.getElementById("lib-search");
  const libClear   = document.getElementById("lib-search-clear");
  const typeFilter = document.getElementById("lib-type-filter");
  const yearFilter = document.getElementById("lib-year-filter");
  const sortSelect = document.getElementById("lib-sort");
  const gridBtn    = document.getElementById("btn-view-grid");
  const listBtn    = document.getElementById("btn-view-list");

  if (libSearch) {
    libSearch.addEventListener("input", () => {
      if (libClear) libClear.style.display = libSearch.value ? "" : "none";
      renderLibrary();
    });
  }
  if (libClear) {
    libClear.addEventListener("click", () => {
      libSearch.value = "";
      libClear.style.display = "none";
      renderLibrary();
    });
  }
  if (typeFilter) typeFilter.addEventListener("change", renderLibrary);
  if (yearFilter) yearFilter.addEventListener("change", renderLibrary);
  if (sortSelect) sortSelect.addEventListener("change", renderLibrary);

  if (gridBtn) {
    gridBtn.addEventListener("click", () => {
      state.libView = "grid";
      gridBtn.classList.add("active");
      listBtn.classList.remove("active");
      renderLibrary();
    });
  }
  if (listBtn) {
    listBtn.addEventListener("click", () => {
      state.libView = "list";
      listBtn.classList.add("active");
      gridBtn.classList.remove("active");
      renderLibrary();
    });
  }
});

// ============================================================
// EDITOR PANEL
// ============================================================
function setupEditorPanel() {
  document.getElementById("btn-editor-close").addEventListener("click", closeEditor);
  document.getElementById("btn-editor-discard").addEventListener("click", discardEditorChanges);
  document.getElementById("btn-editor-save").addEventListener("click", saveEditorContent);
  document.getElementById("btn-editor-delete").addEventListener("click", () => {
    if (state.editorFile) confirmDeleteFile(state.editorFile);
  });
  document.getElementById("btn-editor-rename").addEventListener("click", () => {
    if (state.editorFile) promptRenameFile(state.editorFile);
  });

  // Keyboard shortcuts
  document.addEventListener("keydown", (e) => {
    const overlay = document.getElementById("editor-overlay");
    if (!overlay.classList.contains("open")) return;
    if (e.key === "Escape") { e.preventDefault(); closeEditor(); }
    if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); saveEditorContent(); }
  });
}

async function openEditor(f) {
  state.editorFile  = f;
  state.editorDirty = false;

  // Header
  document.getElementById("editor-filename").textContent = f.name;
  document.getElementById("editor-filename").classList.remove("unsaved");
  document.getElementById("editor-filepath").textContent = f.path;

  // Meta bar
  const meta = document.getElementById("editor-meta");
  meta.innerHTML = "";
  const metaItems = [
    f.type    && { icon: "bi-tag",           label: "Typ",    value: ENTRY_TYPE_LABEL(f.type) },
    f.key     && { icon: "bi-key",           label: "Key",    value: f.key },
    f.author  && { icon: "bi-person",        label: "Autor",  value: f.author },
    f.year    && { icon: "bi-calendar3",     label: "Jahr",   value: f.year },
    f.modified&& { icon: "bi-clock-history", label: "Geändert", value: f.modified },
  ].filter(Boolean);
  metaItems.forEach(item => {
    const span = document.createElement("span");
    span.className = "editor-meta-item";
    span.innerHTML = `<i class="bi ${item.icon}"></i><strong>${escapeHtml(item.value)}</strong>`;
    meta.appendChild(span);
  });

  // Datei-Inhalt laden
  const res = await api("/api/file-content", "POST", { path: f.path });
  const content = res.content || "";

  // Editor anzeigen
  const overlay = document.getElementById("editor-overlay");
  overlay.classList.add("open");

  // CodeMirror initialisieren / aktualisieren
  const wrap = document.getElementById("editor-cm-wrap");
  if (state.editorCM) {
    state.editorCM.toTextArea();
    state.editorCM = null;
  }
  wrap.innerHTML = "";
  const ta = document.createElement("textarea");
  wrap.appendChild(ta);

  const isDark = document.documentElement.getAttribute("data-theme") === "dark";

  state.editorCM = CodeMirror.fromTextArea(ta, {
    value:            content,
    mode:             "stex",
    theme:            isDark ? "dracula" : "default",
    lineNumbers:      true,
    matchBrackets:    true,
    autoCloseBrackets:true,
    lineWrapping:     true,
    extraKeys: {
      "Ctrl-S": saveEditorContent,
      "Esc":    closeEditor,
    },
  });

  state.editorCM.setValue(content);
  state.editorCM.clearHistory();

  state.editorCM.on("change", () => {
    if (!state.editorDirty) {
      state.editorDirty = true;
      document.getElementById("editor-filename").classList.add("unsaved");
    }
  });

  // Focus
  setTimeout(() => state.editorCM?.refresh(), 50);
}

function closeEditor() {
  if (state.editorDirty) {
    if (!confirm("Ungespeicherte Änderungen verwerfen?")) return;
  }
  document.getElementById("editor-overlay").classList.remove("open");
  state.editorDirty = false;
  state.editorFile  = null;
}

function discardEditorChanges() {
  if (state.editorFile) {
    const dirty = state.editorDirty;
    state.editorDirty = false; // Verhindert erneute Rückfrage in openEditor
    openEditor(state.editorFile);
    if (!dirty) toast("Keine Änderungen vorhanden.", "info");
    else        toast("Änderungen verworfen.", "info");
  }
}

async function saveEditorContent() {
  if (!state.editorFile || !state.editorCM) return;
  const content = state.editorCM.getValue();
  const res = await api("/api/bib/save-edit", "POST", {
    path:    state.editorFile.path,
    content,
  });
  if (res.ok) {
    state.editorDirty = false;
    document.getElementById("editor-filename").classList.remove("unsaved");
    toast(`Gespeichert: ${state.editorFile.name}`, "success");
    // Library neu laden falls sichtbar
    if (document.getElementById("view-library").classList.contains("active")) {
      await loadLibrary();
    }
  } else {
    toast(`Fehler beim Speichern: ${res.error}`, "error");
  }
}

async function confirmDeleteFile(f) {
  const confirmed = await showModal({
    icon:    "bi-trash",
    iconColor: "var(--danger)",
    title:   "Datei löschen",
    body:    `Soll die Datei <strong>${escapeHtml(f.name)}</strong> unwiderruflich gelöscht werden?`,
    confirm: "Löschen",
    cancel:  "Abbrechen",
    danger:  true,
  });
  if (!confirmed) return;

  const res = await api("/api/bib/delete", "POST", { path: f.path });
  if (res.ok) {
    let msg = `${f.name} gelöscht.`;
    if (res.tex_removed)      msg += " · LaTeX-Eintrag entfernt.";
    else if (res.tex_error)   toast(`LaTeX: ${res.tex_error}`, "warning");
    toast(msg, "success");
    // Editor schließen falls diese Datei offen war
    if (state.editorFile?.path === f.path) {
      state.editorDirty = false;
      document.getElementById("editor-overlay").classList.remove("open");
      state.editorFile = null;
    }
    // Library neu laden
    if (document.getElementById("view-library").classList.contains("active")) {
      await loadLibrary();
    }
  } else {
    toast(`Fehler beim Löschen: ${res.error}`, "error");
  }
}

async function promptRenameFile(f) {
  const newName = await showModal({
    icon:    "bi-pencil",
    iconColor: "var(--accent)",
    title:   "Datei umbenennen",
    body:    `Neuer Name für <strong>${escapeHtml(f.name)}</strong>:`,
    confirm: "Umbenennen",
    cancel:  "Abbrechen",
    input:   f.name.replace(/\.bib$/, ""),
    inputPlaceholder: "Dateiname (ohne .bib)",
  });
  if (!newName) return;

  const res = await api("/api/bib/rename", "POST", {
    path:     f.path,
    new_name: newName,
  });
  if (res.ok) {
    toast(`Umbenannt zu: ${res.new_name}`, "success");
    const updatedFile = { ...f, name: res.new_name, path: res.new_path };
    if (state.editorFile?.path === f.path) {
      state.editorFile = updatedFile;
      document.getElementById("editor-filename").textContent = res.new_name;
      document.getElementById("editor-filepath").textContent = res.new_path;
    }
    if (document.getElementById("view-library").classList.contains("active")) {
      await loadLibrary();
    }
  } else {
    toast(`Fehler: ${res.error}`, "error");
  }
}

// ============================================================
// MODAL
// ============================================================
function setupModal() {
  document.getElementById("modal-cancel").addEventListener("click",  () => resolveModal(false));
  document.getElementById("modal-confirm").addEventListener("click", () => {
    const inp = document.getElementById("modal-input");
    resolveModal(inp ? inp.value.trim() || true : true);
  });
}

function resolveModal(value) {
  document.getElementById("modal-backdrop").style.display = "none";
  document.getElementById("modal-extra").innerHTML = "";
  if (state.modalResolve) {
    state.modalResolve(value);
    state.modalResolve = null;
  }
}

function showModal({ icon, iconColor, title, body, confirm, cancel, danger, input, inputPlaceholder } = {}) {
  return new Promise(resolve => {
    state.modalResolve = resolve;

    document.getElementById("modal-icon").className  = `bi ${icon || "bi-question-circle"}`;
    document.getElementById("modal-icon").style.color = iconColor || "var(--warning)";
    document.getElementById("modal-title").textContent = title || "";
    document.getElementById("modal-body").innerHTML   = body  || "";

    const extra = document.getElementById("modal-extra");
    extra.innerHTML = "";
    if (input !== undefined) {
      const inp = document.createElement("input");
      inp.type = "text";
      inp.id   = "modal-input";
      inp.className = "modal-input";
      inp.value = input;
      inp.placeholder = inputPlaceholder || "";
      inp.addEventListener("keydown", e => {
        if (e.key === "Enter") resolveModal(inp.value.trim() || true);
        if (e.key === "Escape") resolveModal(false);
      });
      extra.appendChild(inp);
      setTimeout(() => { inp.focus(); inp.select(); }, 50);
    }

    const confirmBtn = document.getElementById("modal-confirm");
    confirmBtn.textContent = confirm || "OK";
    confirmBtn.className   = danger ? "btn btn-danger" : "btn btn-primary";

    const cancelBtn = document.getElementById("modal-cancel");
    cancelBtn.textContent = cancel || "Abbrechen";

    document.getElementById("modal-backdrop").style.display = "flex";
  });
}

// ============================================================
// HISTORY VIEW
// ============================================================
async function loadHistory() {
  const res = await api("/api/history");
  const container = document.getElementById("history-list");
  container.innerHTML = "";

  if (!res.files || res.files.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <i class="bi bi-inbox"></i>
        <p>Keine .bib-Dateien im Zielverzeichnis vorhanden.</p>
      </div>`;
    return;
  }

  res.files.forEach(f => {
    const item = document.createElement("div");
    item.className = "history-item";
    item.innerHTML = `
      <i class="bi bi-file-earmark-text"></i>
      <div class="history-item-info">
        <div class="history-name">${escapeHtml(f.name)}</div>
        <div class="history-meta">${f.modified} &nbsp;·&nbsp; ${formatSize(f.size)}</div>
      </div>
      <i class="bi bi-chevron-right" style="color:var(--text-muted)"></i>
    `;
    item.addEventListener("click", () => viewFile(f));
    container.appendChild(item);
  });
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

async function viewFile(f) {
  const res = await api("/api/file-content", "POST", { path: f.path });
  document.getElementById("file-viewer-name").textContent = f.name;
  const content = res.content || "(Datei konnte nicht gelesen werden)";
  const el = document.getElementById("file-viewer-content");

  let html = escapeHtml(content);
  html = html.replace(/^(@\w+)\{([^,]+),/m,
    (_, t, k) => `<span class="bib-type">${t}</span>{<span class="bib-key">${k}</span>,`);
  html = html.replace(/^(\s+)(\w+)(\s+=\s+)\{([^}]*)\}(,?)$/gm,
    (_, sp, f2, eq, v, comma) =>
      `${sp}<span class="bib-field">${f2}</span>${eq}{<span class="bib-value">${v}</span>}${comma}`);
  html = html.replace(/(^%[^\n]*)/gm, '<span class="bib-comment">$1</span>');
  el.innerHTML = html;

  document.getElementById("file-viewer-card").style.display = "";
  document.getElementById("file-viewer-card").scrollIntoView({ behavior: "smooth" });
}

document.addEventListener("DOMContentLoaded", () => {
  const refreshHistoryBtn = document.getElementById("btn-refresh-history");
  const closeViewerBtn    = document.getElementById("btn-close-viewer");
  if (refreshHistoryBtn) refreshHistoryBtn.addEventListener("click", loadHistory);
  if (closeViewerBtn)    closeViewerBtn.addEventListener("click", () => {
    document.getElementById("file-viewer-card").style.display = "none";
  });
});

// ============================================================
// SETTINGS VIEW
// ============================================================
function setupSettingsPanel() {
  document.getElementById("btn-save-settings").addEventListener("click", saveSettings);

  document.getElementById("btn-browse-dir").addEventListener("click", async () => {
    const res = await api("/api/browse-directory", "POST", {});
    if (res.path) document.getElementById("setting-target-dir").value = res.path;
  });

  document.getElementById("btn-browse-tex").addEventListener("click", async () => {
    const res = await api("/api/browse-file", "POST", {});
    if (res.path) document.getElementById("setting-latex-main").value = res.path;
  });

  document.getElementById("setting-placement-enabled").addEventListener("change", function () {
    document.getElementById("placement-config").style.display = this.checked ? "" : "none";
  });

  document.getElementById("btn-add-section").addEventListener("click", addSection);

  document.getElementById("btn-check-sections").addEventListener("click", async () => {
    const res = await api("/api/check-latex-sections", "POST", {});
    const container = document.getElementById("found-sections");
    if (!res.sections || res.sections.length === 0) {
      container.innerHTML = `<p class="text-muted small">Keine Kommentare in der LaTeX-Datei gefunden.</p>`;
      return;
    }
    const list = document.createElement("div");
    list.className = "found-section-list";
    res.sections.forEach(s => {
      const pill = document.createElement("span");
      pill.className = "found-section-pill";
      pill.textContent = s;
      pill.addEventListener("click", () => {
        document.getElementById("setting-placement-text").value = s;
      });
      list.appendChild(pill);
    });
    container.innerHTML = "";
    container.appendChild(list);
  });
}

function populateSettingsForm() {
  const s = state.settings;
  document.getElementById("setting-target-dir").value     = s.target_directory || "";
  document.getElementById("setting-latex-main").value     = s.latex_main_path  || "";
  document.getElementById("setting-add-date").checked     = s.add_date_comment !== false;
  document.getElementById("setting-auto-browser").checked = s.auto_open_browser !== false;
  document.getElementById("setting-port").value           = s.port || 5000;

  const pc = s.addbibresource_placement || {};
  document.getElementById("setting-placement-enabled").checked = pc.enabled || false;
  document.getElementById("setting-placement-text").value      = pc.search_text || "";
  document.getElementById("setting-after-last").checked        = pc.after_last_existing !== false;
  document.getElementById("placement-config").style.display    = pc.enabled ? "" : "none";

  // Theme cards sync
  const currentTheme = document.documentElement.getAttribute("data-theme") || "light";
  document.querySelectorAll(".theme-card").forEach(c => {
    c.classList.toggle("active", c.dataset.theme === currentTheme);
  });

  renderSectionsList();
}

async function saveSettings() {
  const pc = {
    enabled:             document.getElementById("setting-placement-enabled").checked,
    search_text:         document.getElementById("setting-placement-text").value,
    after_last_existing: document.getElementById("setting-after-last").checked,
  };

  const newSettings = {
    target_directory:         document.getElementById("setting-target-dir").value.trim(),
    latex_main_path:          document.getElementById("setting-latex-main").value.trim(),
    add_date_comment:         document.getElementById("setting-add-date").checked,
    auto_open_browser:        document.getElementById("setting-auto-browser").checked,
    port:                     parseInt(document.getElementById("setting-port").value) || 5000,
    addbibresource_placement: pc,
    bib_placement_sections:   getSectionsFromDOM(),
  };

  const res = await api("/api/settings", "POST", newSettings);
  state.settings = res.settings;
  updateSectionSelect();

  const msg = document.getElementById("settings-saved-msg");
  msg.style.display = "flex";
  setTimeout(() => msg.style.display = "none", 2500);
  toast("Einstellungen gespeichert!", "success");
}

// ============================================================
// SECTIONS MANAGEMENT
// ============================================================
function renderSectionsList() {
  const container = document.getElementById("sections-list");
  container.innerHTML = "";
  const sections = state.settings.bib_placement_sections || [];
  if (sections.length === 0) {
    container.innerHTML = `<p class="text-muted small">Noch keine Abschnitte definiert.</p>`;
    return;
  }
  sections.forEach((sec) => {
    const row = document.createElement("div");
    row.className = "section-row";
    row.dataset.id = sec.id;
    row.innerHTML = `
      <input type="text" class="form-control" placeholder="Bezeichnung"
             value="${escapeHtml(sec.label)}" data-role="label" />
      <input type="text" class="form-control font-mono" placeholder="Suchtext (z.B. % Bücher)"
             value="${escapeHtml(sec.search_text || "")}" data-role="search" />
      <button class="btn btn-icon" title="Entfernen">
        <i class="bi bi-trash text-danger"></i>
      </button>
    `;
    row.querySelector("button").addEventListener("click", () => row.remove());
    container.appendChild(row);
  });
}

function addSection() {
  const container = document.getElementById("sections-list");
  const empty = container.querySelector(".text-muted");
  if (empty) empty.remove();

  const id  = "s" + Date.now();
  const row = document.createElement("div");
  row.className = "section-row";
  row.dataset.id = id;
  row.innerHTML = `
    <input type="text" class="form-control" placeholder="Bezeichnung" data-role="label" />
    <input type="text" class="form-control font-mono" placeholder="Suchtext (z.B. % Bücher)" data-role="search" />
    <button class="btn btn-icon" title="Entfernen">
      <i class="bi bi-trash text-danger"></i>
    </button>
  `;
  row.querySelector("button").addEventListener("click", () => row.remove());
  container.appendChild(row);
  row.querySelector("[data-role=label]").focus();
}

function getSectionsFromDOM() {
  const rows = document.querySelectorAll("#sections-list .section-row");
  return Array.from(rows).map(row => ({
    id:          row.dataset.id,
    label:       row.querySelector("[data-role=label]")?.value?.trim()  || "",
    search_text: row.querySelector("[data-role=search]")?.value?.trim() || "",
  })).filter(s => s.label);
}

// ============================================================
// TOAST NOTIFICATIONS
// ============================================================
function toast(message, type = "info") {
  const icons = {
    success: "bi-check-circle-fill",
    error:   "bi-x-octagon-fill",
    warning: "bi-exclamation-triangle-fill",
    info:    "bi-info-circle-fill",
  };
  const container = document.getElementById("toast-container");
  const t = document.createElement("div");
  t.className = `toast ${type}`;
  t.innerHTML = `<i class="bi ${icons[type] || icons.info}"></i><span>${escapeHtml(message)}</span>`;
  container.appendChild(t);
  setTimeout(() => {
    t.style.animation = "toastOut .25s ease forwards";
    setTimeout(() => t.remove(), 260);
  }, 3500);
}

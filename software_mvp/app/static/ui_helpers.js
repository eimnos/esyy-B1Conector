
(function () {
  "use strict";

  const MASTER_CODE = "__ALL__";

  function txt(node, value) {
    if (node) {
      node.textContent = value || "";
    }
  }

  function escapeSql(value) {
    return String(value || "").replace(/'/g, "''");
  }

  function isNullOperator(op) {
    return op === "IS NULL" || op === "IS NOT NULL";
  }

  function normalizeEngine(value) {
    return String(value || "").toLowerCase() === "hana" ? "hana" : "sqlserver";
  }

  function qIdent(engine, value) {
    const clean = String(value || "").trim();
    if (!clean) {
      return "";
    }
    return engine === "hana"
      ? `"${clean.replace(/"/g, '""')}"`
      : `[${clean.replace(/\]/g, "]]")}]`;
  }

  function tableRef(engine, schemaName, objectName) {
    return `${qIdent(engine, schemaName)}.${qIdent(engine, objectName)}`;
  }

  function keyOf(schemaName, objectName) {
    return `${schemaName || ""}|${objectName || ""}`;
  }

  function initHints() {
    const hints = Array.from(document.querySelectorAll(".hint"));
    if (!hints.length) {
      return;
    }

    function closeAll(exceptNode) {
      hints.forEach(function (node) {
        if (node !== exceptNode) {
          node.removeAttribute("data-open");
        }
      });
    }

    hints.forEach(function (node) {
      const tip = String(node.getAttribute("data-tip") || node.getAttribute("title") || "").trim();
      if (!tip) {
        return;
      }
      node.setAttribute("data-tip", tip);
      node.setAttribute("aria-label", tip);
      if (!node.hasAttribute("tabindex")) {
        node.setAttribute("tabindex", "0");
      }
      if (node.hasAttribute("title")) {
        node.removeAttribute("title");
      }

      node.addEventListener("click", function (event) {
        event.stopPropagation();
        const isOpen = node.getAttribute("data-open") === "1";
        closeAll(node);
        if (!isOpen) {
          node.setAttribute("data-open", "1");
        }
      });

      node.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          const isOpen = node.getAttribute("data-open") === "1";
          closeAll(node);
          if (!isOpen) {
            node.setAttribute("data-open", "1");
          }
        }
        if (event.key === "Escape") {
          node.removeAttribute("data-open");
        }
      });

      node.addEventListener("blur", function () {
        node.removeAttribute("data-open");
      });
    });

    document.addEventListener("click", function (event) {
      if (!event.target.closest(".hint")) {
        closeAll(null);
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeAll(null);
      }
    });
  }

  function initGuideDrawer() {
    const openBtn = document.querySelector("[data-guide-open]");
    const overlay = document.querySelector("[data-guide-overlay]");
    const drawer = document.querySelector("[data-guide-drawer]");
    const closeBtn = document.querySelector("[data-guide-close]");
    const titleNode = document.querySelector("[data-guide-title]");
    const introNode = document.querySelector("[data-guide-intro]");
    const contentNode = document.querySelector("[data-guide-content]");
    if (!openBtn || !overlay || !drawer || !closeBtn || !titleNode || !introNode || !contentNode) {
      return;
    }

    const activeNav = String(document.body.getAttribute("data-active-nav") || "").trim().toLowerCase();
    const guides = {
      dashboard: {
        title: "Dashboard",
        intro: "Controllo rapido stato configurazione, run e integrita generale.",
        sections: [
          {
            heading: "Check iniziale",
            steps: [
              "Verifica eventuali messaggi rossi in alto.",
              "Controlla i contatori Views/Pipelines/Schedules.",
              "Apri gli ultimi run e cerca eventuali status KO."
            ]
          }
        ]
      },
      views: {
        title: "Views",
        intro: "Definisci la query sorgente (SQL Server o HANA) che alimenta le pipeline managed.",
        sections: [
          {
            heading: "Procedura consigliata",
            steps: [
              "Usa il Query Builder per impostare FROM, JOIN e filtri base.",
              "Rifinisci manualmente l'SQL solo se serve.",
              "Salva la view e poi usa Publish per creare/aggiornare la view sul DB sorgente."
            ]
          }
        ]
      },
      pipelines: {
        title: "Pipelines",
        intro: "Collega una view sorgente a una tabella BigQuery target.",
        sections: [
          {
            heading: "Managed mode",
            steps: [
              "Lascia vuoto il campo Command.",
              "Seleziona la view sorgente.",
              "Imposta dataset/tabella BigQuery e write mode.",
              "Esegui Run e controlla il log di esito."
            ]
          }
        ]
      },
      schedules: {
        title: "Schedules",
        intro: "Automatizza i run pipeline con cron + timezone.",
        sections: [
          {
            heading: "Cron pratico",
            steps: [
              "Usa il Cron Builder per generare l'espressione senza scriverla a mano.",
              "Formato: minuto ora giorno mese giorno-settimana.",
              "Esempio ogni 30 minuti: */30 * * * *.",
              "Usa timezone coerente con il contesto cliente (es. Europe/Rome)."
            ]
          }
        ]
      },
      acl: {
        title: "ACL",
        intro: "Gestisci accessi per utente Looker Studio in base al codice cliente.",
        sections: [
          {
            heading: "Regole (legacy + generiche)",
            steps: [
              "Per il caso storico usa ACL legacy su customer_code.",
              "Per nuovi clienti usa ACL generica: seleziona vista, campo, operatore e valore.",
              "Sincronizza ACL su BigQuery dopo modifiche (automatico o pulsante manuale)."
            ]
          }
        ]
      },
      users: {
        title: "Users",
        intro: "Gestione utenti applicazione e ruoli operativi.",
        sections: [
          {
            heading: "Ruoli",
            steps: [
              "Admin: pieno controllo.",
              "Operator: operativo ma senza gestione Users/Settings.",
              "Viewer: sola lettura."
            ]
          }
        ]
      },
      settings: {
        title: "Settings Wizard",
        intro: "Configurazione guidata in step, dalla connessione sorgente fino al setup BigQuery.",
        sections: [
          {
            heading: "Step 1 - Database sorgente",
            steps: [
              "Apri wizard DB e scegli SQL Server o SAP HANA.",
              "Compila host/istanza/porta, database, utente e password.",
              "Applica la stringa e lancia il Test connessione."
            ]
          },
          {
            heading: "Step 2 - Attiva BigQuery (Google Cloud Console)",
            steps: [
              "Vai su console.cloud.google.com e seleziona il progetto cliente.",
              "Menu in alto a sinistra -> Billing -> collega un account di fatturazione.",
              "Menu -> APIs & Services -> Library -> cerca BigQuery API -> Enable.",
              "Menu -> IAM & Admin -> Service Accounts -> Create Service Account.",
              "Assegna ruoli: BigQuery Job User + BigQuery Data Editor.",
              "Apri il service account -> Keys -> Add Key -> Create new key -> JSON.",
              "Salva il file JSON sul server app, es. C:\\BigQuery\\chiave_cliente.json."
            ]
          },
          {
            heading: "Step 3 - Setup automatico BigQuery in app",
            steps: [
              "Compila Project ID, Dataset, Location e path JSON.",
              "Clicca Esegui setup automatico BigQuery.",
              "Il wizard salva config, testa connessione e crea/valida il dataset."
            ]
          },
          {
            heading: "Step 4 - Verifica finale",
            steps: [
              "Crea una pipeline managed e lancia Run.",
              "Controlla che il log segnali righe caricate in BigQuery.",
              "Verifica in BigQuery che la tabella target sia aggiornata."
            ]
          }
        ]
      },
      fallback: {
        title: "Guida",
        intro: "Indicazioni operative base per la pagina corrente.",
        sections: [
          {
            heading: "Uso rapido",
            steps: [
              "Compila i campi con i tooltip di supporto.",
              "Salva e poi testa la configurazione.",
              "In caso errore, controlla i log uvicorn sul server."
            ]
          }
        ]
      }
    };

    function renderGuide(data) {
      titleNode.textContent = data.title || "Guida";
      introNode.textContent = data.intro || "";
      contentNode.innerHTML = "";
      (data.sections || []).forEach(function (section) {
        const block = document.createElement("section");
        block.className = "guide-block";
        const h = document.createElement("h4");
        h.textContent = section.heading || "";
        block.appendChild(h);
        const ol = document.createElement("ol");
        (section.steps || []).forEach(function (step) {
          const li = document.createElement("li");
          li.textContent = step;
          ol.appendChild(li);
        });
        block.appendChild(ol);
        contentNode.appendChild(block);
      });
    }

    function openDrawer() {
      const data = guides[activeNav] || guides.fallback;
      renderGuide(data);
      drawer.classList.add("open");
      overlay.hidden = false;
      overlay.classList.add("open");
      drawer.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
    }

    function closeDrawer() {
      drawer.classList.remove("open");
      overlay.classList.remove("open");
      drawer.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
      setTimeout(function () {
        if (!overlay.classList.contains("open")) {
          overlay.hidden = true;
        }
      }, 180);
    }

    openBtn.addEventListener("click", openDrawer);
    closeBtn.addEventListener("click", closeDrawer);
    overlay.addEventListener("click", closeDrawer);
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && drawer.classList.contains("open")) {
        closeDrawer();
      }
    });
  }

  async function fetchJson(url) {
    const response = await fetch(url, { credentials: "same-origin" });
    let payload = {};
    try {
      payload = await response.json();
    } catch (err) {
      payload = {};
    }
    if (!response.ok) {
      throw new Error(payload.detail || "Richiesta non riuscita.");
    }
    return payload;
  }

  function initAclMasterToggle(form) {
    const master = form.querySelector("[data-acl-master]");
    const customer = form.querySelector("[data-acl-customer]");
    if (!master || !customer) {
      return;
    }

    const applyState = function () {
      if (master.checked) {
        customer.dataset.prevValue = customer.value || "";
        customer.value = MASTER_CODE;
        customer.readOnly = true;
        customer.required = false;
      } else {
        if ((customer.value || "").trim().toUpperCase() === MASTER_CODE) {
          customer.value = customer.dataset.prevValue || "";
        }
        customer.readOnly = false;
        customer.required = true;
      }
    };

    master.addEventListener("change", applyState);
    applyState();
  }

  function initAclFilterBuilder(form) {
    const view = form.querySelector("[data-acl-filter-view]");
    const field = form.querySelector("[data-acl-filter-field]");
    const operator = form.querySelector("[data-acl-filter-operator]");
    const value = form.querySelector("[data-acl-filter-value]");
    const master = form.querySelector("[data-acl-filter-master]");
    const status = form.querySelector("[data-acl-filter-status]");
    if (!view || !field || !operator || !value || !master) {
      return;
    }

    function setStatus(message, isError) {
      if (!status) {
        return;
      }
      status.textContent = message || "";
      status.style.color = isError ? "#8f2a24" : "";
    }

    function applyMasterState() {
      const disabled = !!master.checked;
      field.disabled = disabled;
      operator.disabled = disabled;
      value.disabled = disabled;
      if (disabled) {
        setStatus("Master attivo: filtro campo/operatore/valore disattivato.", false);
      } else {
        setStatus("", false);
      }
    }

    async function loadColumns() {
      const viewId = String(view.value || "").trim();
      if (!viewId) {
        field.innerHTML = '<option value=\"\">-- seleziona vista --</option>';
        return;
      }
      setStatus("Carico campi vista...", false);
      try {
        const payload = await fetchJson(`/api/acl/view-columns?view_id=${encodeURIComponent(viewId)}`);
        const cols = payload.columns || [];
        field.innerHTML = "";
        if (!cols.length) {
          const opt = document.createElement("option");
          opt.value = "";
          opt.textContent = "-- nessun campo disponibile --";
          field.appendChild(opt);
          setStatus("Nessun campo disponibile sulla vista selezionata.", true);
          return;
        }
        cols.forEach(function (col) {
          const opt = document.createElement("option");
          opt.value = col.column_name;
          opt.textContent = `${col.column_name}${col.data_type ? " (" + col.data_type + ")" : ""}`;
          field.appendChild(opt);
        });
        setStatus(`Campi caricati: ${cols.length}`, false);
      } catch (err) {
        field.innerHTML = '<option value=\"\">-- errore caricamento campi --</option>';
        setStatus(err.message || "Errore caricamento campi.", true);
      }
      applyMasterState();
    }

    view.addEventListener("change", loadColumns);
    master.addEventListener("change", applyMasterState);
    applyMasterState();
    loadColumns();
  }

  function initLockForms() {
    document.querySelectorAll("[data-lock-form]").forEach(function (form) {
      const fieldset = form.querySelector("[data-lock-fieldset]");
      const toggle = form.querySelector("[data-lock-toggle]");
      const save = form.querySelector("[data-lock-save]");
      if (!fieldset || !toggle || !save) {
        return;
      }

      let locked = String(form.getAttribute("data-start-locked") || "1") !== "0";
      function applyState() {
        form.classList.toggle("is-locked", locked);
        fieldset.disabled = locked;
        save.disabled = locked;
        toggle.textContent = locked ? "Modifica" : "Blocca campi";
      }

      toggle.addEventListener("click", function () {
        locked = !locked;
        applyState();
      });

      form.addEventListener("submit", function () {
        fieldset.disabled = false;
      });

      applyState();
    });
  }

  function initCronBuilders() {
    function clampInt(raw, min, max, fallback) {
      const n = Number.parseInt(String(raw || "").trim(), 10);
      if (Number.isNaN(n)) {
        return fallback;
      }
      return Math.min(max, Math.max(min, n));
    }

    document.querySelectorAll("[data-cron-builder]").forEach(function (root) {
      const form = root.closest("form");
      const targetFieldName = root.getAttribute("data-cron-target") || "cron_expression";
      const targetInput = form ? form.querySelector(`[name='${targetFieldName}']`) : null;
      const mode = root.querySelector("[data-cron-mode]");
      const every = root.querySelector("[data-cron-every]");
      const minute = root.querySelector("[data-cron-minute]");
      const hour = root.querySelector("[data-cron-hour]");
      const weekday = root.querySelector("[data-cron-weekday]");
      const monthday = root.querySelector("[data-cron-monthday]");
      const generate = root.querySelector("[data-cron-generate]");
      const preview = root.querySelector("[data-cron-preview]");
      const groups = root.querySelectorAll("[data-cron-group]");

      if (!targetInput || !mode || !generate || !preview) {
        return;
      }

      function syncVisibility() {
        const current = mode.value;
        groups.forEach(function (group) {
          const allowed = String(group.getAttribute("data-mode") || "")
            .split(",")
            .map(function (x) { return x.trim(); })
            .filter(Boolean);
          group.classList.toggle("is-hidden", allowed.indexOf(current) === -1);
        });
      }

      function buildCron() {
        const current = mode.value;
        const n = clampInt(every ? every.value : "30", 1, 59, 30);
        const mm = clampInt(minute ? minute.value : "0", 0, 59, 0);
        const hh = clampInt(hour ? hour.value : "7", 0, 23, 7);
        const wd = clampInt(weekday ? weekday.value : "1", 0, 6, 1);
        const dm = clampInt(monthday ? monthday.value : "1", 1, 31, 1);

        if (current === "every_n_minutes") {
          return `*/${n} * * * *`;
        }
        if (current === "hourly") {
          return `${mm} * * * *`;
        }
        if (current === "daily") {
          return `${mm} ${hh} * * *`;
        }
        if (current === "weekly") {
          return `${mm} ${hh} * * ${wd}`;
        }
        if (current === "monthly") {
          return `${mm} ${hh} ${dm} * *`;
        }
        return "0 * * * *";
      }

      function updatePreview() {
        const cron = buildCron();
        preview.textContent = `Cron suggerito: ${cron}`;
      }

      mode.addEventListener("change", function () {
        syncVisibility();
        updatePreview();
      });
      [every, minute, hour, weekday, monthday].forEach(function (node) {
        if (node) {
          node.addEventListener("input", updatePreview);
          node.addEventListener("change", updatePreview);
        }
      });

      generate.addEventListener("click", function () {
        const cron = buildCron();
        targetInput.value = cron;
        updatePreview();
      });

      syncVisibility();
      updatePreview();
    });
  }

  function templatesForEngine(engine) {
    if (engine === "hana") {
      return {
        basic: 'SELECT\n  *\nFROM "SCHEMA"."TABELLA";',
        date_range:
          'SELECT\n  T0.*\nFROM "SCHEMA"."TABELLA" AS T0\nWHERE T0."DocDate" >= ADD_DAYS(CURRENT_DATE, -30);',
        join:
          'SELECT\n  T0."DocNum",\n  T0."CardCode",\n  T1."ItemCode",\n  T1."Quantity"\nFROM "SCHEMA"."ORDR" AS T0\nINNER JOIN "SCHEMA"."RDR1" AS T1 ON T1."DocEntry" = T0."DocEntry"\nWHERE T0."CANCELED" = \'N\';',
      };
    }

    return {
      basic: "SELECT\n  *\nFROM [dbo].[TABELLA];",
      date_range:
        "SELECT\n  T0.*\nFROM [dbo].[TABELLA] AS T0\nWHERE T0.[DocDate] >= DATEADD(day, -30, CAST(GETDATE() AS date));",
      join:
        "SELECT\n  T0.[DocNum],\n  T0.[CardCode],\n  T1.[ItemCode],\n  T1.[Quantity]\nFROM [dbo].[ORDR] AS T0\nINNER JOIN [dbo].[RDR1] AS T1 ON T1.[DocEntry] = T0.[DocEntry]\nWHERE T0.[CANCELED] = 'N';",
    };
  }

  function initSqlBuilder(form) {
    const editor = form.querySelector("[data-sql-editor]");
    if (!editor) {
      return;
    }

    const root = form.querySelector("[data-query-builder]");
    const tplButtons = form.querySelectorAll("[data-sql-template]");
    const generateBtn = form.querySelector("[data-qb-generate]");

    const state = {
      engine: "sqlserver",
      objects: [],
      columns: {},
      selectedObject: null,
      base: null,
      joinCandidate: null,
      joins: [],
      fields: [],
      filters: [],
      contextLoaded: false,
      searchTimer: null,
    };

    function applyTemplate(key) {
      const templates = templatesForEngine(state.engine);
      if (templates[key]) {
        editor.value = templates[key];
      }
    }

    tplButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        const key = btn.getAttribute("data-sql-template");
        applyTemplate(key);
      });
    });

    if (!root) {
      return;
    }

    const refs = {
      search: root.querySelector("[data-qb-search]"),
      searchSuggestions: root.querySelector("[data-qb-search-suggestions]"),
      searchBtn: root.querySelector("[data-qb-search-btn]"),
      refreshBtn: root.querySelector("[data-qb-refresh]"),
      status: root.querySelector("[data-qb-status]"),
      engine: root.querySelector("[data-qb-engine]"),
      error: root.querySelector("[data-qb-error]"),
      objects: root.querySelector("[data-qb-objects]"),
      selectedObject: root.querySelector("[data-qb-selected-object]"),
      selectedColumns: root.querySelector("[data-qb-selected-columns]"),
      setBaseBtn: root.querySelector("[data-qb-set-base]"),
      useJoinBtn: root.querySelector("[data-qb-use-join]"),
      addColumnsBtn: root.querySelector("[data-qb-add-columns]"),
      rowLimit: root.querySelector("[data-qb-row-limit]"),
      baseDisplay: root.querySelector("[data-qb-base-display]"),
      joinTarget: root.querySelector("[data-qb-join-target]"),
      joinType: root.querySelector("[data-qb-join-type]"),
      joinOperator: root.querySelector("[data-qb-join-operator]"),
      joinLeft: root.querySelector("[data-qb-join-left]"),
      joinRight: root.querySelector("[data-qb-join-right]"),
      addJoinBtn: root.querySelector("[data-qb-add-join]"),
      joinsList: root.querySelector("[data-qb-joins]"),
      filterLogic: root.querySelector("[data-qb-filter-logic]"),
      filterField: root.querySelector("[data-qb-filter-field]"),
      filterOperator: root.querySelector("[data-qb-filter-operator]"),
      filterValueType: root.querySelector("[data-qb-filter-value-type]"),
      filterValue: root.querySelector("[data-qb-filter-value]"),
      addFilterBtn: root.querySelector("[data-qb-add-filter]"),
      filtersList: root.querySelector("[data-qb-filters]"),
      fieldsList: root.querySelector("[data-qb-fields]"),
      clearFieldsBtn: root.querySelector("[data-qb-clear-fields]"),
    };

    function setError(message) {
      txt(refs.error, message);
    }

    function emptyBox(container, message) {
      container.innerHTML = "";
      const row = document.createElement("div");
      row.className = "muted";
      row.textContent = message;
      container.appendChild(row);
    }
    function aliasFor(schemaName, objectName) {
      if (state.base && keyOf(state.base.schema_name, state.base.object_name) === keyOf(schemaName, objectName)) {
        return "T0";
      }
      for (let i = 0; i < state.joins.length; i += 1) {
        const join = state.joins[i];
        if (keyOf(join.schema_name, join.object_name) === keyOf(schemaName, objectName)) {
          return join.alias;
        }
      }
      return null;
    }

    function nextJoinAlias() {
      return `T${state.joins.length + 1}`;
    }

    function columnsFor(schemaName, objectName) {
      return state.columns[keyOf(schemaName, objectName)] || [];
    }

    function refreshBase() {
      refs.baseDisplay.value = state.base ? `T0 -> ${state.base.schema_name}.${state.base.object_name}` : "";
    }

    function refreshJoinCandidate() {
      refs.joinTarget.value = state.joinCandidate
        ? `${nextJoinAlias()} -> ${state.joinCandidate.schema_name}.${state.joinCandidate.object_name}`
        : "";
    }

    function availableColumns() {
      const rows = [];
      if (state.base) {
        columnsFor(state.base.schema_name, state.base.object_name).forEach(function (col) {
          rows.push({
            alias: "T0",
            column_name: col.column_name,
            expression: `T0.${qIdent(state.engine, col.column_name)}`,
            label: `T0.${col.column_name}`,
          });
        });
      }
      state.joins.forEach(function (join) {
        columnsFor(join.schema_name, join.object_name).forEach(function (col) {
          rows.push({
            alias: join.alias,
            column_name: col.column_name,
            expression: `${join.alias}.${qIdent(state.engine, col.column_name)}`,
            label: `${join.alias}.${col.column_name}`,
          });
        });
      });
      return rows;
    }

    async function ensureColumns(objectRow) {
      const key = keyOf(objectRow.schema_name, objectRow.object_name);
      if (state.columns[key]) {
        return;
      }
      const params = new URLSearchParams({
        schema_name: objectRow.schema_name,
        object_name: objectRow.object_name,
      });
      const payload = await fetchJson(`/api/query-builder/columns?${params.toString()}`);
      state.columns[key] = payload.columns || [];
    }

    function renderObjects() {
      refs.objects.innerHTML = "";
      if (!state.objects.length) {
        emptyBox(refs.objects, "Nessun oggetto trovato.");
        return;
      }
      state.objects.forEach(function (obj) {
        const item = document.createElement("div");
        item.className = "qb-item";
        if (state.selectedObject && keyOf(state.selectedObject.schema_name, state.selectedObject.object_name) === keyOf(obj.schema_name, obj.object_name)) {
          item.classList.add("active");
        }
        const left = document.createElement("div");
        const name = document.createElement("div");
        name.textContent = `${obj.schema_name}.${obj.object_name}`;
        const meta = document.createElement("div");
        meta.className = "qb-item-meta";
        meta.textContent = obj.object_type;
        left.appendChild(name);
        left.appendChild(meta);
        item.appendChild(left);
        item.addEventListener("click", function () {
          selectObject(obj);
        });
        refs.objects.appendChild(item);
      });
    }

    function renderSearchSuggestions() {
      if (!refs.searchSuggestions) {
        return;
      }
      refs.searchSuggestions.innerHTML = "";
      const maxItems = Math.min(state.objects.length, 40);
      for (let i = 0; i < maxItems; i += 1) {
        const obj = state.objects[i];
        const opt = document.createElement("option");
        opt.value = `${obj.schema_name}.${obj.object_name}`;
        refs.searchSuggestions.appendChild(opt);
      }
    }

    async function selectObject(obj) {
      state.selectedObject = obj;
      renderObjects();
      txt(refs.selectedObject, `${obj.schema_name}.${obj.object_name} (${obj.object_type})`);
      setError("");
      try {
        await ensureColumns(obj);
      } catch (err) {
        setError(err.message);
      }
      renderSelectedColumns();
    }

    function renderSelectedColumns() {
      refs.selectedColumns.innerHTML = "";
      if (!state.selectedObject) {
        emptyBox(refs.selectedColumns, "Seleziona una tabella/view.");
        return;
      }
      const cols = columnsFor(state.selectedObject.schema_name, state.selectedObject.object_name);
      if (!cols.length) {
        emptyBox(refs.selectedColumns, "Nessuna colonna disponibile.");
        return;
      }
      cols.forEach(function (col) {
        const row = document.createElement("label");
        row.className = "inline-check";
        const chk = document.createElement("input");
        chk.type = "checkbox";
        chk.dataset.columnName = col.column_name;
        const span = document.createElement("span");
        span.textContent = `${col.column_name} (${col.data_type})`;
        row.appendChild(chk);
        row.appendChild(span);
        refs.selectedColumns.appendChild(row);
      });
    }

    function renderJoinSelectors() {
      refs.joinLeft.innerHTML = "";
      const leftCols = availableColumns();
      if (!leftCols.length) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "-- imposta FROM prima --";
        refs.joinLeft.appendChild(opt);
      } else {
        leftCols.forEach(function (col) {
          const opt = document.createElement("option");
          opt.value = col.expression;
          opt.textContent = col.label;
          refs.joinLeft.appendChild(opt);
        });
      }

      refs.joinRight.innerHTML = "";
      if (!state.joinCandidate) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "-- prepara JOIN da catalogo --";
        refs.joinRight.appendChild(opt);
        return;
      }
      const rightCols = columnsFor(state.joinCandidate.schema_name, state.joinCandidate.object_name);
      if (!rightCols.length) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "-- nessuna colonna --";
        refs.joinRight.appendChild(opt);
        return;
      }
      rightCols.forEach(function (col) {
        const opt = document.createElement("option");
        opt.value = col.column_name;
        opt.textContent = col.column_name;
        refs.joinRight.appendChild(opt);
      });
    }

    function renderLines(container, rows, emptyMessage, onRemove) {
      container.innerHTML = "";
      if (!rows.length) {
        emptyBox(container, emptyMessage);
        return;
      }
      rows.forEach(function (row, idx) {
        const line = document.createElement("div");
        line.className = "qb-line";
        const code = document.createElement("code");
        code.textContent = row;
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn danger btn-xs";
        btn.textContent = "Rimuovi";
        btn.addEventListener("click", function () {
          onRemove(idx);
        });
        line.appendChild(code);
        line.appendChild(btn);
        container.appendChild(line);
      });
    }
    function refreshFilterFields() {
      refs.filterField.innerHTML = "";
      const cols = availableColumns();
      if (!cols.length) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "-- imposta FROM/JOIN --";
        refs.filterField.appendChild(opt);
        return;
      }
      cols.forEach(function (col) {
        const opt = document.createElement("option");
        opt.value = col.expression;
        opt.dataset.alias = col.alias;
        opt.textContent = col.label;
        refs.filterField.appendChild(opt);
      });
    }

    function toggleFilterValue() {
      const disabled = isNullOperator(refs.filterOperator.value);
      refs.filterValue.disabled = disabled;
      if (disabled) {
        refs.filterValue.value = "";
      }
    }

    function literal(valueType, operator, rawValue) {
      const clean = String(rawValue || "").trim();
      if (isNullOperator(operator)) {
        return "";
      }
      if (operator === "IN") {
        const parts = clean.split(",").map(function (v) { return v.trim(); }).filter(Boolean);
        if (!parts.length) {
          return "(NULL)";
        }
        return `(${parts.map(function (v) { return literal(valueType, "=", v); }).join(", ")})`;
      }
      if (valueType === "raw") {
        return clean;
      }
      if (valueType === "number") {
        return /^-?\d+(\.\d+)?$/.test(clean) ? clean : "0";
      }
      return `'${escapeSql(clean)}'`;
    }

    function limitValue() {
      const raw = String(refs.rowLimit.value || "").trim();
      return /^\d+$/.test(raw) ? raw : "";
    }

    function renderJoins() {
      const rows = state.joins.map(function (join) {
        return `${join.join_type} ${join.alias} (${join.schema_name}.${join.object_name}) ON ${join.left_expression} ${join.operator} ${join.right_expression}`;
      });
      renderLines(refs.joinsList, rows, "Nessun JOIN configurato.", function (index) {
        const removedAlias = state.joins[index].alias;
        state.joins.splice(index, 1);
        state.fields = state.fields.filter(function (f) { return f.alias !== removedAlias; });
        state.filters = state.filters.filter(function (f) { return f.alias !== removedAlias; });
        renderJoins();
        renderFields();
        renderFilters();
        renderJoinSelectors();
        refreshFilterFields();
        generateSql();
      });
    }

    function renderFields() {
      const rows = state.fields.map(function (field) { return field.expression; });
      renderLines(refs.fieldsList, rows, "Nessun campo selezionato. Sara usato T0.*", function (index) {
        state.fields.splice(index, 1);
        renderFields();
        generateSql();
      });
    }

    function renderFilters() {
      const rows = state.filters.map(function (filterRow, index) {
        return (index === 0 ? "" : `${filterRow.logic} `) + filterRow.preview;
      });
      renderLines(refs.filtersList, rows, "Nessun filtro WHERE configurato.", function (index) {
        state.filters.splice(index, 1);
        renderFilters();
        generateSql();
      });
    }

    function generateSql() {
      if (!state.base) {
        return false;
      }
      const lines = [];
      const lim = limitValue();
      const selectCols = state.fields.length ? state.fields.map(function (f) { return f.expression; }) : ["T0.*"];

      lines.push("SELECT");
      if (state.engine === "sqlserver" && lim) {
        lines.push(`  TOP ${lim} ${selectCols.join(",\n  ")}`);
      } else {
        lines.push(`  ${selectCols.join(",\n  ")}`);
      }
      lines.push(`FROM ${tableRef(state.engine, state.base.schema_name, state.base.object_name)} AS T0`);

      state.joins.forEach(function (join) {
        lines.push(`${join.join_type} ${tableRef(state.engine, join.schema_name, join.object_name)} AS ${join.alias} ON ${join.left_expression} ${join.operator} ${join.right_expression}`);
      });

      if (state.filters.length) {
        lines.push("WHERE");
        state.filters.forEach(function (filterRow, index) {
          const prefix = index === 0 ? "  " : `  ${filterRow.logic} `;
          lines.push(`${prefix}${filterRow.preview}`);
        });
      }

      if (state.engine === "hana" && lim) {
        lines.push(`LIMIT ${lim}`);
      }
      lines[lines.length - 1] += ";";
      editor.value = lines.join("\n");
      return true;
    }

    function addSelectedColumns() {
      if (!state.selectedObject) {
        setError("Seleziona prima una tabella/view dal catalogo.");
        return;
      }
      const alias = aliasFor(state.selectedObject.schema_name, state.selectedObject.object_name);
      if (!alias) {
        setError("Imposta l'oggetto come FROM o aggiungilo prima come JOIN.");
        return;
      }

      const checks = refs.selectedColumns.querySelectorAll("input[type='checkbox']:checked");
      if (!checks.length) {
        setError("Seleziona almeno una colonna.");
        return;
      }

      checks.forEach(function (check) {
        const col = check.dataset.columnName || "";
        const expression = `${alias}.${qIdent(state.engine, col)}`;
        const already = state.fields.some(function (item) { return item.expression === expression; });
        if (!already) {
          state.fields.push({ alias: alias, expression: expression });
        }
        check.checked = false;
      });

      setError("");
      renderFields();
      generateSql();
    }

    function setBase() {
      if (!state.selectedObject) {
        setError("Seleziona prima una tabella/view dal catalogo.");
        return;
      }
      const currentBaseKey = state.base ? keyOf(state.base.schema_name, state.base.object_name) : "";
      const nextBaseKey = keyOf(state.selectedObject.schema_name, state.selectedObject.object_name);
      if (currentBaseKey !== nextBaseKey) {
        state.joins = [];
        state.fields = [];
        state.filters = [];
      }
      state.base = {
        schema_name: state.selectedObject.schema_name,
        object_name: state.selectedObject.object_name,
        object_type: state.selectedObject.object_type,
      };
      state.joinCandidate = null;
      setError("");
      refreshBase();
      refreshJoinCandidate();
      renderJoins();
      renderFields();
      renderFilters();
      renderJoinSelectors();
      refreshFilterFields();
      generateSql();
    }

    function useJoin() {
      if (!state.base) {
        setError("Imposta prima la tabella FROM.");
        return;
      }
      if (!state.selectedObject) {
        setError("Seleziona una tabella/view da usare nel JOIN.");
        return;
      }
      if (keyOf(state.base.schema_name, state.base.object_name) === keyOf(state.selectedObject.schema_name, state.selectedObject.object_name)) {
        setError("La tabella JOIN deve essere diversa dal FROM.");
        return;
      }
      state.joinCandidate = {
        schema_name: state.selectedObject.schema_name,
        object_name: state.selectedObject.object_name,
        object_type: state.selectedObject.object_type,
      };
      setError("");
      refreshJoinCandidate();
      renderJoinSelectors();
    }
    function addJoin() {
      if (!state.base) {
        setError("Imposta prima la tabella FROM.");
        return;
      }
      if (!state.joinCandidate) {
        setError("Seleziona una tabella e clicca 'Prepara JOIN'.");
        return;
      }
      const candidateKey = keyOf(state.joinCandidate.schema_name, state.joinCandidate.object_name);
      const duplicate = state.joins.some(function (join) {
        return keyOf(join.schema_name, join.object_name) === candidateKey;
      });
      if (duplicate) {
        setError("JOIN gia presente per questa tabella/view.");
        return;
      }

      const leftExpression = refs.joinLeft.value || "";
      const rightColumn = refs.joinRight.value || "";
      const joinType = refs.joinType.value || "INNER JOIN";
      const joinOperator = refs.joinOperator.value || "=";
      if (!leftExpression || !rightColumn) {
        setError("Compila i campi di condizione JOIN.");
        return;
      }

      const alias = nextJoinAlias();
      state.joins.push({
        schema_name: state.joinCandidate.schema_name,
        object_name: state.joinCandidate.object_name,
        alias: alias,
        join_type: joinType,
        operator: joinOperator,
        left_expression: leftExpression,
        right_expression: `${alias}.${qIdent(state.engine, rightColumn)}`,
      });
      state.joinCandidate = null;
      setError("");
      refreshJoinCandidate();
      renderJoinSelectors();
      refreshFilterFields();
      renderJoins();
      generateSql();
    }

    function addFilter() {
      const fieldExpression = refs.filterField.value || "";
      const logic = refs.filterLogic.value || "AND";
      const operator = refs.filterOperator.value || "=";
      const valueType = refs.filterValueType.value || "string";
      const value = refs.filterValue.value || "";
      if (!fieldExpression) {
        setError("Seleziona un campo per il filtro WHERE.");
        return;
      }
      if (!isNullOperator(operator) && !String(value).trim()) {
        setError("Inserisci un valore per il filtro.");
        return;
      }
      const preview = isNullOperator(operator)
        ? `${fieldExpression} ${operator}`
        : `${fieldExpression} ${operator} ${literal(valueType, operator, value)}`;
      state.filters.push({
        logic: logic,
        alias: fieldExpression.split(".")[0],
        preview: preview,
      });
      refs.filterValue.value = "";
      setError("");
      renderFilters();
      generateSql();
    }

    async function loadCatalog(options) {
      const opts = options || {};
      setError("");
      if (!state.contextLoaded || opts.forceContext) {
        try {
          const context = await fetchJson("/api/query-builder/context");
          state.engine = normalizeEngine(context.engine);
          state.contextLoaded = true;
        } catch (err) {
          state.engine = "sqlserver";
          setError(err.message);
        }
      }
      txt(refs.engine, state.engine);

      const params = new URLSearchParams({
        search: String(refs.search.value || "").trim(),
        limit: "250",
      });
      try {
        const payload = await fetchJson(`/api/query-builder/objects?${params.toString()}`);
        state.engine = normalizeEngine(payload.engine || state.engine);
        state.objects = payload.objects || [];
        txt(refs.status, `Oggetti caricati: ${state.objects.length}`);
      } catch (err) {
        state.objects = [];
        txt(refs.status, "Errore caricamento catalogo.");
        setError(err.message);
      }
      txt(refs.engine, state.engine);
      renderObjects();
      renderSearchSuggestions();
    }

    function scheduleCatalogLoad() {
      if (state.searchTimer) {
        clearTimeout(state.searchTimer);
      }
      state.searchTimer = setTimeout(function () {
        loadCatalog();
      }, 280);
    }

    refs.searchBtn.addEventListener("click", loadCatalog);
    refs.refreshBtn.addEventListener("click", function () {
      refs.search.value = "";
      loadCatalog();
    });
    refs.search.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        loadCatalog();
      }
    });
    refs.search.addEventListener("input", function () {
      scheduleCatalogLoad();
    });
    refs.search.addEventListener("change", function () {
      loadCatalog();
    });
    refs.setBaseBtn.addEventListener("click", setBase);
    refs.useJoinBtn.addEventListener("click", useJoin);
    refs.addColumnsBtn.addEventListener("click", addSelectedColumns);
    refs.addJoinBtn.addEventListener("click", addJoin);
    refs.addFilterBtn.addEventListener("click", addFilter);
    refs.clearFieldsBtn.addEventListener("click", function () {
      state.fields = [];
      renderFields();
      generateSql();
    });
    refs.filterOperator.addEventListener("change", toggleFilterValue);

    if (generateBtn) {
      generateBtn.addEventListener("click", function () {
        if (!generateSql()) {
          setError("Imposta almeno una tabella FROM per generare la query.");
        }
      });
    }

    refreshBase();
    refreshJoinCandidate();
    renderJoinSelectors();
    refreshFilterFields();
    renderJoins();
    renderFields();
    renderFilters();
    toggleFilterValue();
    loadCatalog();
  }

  initHints();
  initGuideDrawer();
  initLockForms();
  initCronBuilders();
  document.querySelectorAll("[data-acl-form]").forEach(initAclMasterToggle);
  document.querySelectorAll("[data-acl-filter-form]").forEach(initAclFilterBuilder);
  document.querySelectorAll("[data-sql-builder]").forEach(initSqlBuilder);
})();

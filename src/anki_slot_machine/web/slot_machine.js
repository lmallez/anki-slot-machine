(function () {
  function addonPackageFromScript() {
    const currentScript = document.currentScript;
    const source = currentScript && currentScript.src ? String(currentScript.src) : "";
    const match = source.match(/\/_addons\/([^/]+)\/web\/slot_machine\.js/);
    return match ? decodeURIComponent(match[1]) : "anki_slot_machine";
  }

  function instanceKeyForPackage(packageName) {
    return String(packageName || "anki_slot_machine");
  }

  const ADDON_PACKAGE = addonPackageFromScript();
  const INSTANCE_KEY = instanceKeyForPackage(ADDON_PACKAGE);

  window.AnkiSlotMachineInstances = window.AnkiSlotMachineInstances || {};
  if (window.AnkiSlotMachineInstances[INSTANCE_KEY]) {
    return;
  }

  const PREFIX = `anki-slot-machine:${INSTANCE_KEY}`;
  const SYMBOLS = ["slot_1", "slot_2", "slot_3", "slot_4", "slot_5"];
  const DEFAULT_WIDTH = 316;
  const DEFAULT_HEIGHT = 480;
  const WINDOW_RATIO = DEFAULT_HEIGHT / DEFAULT_WIDTH;
  const MIN_WIDTH = 100;
  const MAX_WIDTH = 420;
  const VIEWPORT_MARGIN = 12;
  const defaultMoney = "1.00";
  const defaultMultiplier = "0.00";
  const CONTROL_PANEL_STORAGE_KEY = `anki-slot-machine-control-panel-v1:${INSTANCE_KEY}`;
  const machineViews = {};
  let controlPanel = null;
  let closeAllConfirmOpen = false;
  let lastSyncedMachineCount = 0;
  let controlPanelCollapsed = false;
  let interaction = null;
  let hasHydratedLayouts = false;
  let windowEventsBound = false;

  function send(command, value) {
    if (typeof pycmd !== "function") {
      return;
    }
    const suffix = value === undefined ? command : `${command}:${value}`;
    pycmd(`${PREFIX}:${suffix}`);
  }

  function layoutStorageKey(machineKey) {
    return `anki-slot-machine-layout-v2:${INSTANCE_KEY}:${machineKey}`;
  }

  function readControlPanelCollapsed() {
    try {
      return window.localStorage.getItem(CONTROL_PANEL_STORAGE_KEY) === "collapsed";
    } catch (_error) {
      return false;
    }
  }

  function writeControlPanelCollapsed(collapsed) {
    try {
      window.localStorage.setItem(
        CONTROL_PANEL_STORAGE_KEY,
        collapsed ? "collapsed" : "expanded",
      );
    } catch (_error) {
      // Ignore storage failures.
    }
  }

  function toSymbol(symbol) {
    const normalized = String(symbol || "").toLowerCase();
    return SYMBOLS.includes(normalized) ? normalized : null;
  }

  function machineIndex(machineKey) {
    return Object.keys(machineViews).indexOf(machineKey);
  }

  function createRootMarkup(machineLabel) {
    const label = String(machineLabel || "Slot Machine");
    return `
      <div class="anki-slot-machine-machine" data-slot-machine>
        <div class="anki-slot-machine-machine-inner" data-slot-machine-inner>
          <div class="anki-slot-machine-titlebar" data-slot-drag-handle>
            <div class="anki-slot-machine-window-controls">
              <button class="anki-slot-machine-window-button is-close" data-slot-close type="button" aria-label="Close ${label}"></button>
            </div>
            <div class="anki-slot-machine-title" data-slot-title>${label}</div>
            <div class="anki-slot-machine-titlebar-actions">
              <button class="anki-slot-machine-toolbar-button" data-slot-stats type="button" aria-label="Open slot stats">Stats</button>
              <div class="anki-slot-machine-balance" data-slot-balance>$0</div>
            </div>
          </div>
          <div class="anki-slot-machine-lights">
            <div class="anki-slot-machine-light"></div>
            <div class="anki-slot-machine-light"></div>
            <div class="anki-slot-machine-light"></div>
            <div class="anki-slot-machine-light"></div>
            <div class="anki-slot-machine-light"></div>
            <div class="anki-slot-machine-light"></div>
            <div class="anki-slot-machine-light"></div>
          </div>
          <div class="anki-slot-machine-window">
            <div class="anki-slot-machine-reels">
              <div class="anki-slot-machine-reel" data-slot-reel>
                <div class="anki-slot-machine-symbol is-blank" data-slot-symbol></div>
              </div>
              <div class="anki-slot-machine-reel" data-slot-reel>
                <div class="anki-slot-machine-symbol is-blank" data-slot-symbol></div>
              </div>
              <div class="anki-slot-machine-reel" data-slot-reel>
                <div class="anki-slot-machine-symbol is-blank" data-slot-symbol></div>
              </div>
            </div>
          </div>
          <div class="anki-slot-machine-breakdown" data-slot-breakdown>
            <div class="anki-slot-machine-breakdown-line" data-slot-base>+$1</div>
            <div class="anki-slot-machine-breakdown-line" data-slot-bonus>x 0</div>
            <div class="anki-slot-machine-breakdown-line is-total is-neutral" data-slot-total>= $0</div>
          </div>
          <div class="anki-slot-machine-amount" data-slot-amount></div>
          <div class="anki-slot-machine-particles" data-slot-particles></div>
        </div>
        <button class="anki-slot-machine-resize" data-slot-resize-handle type="button" aria-label="Resize ${label}"></button>
      </div>
    `;
  }

  function ensureView(machine) {
    const key = String(machine && machine.key ? machine.key : "main");
    const label = String(machine && machine.label ? machine.label : "Slot Machine");
    let view = machineViews[key];
    if (view && view.root && document.body.contains(view.root)) {
      updateMachineTitle(view, label);
      return view;
    }

    const root = document.createElement("div");
    root.className = "anki-slot-machine-root";
    root.dataset.slotInstance = INSTANCE_KEY;
    root.dataset.slotMachineKey = key;
    root.innerHTML = createRootMarkup(label);
    document.body.appendChild(root);

    view = {
      key,
      label,
      root,
      currentLayout: null,
      lastAnimatedEventId: null,
      amountTimeout: null,
      revealTimeouts: [],
      hasHydratedLayout: false,
    };
    machineViews[key] = view;

    bindWindowControls(view);
    bindGlobalWindowEvents();
    return view;
  }

  function ensureControlPanel() {
    if (controlPanel && document.body.contains(controlPanel)) {
      return controlPanel;
    }

    controlPanel = document.createElement("div");
    controlPanel.className = "anki-slot-machine-control-panel";
    controlPanel.innerHTML = `
      <div class="anki-slot-machine-control-panel-inner">
        <button class="anki-slot-machine-control-button is-collapse" data-slot-panel-collapse type="button">Hide</button>
        <button class="anki-slot-machine-control-button is-add" data-slot-panel-add type="button">Add Slot</button>
        <button class="anki-slot-machine-control-button is-close-all" data-slot-panel-close-all type="button">Close All</button>
        <button class="anki-slot-machine-control-button is-confirm" data-slot-panel-confirm type="button" hidden>Confirm</button>
        <button class="anki-slot-machine-control-button is-cancel" data-slot-panel-cancel type="button" hidden>Cancel</button>
      </div>
      <button class="anki-slot-machine-control-pill" data-slot-panel-expand type="button" hidden>Slots</button>
    `;
    document.body.appendChild(controlPanel);

    controlPanelCollapsed = readControlPanelCollapsed();
    const collapseButton = controlPanel.querySelector("[data-slot-panel-collapse]");
    const addButton = controlPanel.querySelector("[data-slot-panel-add]");
    const closeAllButton = controlPanel.querySelector("[data-slot-panel-close-all]");
    const confirmButton = controlPanel.querySelector("[data-slot-panel-confirm]");
    const cancelButton = controlPanel.querySelector("[data-slot-panel-cancel]");
    const expandButton = controlPanel.querySelector("[data-slot-panel-expand]");

    collapseButton.addEventListener("click", () => {
      closeAllConfirmOpen = false;
      controlPanelCollapsed = true;
      writeControlPanelCollapsed(true);
      updateControlPanelState(lastSyncedMachineCount);
    });

    addButton.addEventListener("click", () => {
      closeAllConfirmOpen = false;
      updateControlPanelState(lastSyncedMachineCount);
      send("addSlot");
    });
    closeAllButton.addEventListener("click", () => {
      closeAllConfirmOpen = true;
      updateControlPanelState(lastSyncedMachineCount);
    });
    confirmButton.addEventListener("click", () => {
      closeAllConfirmOpen = false;
      updateControlPanelState(lastSyncedMachineCount);
      send("closeAllSlots");
    });
    cancelButton.addEventListener("click", () => {
      closeAllConfirmOpen = false;
      updateControlPanelState(lastSyncedMachineCount);
    });
    expandButton.addEventListener("click", () => {
      controlPanelCollapsed = false;
      writeControlPanelCollapsed(false);
      updateControlPanelState(lastSyncedMachineCount);
    });

    return controlPanel;
  }

  function updateControlPanelState(machineCount) {
    const panel = ensureControlPanel();
    const panelInner = panel.querySelector(".anki-slot-machine-control-panel-inner");
    const collapseButton = panel.querySelector("[data-slot-panel-collapse]");
    const closeAllButton = panel.querySelector("[data-slot-panel-close-all]");
    const confirmButton = panel.querySelector("[data-slot-panel-confirm]");
    const cancelButton = panel.querySelector("[data-slot-panel-cancel]");
    const expandButton = panel.querySelector("[data-slot-panel-expand]");
    const canCloseAll = Number(machineCount || 0) > 0;

    if (controlPanelCollapsed) {
      closeAllConfirmOpen = false;
    }
    closeAllButton.disabled = !canCloseAll;
    if (!canCloseAll) {
      closeAllConfirmOpen = false;
    }
    panel.classList.toggle("is-collapsed", controlPanelCollapsed);
    if (panelInner) {
      panelInner.hidden = controlPanelCollapsed;
    }
    if (expandButton) {
      expandButton.hidden = !controlPanelCollapsed;
    }
    if (collapseButton) {
      collapseButton.hidden = controlPanelCollapsed;
    }
    confirmButton.hidden = !closeAllConfirmOpen;
    cancelButton.hidden = !closeAllConfirmOpen;
    closeAllButton.hidden = closeAllConfirmOpen;
    closeAllButton.title = canCloseAll ? "Close every slot window" : "No slots are open";
  }

  function updateMachineTitle(view, label) {
    view.label = String(label || "Slot Machine");
    const titleNode = view.root.querySelector("[data-slot-title]");
    if (titleNode) {
      titleNode.textContent = view.label;
    }
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function readStoredLayout(machineKey) {
    try {
      const raw = window.localStorage.getItem(layoutStorageKey(machineKey));
      if (!raw) {
        return null;
      }
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch (_error) {
      return null;
    }
  }

  function saveLayout(machineKey, layout) {
    try {
      window.localStorage.setItem(layoutStorageKey(machineKey), JSON.stringify(layout));
    } catch (_error) {
      // Ignore storage failures and keep the current in-memory layout.
    }
  }

  function persistLayout(machineKey, layout) {
    saveLayout(machineKey, layout);
    send(
      "saveLayout",
      JSON.stringify({
        machine_key: machineKey,
        layout,
      }),
    );
  }

  function maxWidthForViewport() {
    const maxByWidth = window.innerWidth - VIEWPORT_MARGIN * 2;
    const maxByHeight = (window.innerHeight - VIEWPORT_MARGIN * 2) / WINDOW_RATIO;
    return Math.max(1, Math.min(MAX_WIDTH, maxByWidth, maxByHeight));
  }

  function fitWidthToViewport(width) {
    const maxWidth = maxWidthForViewport();
    return clamp(width, Math.min(MIN_WIDTH, maxWidth), maxWidth);
  }

  function defaultLayout(index) {
    const width = fitWidthToViewport(DEFAULT_WIDTH);
    const height = Math.round(width * WINDOW_RATIO);
    const offset = Math.max(0, index) * 28;
    return {
      left: Math.max(VIEWPORT_MARGIN, window.innerWidth - width - 44 - offset),
      top: Math.max(VIEWPORT_MARGIN, Math.round((window.innerHeight - height) / 2) + offset),
      width,
      height,
      mode: "open",
    };
  }

  function normalizedLayout(layout, index) {
    const fallback = defaultLayout(index);
    const widthCandidate =
      Number(layout && layout.width) ||
      (Number(layout && layout.height) ? Number(layout.height) / WINDOW_RATIO : fallback.width);
    const width = fitWidthToViewport(widthCandidate);
    const height = Math.round(width * WINDOW_RATIO);
    const maxLeft = Math.max(VIEWPORT_MARGIN, window.innerWidth - width - VIEWPORT_MARGIN);
    const maxTop = Math.max(VIEWPORT_MARGIN, window.innerHeight - height - VIEWPORT_MARGIN);
    return {
      left: clamp(Number(layout && layout.left) || fallback.left, VIEWPORT_MARGIN, maxLeft),
      top: clamp(Number(layout && layout.top) || fallback.top, VIEWPORT_MARGIN, maxTop),
      width,
      height,
    };
  }

  function layoutVariables(layout) {
    return {
      scale: layout.width / DEFAULT_WIDTH,
      symbolSize: 64,
      reelHeight: 182,
      windowWidth: 248,
      breakdownWidth: 192,
      amountTop: 76,
      particlesTop: 94,
    };
  }

  function applyLayout(view, layout, options) {
    const index = machineIndex(view.key);
    view.currentLayout = normalizedLayout(layout || view.currentLayout || defaultLayout(index), index);
    const machine = view.root.querySelector("[data-slot-machine]");
    const vars = layoutVariables(view.currentLayout);
    view.root.style.left = `${view.currentLayout.left}px`;
    view.root.style.top = `${view.currentLayout.top}px`;
    view.root.style.right = "auto";
    view.root.style.bottom = "auto";
    view.root.style.width = `${view.currentLayout.width}px`;
    view.root.style.height = `${view.currentLayout.height}px`;

    view.root.style.setProperty("--slot-window-scale", `${vars.scale}`);
    view.root.style.setProperty("--slot-scale", "1");
    view.root.style.setProperty("--slot-machine-symbol-size", `${vars.symbolSize}px`);
    view.root.style.setProperty("--slot-machine-reel-height", `${vars.reelHeight}px`);
    view.root.style.setProperty("--slot-machine-window-width", `${vars.windowWidth}px`);
    view.root.style.setProperty("--slot-machine-breakdown-width", `${vars.breakdownWidth}px`);
    view.root.style.setProperty("--slot-machine-amount-top", `${vars.amountTop}px`);
    view.root.style.setProperty("--slot-machine-particles-top", `${vars.particlesTop}px`);
    machine.hidden = false;

    if (!options || options.persist !== false) {
      persistLayout(view.key, view.currentLayout);
    }
  }

  function updateLayout(view, patch, options) {
    applyLayout(view, { ...(view.currentLayout || defaultLayout(machineIndex(view.key))), ...patch }, options);
  }

  function bindGlobalWindowEvents() {
    if (windowEventsBound) {
      return;
    }
    windowEventsBound = true;

    window.addEventListener("pointermove", (event) => {
      if (!interaction) {
        return;
      }
      event.preventDefault();
      const view = machineViews[interaction.machineKey];
      if (!view) {
        return;
      }
      const dx = event.clientX - interaction.startX;
      const dy = event.clientY - interaction.startY;
      if (interaction.mode === "move") {
        applyLayout(
          view,
          {
            ...interaction.layout,
            left: interaction.layout.left + dx,
            top: interaction.layout.top + dy,
          },
          { persist: false },
        );
        return;
      }

      const widthDelta = Math.max(dx, dy / WINDOW_RATIO);
      applyLayout(
        view,
        {
          ...interaction.layout,
          width: interaction.layout.width + widthDelta,
        },
        { persist: false },
      );
    });

    function endInteraction() {
      if (interaction) {
        const view = machineViews[interaction.machineKey];
        if (view && view.currentLayout) {
          persistLayout(view.key, view.currentLayout);
        }
      }
      interaction = null;
      document.body.classList.remove("anki-slot-machine-is-dragging");
      document.body.classList.remove("anki-slot-machine-is-resizing");
    }

    window.addEventListener("pointerup", endInteraction);
    window.addEventListener("pointercancel", endInteraction);
    window.addEventListener("resize", () => {
      Object.keys(machineViews).forEach((machineKey) => {
        const view = machineViews[machineKey];
        if (view) {
          applyLayout(view, view.currentLayout, { persist: false });
        }
      });
    });
  }

  function bindWindowControls(view) {
    if (view.root.dataset.controlsBound === "true") {
      return;
    }
    view.root.dataset.controlsBound = "true";

    const dragHandle = view.root.querySelector("[data-slot-drag-handle]");
    const resizeHandle = view.root.querySelector("[data-slot-resize-handle]");
    const closeButton = view.root.querySelector("[data-slot-close]");
    const statsButton = view.root.querySelector("[data-slot-stats]");

    function beginInteraction(mode, event) {
      interaction = {
        machineKey: view.key,
        mode,
        startX: event.clientX,
        startY: event.clientY,
        layout: { ...(view.currentLayout || defaultLayout(machineIndex(view.key))) },
      };
      document.body.classList.add(
        mode === "move" ? "anki-slot-machine-is-dragging" : "anki-slot-machine-is-resizing",
      );
    }

    dragHandle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) {
        return;
      }
      event.preventDefault();
      beginInteraction("move", event);
    });

    resizeHandle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) {
        return;
      }
      event.preventDefault();
      beginInteraction("resize", event);
    });

    closeButton.addEventListener("click", () => {
      send("removeSlot", view.key);
    });
    closeButton.addEventListener("pointerdown", (event) => {
      event.stopPropagation();
    });

    statsButton.addEventListener("click", () => {
      send("showStats");
    });
    statsButton.addEventListener("pointerdown", (event) => {
      event.stopPropagation();
    });
  }

  function renderSymbolNode(node, symbol) {
    node.className = "anki-slot-machine-symbol";
    if (!symbol) {
      node.classList.add("is-blank");
      delete node.dataset.symbol;
      node.innerHTML = "";
      return;
    }
    node.dataset.symbol = symbol;
    node.innerHTML = `
      <span class="anki-slot-machine-symbol-sprite" data-slot-sprite></span>
    `;
  }

  function symbolMarkup(symbol) {
    return `
      <span class="anki-slot-machine-symbol anki-slot-machine-symbol--inline" data-symbol="${symbol}">
        <span class="anki-slot-machine-symbol-sprite"></span>
      </span>
    `;
  }

  function setReelSymbol(reel, symbol) {
    const node = reel.querySelector("[data-slot-symbol]");
    renderSymbolNode(node, symbol);
  }

  function clearRevealTimeouts(view) {
    view.revealTimeouts.forEach((timeoutId) => window.clearTimeout(timeoutId));
    view.revealTimeouts = [];
  }

  function clearReels(view) {
    view.root.querySelectorAll("[data-slot-reel]").forEach((reel) => {
      reel.classList.remove("is-bright");
      reel.classList.remove("is-pair");
      setReelSymbol(reel, null);
    });
  }

  function showAmount(view, text, tone) {
    const amount = view.root.querySelector("[data-slot-amount]");
    const numericValue = Math.abs(Number.parseFloat(String(text).replace(/[^0-9.\-]/g, "")) || 0);
    const fontScale = Math.max(1, Math.min(3.2, 1 + Math.pow(numericValue / 8, 0.6) * 0.95));
    amount.textContent = text;
    amount.style.setProperty("--slot-amount-font-scale", String(fontScale));
    amount.className = `anki-slot-machine-amount is-visible is-${tone}`;
    if (view.amountTimeout) {
      window.clearTimeout(view.amountTimeout);
    }
    view.amountTimeout = window.setTimeout(() => {
      amount.style.removeProperty("--slot-amount-font-scale");
      amount.className = "anki-slot-machine-amount";
      amount.textContent = "";
    }, 900);
  }

  function burstParticles(view, tone) {
    const container = view.root.querySelector("[data-slot-particles]");
    container.innerHTML = "";
    for (let index = 0; index < 8; index += 1) {
      const particle = document.createElement("div");
      particle.className = `anki-slot-machine-particle is-${tone}`;
      particle.style.left = `${30 + Math.random() * 40}%`;
      particle.style.setProperty("--dx", `${-12 + Math.random() * 24}px`);
      particle.style.setProperty("--dy", `${-18 - Math.random() * 18}px`);
      particle.style.animationDelay = `${index * 18}ms`;
      container.appendChild(particle);
      window.setTimeout(() => {
        if (particle.parentNode && typeof particle.parentNode.removeChild === "function") {
          particle.parentNode.removeChild(particle);
        }
      }, 520);
    }
  }

  function flashLoss(view) {
    const machine = view.root.querySelector("[data-slot-machine]");
    machine.classList.remove("is-loss");
    void machine.offsetWidth;
    machine.classList.add("is-loss");
    window.setTimeout(() => machine.classList.remove("is-loss"), 220);
  }

  function revealSpinResult(view, result, options) {
    const reels = view.root.querySelectorAll("[data-slot-reel]");
    const symbols = (result.reels || []).map(toSymbol);
    const highlight = Boolean(options && options.highlight);
    const pairHighlight = options && options.pairHighlight === false ? false : true;
    const pairSymbol = !result.line_hit ? toSymbol(result.matched_symbol) : null;
    clearReels(view);
    reels.forEach((reel, index) => {
      const timeoutId = window.setTimeout(() => {
        if (highlight) {
          reel.classList.add("is-bright");
        } else if (pairHighlight && pairSymbol && symbols[index] === pairSymbol) {
          reel.classList.add("is-pair");
        }
        setReelSymbol(reel, symbols[index] || null);
      }, index * 140);
      view.revealTimeouts.push(timeoutId);
    });
  }

  function renderStaticResult(view, result) {
    const reels = view.root.querySelectorAll("[data-slot-reel]");
    clearRevealTimeouts(view);
    if (!result || result.answer_key === "hard") {
      clearReels(view);
      return;
    }
    const symbols = result.reels ? result.reels.map(toSymbol) : [];
    const pairSymbol =
      result.answer_key === "again" ? null : !result.line_hit ? toSymbol(result.matched_symbol) : null;
    reels.forEach((reel, index) => {
      reel.classList.remove("is-bright");
      reel.classList.remove("is-pair");
      if (result.answer_key !== "again" && result.line_hit) {
        reel.classList.add("is-bright");
      } else if (pairSymbol && symbols[index] === pairSymbol) {
        reel.classList.add("is-pair");
      }
      setReelSymbol(reel, symbols[index] || null);
    });
  }

  function renderBreakdown(view, result) {
    const baseNode = view.root.querySelector("[data-slot-base]");
    const bonusNode = view.root.querySelector("[data-slot-bonus]");
    const totalNode = view.root.querySelector("[data-slot-total]");

    baseNode.className = "anki-slot-machine-breakdown-line";
    bonusNode.className = "anki-slot-machine-breakdown-line";
    totalNode.className = "anki-slot-machine-breakdown-line is-total is-positive";

    if (!result) {
      baseNode.textContent = `+$${defaultMoney}`;
      bonusNode.textContent = `x ${defaultMultiplier}`;
      totalNode.className = "anki-slot-machine-breakdown-line is-total is-neutral";
      totalNode.textContent = "= $0";
      return;
    }

    if (result.answer_key === "again") {
      baseNode.textContent = `-$${result.base_reward || defaultMoney}`;
      if (result.did_spin && result.matched_symbol) {
        const symbolName = String(result.matched_symbol).toLowerCase();
        const faceCountLabel = result.line_hit ? "3 faces" : "2 faces";
        bonusNode.innerHTML = `
          <span class="anki-slot-machine-multiplier">
            ${symbolMarkup(symbolName)}
            <span class="anki-slot-machine-multiplier-indicator">${faceCountLabel}</span>
            <span class="anki-slot-machine-multiplier-text">x ${result.slot_multiplier || 0}</span>
          </span>
        `;
      } else {
        bonusNode.textContent = `x ${result.slot_multiplier || 0}`;
      }
      totalNode.className =
        Number.parseFloat(String(result.payout || 0)) === 0
          ? "anki-slot-machine-breakdown-line is-total is-neutral"
          : "anki-slot-machine-breakdown-line is-total is-negative";
      totalNode.textContent = `= -$${result.payout || 0}`;
      return;
    }

    if (result.answer_key === "hard") {
      baseNode.textContent = `+$${result.base_reward || 0}`;
      bonusNode.textContent = "no spin";
      totalNode.className = "anki-slot-machine-breakdown-line is-total is-neutral";
      totalNode.textContent = `= $${result.payout || 0}`;
      return;
    }

    baseNode.textContent = `+$${result.base_reward || 1}`;
    if (result.did_spin && result.matched_symbol) {
      const symbolName = String(result.matched_symbol).toLowerCase();
      const faceCountLabel = result.line_hit ? "3 faces" : "2 faces";
      bonusNode.innerHTML = `
        <span class="anki-slot-machine-multiplier">
          ${symbolMarkup(symbolName)}
          <span class="anki-slot-machine-multiplier-indicator">${faceCountLabel}</span>
          <span class="anki-slot-machine-multiplier-text">x ${result.slot_multiplier || 1}</span>
        </span>
      `;
    } else {
      bonusNode.textContent = `x ${result.slot_multiplier || 1}`;
    }
    totalNode.className =
      Number.parseFloat(String(result.payout || 0)) === 0
        ? "anki-slot-machine-breakdown-line is-total is-neutral"
        : "anki-slot-machine-breakdown-line is-total is-positive";
    totalNode.textContent = `= $${result.payout || 1}`;
  }

  function maybeAnimate(view, result) {
    if (!result || !result.event_id) {
      return;
    }
    if (result.event_id === view.lastAnimatedEventId) {
      return;
    }
    view.lastAnimatedEventId = result.event_id;
    clearRevealTimeouts(view);

    if (result.did_spin && result.animation_enabled) {
      if (result.answer_key === "again") {
        revealSpinResult(view, result, { highlight: false, pairHighlight: false });
        flashLoss(view);
        burstParticles(view, "loss");
        showAmount(
          view,
          `-$${result.payout || 0}`,
          Number.parseFloat(String(result.payout || 0)) === 0 ? "neutral" : "loss",
        );
      } else if (result.line_hit) {
        revealSpinResult(view, result, { highlight: true });
        burstParticles(view, "win");
        showAmount(view, `+$${result.payout}`, "win");
      } else {
        revealSpinResult(view, result, { highlight: false });
        showAmount(
          view,
          `+$${result.payout}`,
          Number.parseFloat(String(result.payout || 0)) > 0 ? "win" : "neutral",
        );
      }
      return;
    }

    renderStaticResult(view, result);
    if (result.answer_key === "again") {
      flashLoss(view);
      burstParticles(view, "loss");
      showAmount(
        view,
        `-$${result.bet}`,
        Number.parseFloat(String(result.bet || 0)) === 0 ? "neutral" : "loss",
      );
      return;
    }

    if (result.answer_key === "hard") {
      showAmount(view, `$${result.payout}`, "neutral");
    }
  }

  function machineResultFor(roundResult, machineKey) {
    if (!roundResult) {
      return null;
    }
    const rawResults = Array.isArray(roundResult.machine_results) ? roundResult.machine_results : null;
    if (!rawResults || rawResults.length === 0) {
      return roundResult;
    }
    for (let index = 0; index < rawResults.length; index += 1) {
      const result = rawResults[index];
      if (result && String(result.machine_key || "") === String(machineKey)) {
        return result;
      }
    }
    return rawResults[0] || null;
  }

  function syncState(nextState) {
    const state = nextState || {};
    ensureControlPanel();
    let machines = [];
    if (Array.isArray(state.machines)) {
      machines = state.machines;
    } else {
      machines = [{ key: "main", label: "Slot Machine" }];
    }
    lastSyncedMachineCount = machines.length;
    const activeMachineKeys = new Set(machines.map((machine) => String(machine.key || "main")));
    const persistedLayouts =
      state.window_layouts && typeof state.window_layouts === "object" ? state.window_layouts : {};

    Object.keys(machineViews).forEach((machineKey) => {
      if (activeMachineKeys.has(machineKey)) {
        return;
      }
      const view = machineViews[machineKey];
      if (view && view.root && view.root.parentNode && typeof view.root.parentNode.removeChild === "function") {
        view.root.parentNode.removeChild(view.root);
      }
      delete machineViews[machineKey];
    });

    machines.forEach((machine, index) => {
      const view = ensureView(machine);
      updateMachineTitle(view, machine.label);
      if (!view.hasHydratedLayout) {
        const savedLayout =
          persistedLayouts[machine.key] ||
          (machine.key === "main" ? state.window_layout : null) ||
          readStoredLayout(machine.key) ||
          defaultLayout(index);
        applyLayout(view, savedLayout, { persist: false });
        view.hasHydratedLayout = true;
      } else if (!hasHydratedLayouts && persistedLayouts[machine.key]) {
        applyLayout(view, persistedLayouts[machine.key], { persist: false });
      }

      view.root.querySelector("[data-slot-balance]").textContent = `$${state.balance || 0}`;
      const machineResult = machineResultFor(state.last_result, machine.key);
      renderBreakdown(view, machineResult);
      if (
        machineResult &&
        machineResult.event_id &&
        machineResult.event_id !== view.lastAnimatedEventId
      ) {
        maybeAnimate(view, machineResult);
      } else {
        renderStaticResult(view, machineResult);
      }
    });

    updateControlPanelState(machines.length);
    hasHydratedLayouts = true;
  }

  window.AnkiSlotMachineInstances[INSTANCE_KEY] = {
    syncState,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => send("refresh"));
  } else {
    send("refresh");
  }
})();

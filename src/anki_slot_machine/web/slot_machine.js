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
  const SYMBOL_SET = new Set(SYMBOLS);
  const DEFAULT_WIDTH = 316;
  const DEFAULT_HEIGHT = 480;
  const WINDOW_RATIO = DEFAULT_HEIGHT / DEFAULT_WIDTH;
  const MIN_WIDTH = 100;
  const MAX_WIDTH = 420;
  const VIEWPORT_MARGIN = 12;
  const REEL_GAP = 18;
  const REEL_STEP = 64 + REEL_GAP;
  const defaultMoney = "1.00";
  const defaultMultiplier = "0.00";
  const CONTROL_PANEL_STORAGE_KEY = `anki-slot-machine-control-panel-v1:${INSTANCE_KEY}`;

  const machineViews = Object.create(null);
  let machineKeys = [];
  let controlPanel = null;
  let controlPanelRefs = null;
  let closeAllConfirmOpen = false;
  let lastSyncedMachineCount = 0;
  let controlPanelCollapsed = true;
  let interaction = null;
  let hasHydratedLayouts = false;
  let windowEventsBound = false;

  const particleCleanupTimers = Object.create(null);
  const trackRenderCache = Object.create(null);

  const requestFrame =
    typeof window.requestAnimationFrame === "function"
      ? window.requestAnimationFrame.bind(window)
      : (callback) => window.setTimeout(() => callback(Date.now()), 16);

  const cancelFrame =
    typeof window.cancelAnimationFrame === "function"
      ? window.cancelAnimationFrame.bind(window)
      : (handle) => window.clearTimeout(handle);

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
      const stored = window.localStorage.getItem(CONTROL_PANEL_STORAGE_KEY);
      if (stored == null) {
        return true;
      }
      return stored === "collapsed";
    } catch (_error) {
      return true;
    }
  }

  function writeControlPanelCollapsed(collapsed) {
    try {
      window.localStorage.setItem(
        CONTROL_PANEL_STORAGE_KEY,
        collapsed ? "collapsed" : "expanded",
      );
    } catch (_error) {}
  }

  function toSymbol(symbol) {
    const normalized = String(symbol || "").toLowerCase();
    return SYMBOL_SET.has(normalized) ? normalized : null;
  }

  function machineIndex(machineKey) {
    return machineKeys.indexOf(machineKey);
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
                <div class="anki-slot-machine-reel-track" data-slot-track></div>
              </div>
              <div class="anki-slot-machine-reel" data-slot-reel>
                <div class="anki-slot-machine-reel-track" data-slot-track></div>
              </div>
              <div class="anki-slot-machine-reel" data-slot-reel>
                <div class="anki-slot-machine-reel-track" data-slot-track></div>
              </div>
            </div>
          </div>
          <div class="anki-slot-machine-breakdown" data-slot-breakdown>
            <div class="anki-slot-machine-breakdown-line" data-slot-base>+$1</div>
            <div class="anki-slot-machine-breakdown-line" data-slot-bonus>x 0</div>
            <div class="anki-slot-machine-breakdown-line is-total is-neutral" data-slot-total>= $0</div>
          </div>
          <div class="anki-slot-machine-status" data-slot-status></div>
          <div class="anki-slot-machine-amount" data-slot-amount></div>
          <div class="anki-slot-machine-particles" data-slot-particles></div>
        </div>
        <button class="anki-slot-machine-resize" data-slot-resize-handle type="button" aria-label="Resize ${label}"></button>
      </div>
    `;
  }

  function cacheViewElements(root) {
    const reels = Array.from(root.querySelectorAll("[data-slot-reel]"));
    return {
      machine: root.querySelector("[data-slot-machine]"),
      title: root.querySelector("[data-slot-title]"),
      balance: root.querySelector("[data-slot-balance]"),
      dragHandle: root.querySelector("[data-slot-drag-handle]"),
      resizeHandle: root.querySelector("[data-slot-resize-handle]"),
      closeButton: root.querySelector("[data-slot-close]"),
      statsButton: root.querySelector("[data-slot-stats]"),
      amount: root.querySelector("[data-slot-amount]"),
      status: root.querySelector("[data-slot-status]"),
      particles: root.querySelector("[data-slot-particles]"),
      baseNode: root.querySelector("[data-slot-base]"),
      bonusNode: root.querySelector("[data-slot-bonus]"),
      totalNode: root.querySelector("[data-slot-total]"),
      reels,
      tracks: reels.map((reel) => reel.querySelector("[data-slot-track]")),
    };
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
      els: cacheViewElements(root),
      currentLayout: null,
      lastAnimatedEventId: null,
      hasHydratedResult: false,
      amountTimeout: null,
      activeSpin: null,
      reelStrip: SYMBOLS.slice(),
      reelPositions: [0, 0, 0],
      syncedReelPositions: [0, 0, 0],
      spinDurationMs: 750,
      pendingBreakdownEventId: null,
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
        <button class="anki-slot-machine-control-button is-settings" data-slot-panel-settings type="button">Settings</button>
      </div>
      <button class="anki-slot-machine-control-pill" data-slot-panel-expand type="button" hidden>Slots</button>
    `;
    document.body.appendChild(controlPanel);

    controlPanelCollapsed = readControlPanelCollapsed();

    controlPanelRefs = {
      panel: controlPanel,
      panelInner: controlPanel.querySelector(".anki-slot-machine-control-panel-inner"),
      collapseButton: controlPanel.querySelector("[data-slot-panel-collapse]"),
      addButton: controlPanel.querySelector("[data-slot-panel-add]"),
      closeAllButton: controlPanel.querySelector("[data-slot-panel-close-all]"),
      confirmButton: controlPanel.querySelector("[data-slot-panel-confirm]"),
      cancelButton: controlPanel.querySelector("[data-slot-panel-cancel]"),
      settingsButton: controlPanel.querySelector("[data-slot-panel-settings]"),
      expandButton: controlPanel.querySelector("[data-slot-panel-expand]"),
    };

    controlPanelRefs.collapseButton.addEventListener("click", () => {
      closeAllConfirmOpen = false;
      controlPanelCollapsed = true;
      writeControlPanelCollapsed(true);
      updateControlPanelState(lastSyncedMachineCount);
    });

    controlPanelRefs.addButton.addEventListener("click", () => {
      closeAllConfirmOpen = false;
      updateControlPanelState(lastSyncedMachineCount);
      send("addSlot");
    });

    controlPanelRefs.settingsButton.addEventListener("click", () => {
      closeAllConfirmOpen = false;
      updateControlPanelState(lastSyncedMachineCount);
      send("showSettings");
    });

    controlPanelRefs.closeAllButton.addEventListener("click", () => {
      closeAllConfirmOpen = true;
      updateControlPanelState(lastSyncedMachineCount);
    });

    controlPanelRefs.confirmButton.addEventListener("click", () => {
      closeAllConfirmOpen = false;
      updateControlPanelState(lastSyncedMachineCount);
      send("closeAllSlots");
    });

    controlPanelRefs.cancelButton.addEventListener("click", () => {
      closeAllConfirmOpen = false;
      updateControlPanelState(lastSyncedMachineCount);
    });

    controlPanelRefs.expandButton.addEventListener("click", () => {
      controlPanelCollapsed = false;
      writeControlPanelCollapsed(false);
      updateControlPanelState(lastSyncedMachineCount);
    });

    return controlPanel;
  }

  function updateControlPanelState(machineCount) {
    ensureControlPanel();
    const refs = controlPanelRefs;
    const canCloseAll = Number(machineCount || 0) > 0;

    if (controlPanelCollapsed) {
      closeAllConfirmOpen = false;
    }
    if (!canCloseAll) {
      closeAllConfirmOpen = false;
    }

    refs.closeAllButton.disabled = !canCloseAll;
    refs.closeAllButton.hidden = closeAllConfirmOpen;
    refs.closeAllButton.title = canCloseAll ? "Close every slot window" : "No slots are open";

    refs.panel.classList.toggle("is-collapsed", controlPanelCollapsed);
    if (refs.panelInner) refs.panelInner.hidden = controlPanelCollapsed;
    if (refs.expandButton) refs.expandButton.hidden = !controlPanelCollapsed;
    if (refs.collapseButton) refs.collapseButton.hidden = controlPanelCollapsed;
    refs.confirmButton.hidden = !closeAllConfirmOpen;
    refs.cancelButton.hidden = !closeAllConfirmOpen;
  }

  function updateMachineTitle(view, label) {
    view.label = String(label || "Slot Machine");
    if (view.els.title) {
      view.els.title.textContent = view.label;
    }
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function readStoredLayout(machineKey) {
    try {
      const raw = window.localStorage.getItem(layoutStorageKey(machineKey));
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch (_error) {
      return null;
    }
  }

  function saveLayout(machineKey, layout) {
    try {
      window.localStorage.setItem(layoutStorageKey(machineKey), JSON.stringify(layout));
    } catch (_error) {}
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
      reelGap: REEL_GAP,
    };
  }

  function applyLayout(view, layout, options) {
    const index = machineIndex(view.key);
    const nextLayout = normalizedLayout(layout || view.currentLayout || defaultLayout(index), index);
    view.currentLayout = nextLayout;

    const vars = layoutVariables(nextLayout);
    const style = view.root.style;

    style.left = `${nextLayout.left}px`;
    style.top = `${nextLayout.top}px`;
    style.right = "auto";
    style.bottom = "auto";
    style.width = `${nextLayout.width}px`;
    style.height = `${nextLayout.height}px`;

    style.setProperty("--slot-window-scale", `${vars.scale}`);
    style.setProperty("--slot-scale", "1");
    style.setProperty("--slot-machine-symbol-size", `${vars.symbolSize}px`);
    style.setProperty("--slot-machine-reel-height", `${vars.reelHeight}px`);
    style.setProperty("--slot-machine-window-width", `${vars.windowWidth}px`);
    style.setProperty("--slot-machine-breakdown-width", `${vars.breakdownWidth}px`);
    style.setProperty("--slot-machine-amount-top", `${vars.amountTop}px`);
    style.setProperty("--slot-machine-particles-top", `${vars.particlesTop}px`);
    style.setProperty("--slot-machine-reel-gap", `${vars.reelGap}px`);

    view.els.machine.hidden = false;

    if (!options || options.persist !== false) {
      persistLayout(view.key, nextLayout);
    }
  }

  function updateLayout(view, patch, options) {
    applyLayout(
      view,
      { ...(view.currentLayout || defaultLayout(machineIndex(view.key))), ...patch },
      options,
    );
  }

  function bindGlobalWindowEvents() {
    if (windowEventsBound) {
      return;
    }
    windowEventsBound = true;

    window.addEventListener("pointermove", (event) => {
      if (!interaction) return;

      event.preventDefault();
      const view = machineViews[interaction.machineKey];
      if (!view) return;

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
      for (let i = 0; i < machineKeys.length; i += 1) {
        const view = machineViews[machineKeys[i]];
        if (view) {
          applyLayout(view, view.currentLayout, { persist: false });
        }
      }
    });
  }

  function bindWindowControls(view) {
    if (view.root.dataset.controlsBound === "true") {
      return;
    }
    view.root.dataset.controlsBound = "true";

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

    view.els.dragHandle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      beginInteraction("move", event);
    });

    view.els.resizeHandle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      beginInteraction("resize", event);
    });

    view.els.closeButton.addEventListener("click", () => {
      send("removeSlot", view.key);
    });
    view.els.closeButton.addEventListener("pointerdown", (event) => {
      event.stopPropagation();
    });

    view.els.statsButton.addEventListener("click", () => {
      send("showStats");
    });
    view.els.statsButton.addEventListener("pointerdown", (event) => {
      event.stopPropagation();
    });
  }

  function symbolMarkup(symbol) {
    return `
      <span class="anki-slot-machine-symbol anki-slot-machine-symbol--inline" data-symbol="${symbol}">
        <span class="anki-slot-machine-symbol-sprite"></span>
      </span>
    `;
  }

  function normalizeStrip(rawStrip) {
    if (!Array.isArray(rawStrip)) {
      return SYMBOLS.slice();
    }
    const strip = [];
    for (let i = 0; i < rawStrip.length; i += 1) {
      const symbol = toSymbol(rawStrip[i]);
      if (symbol) strip.push(symbol);
    }
    return strip.length ? strip : SYMBOLS.slice();
  }

  function defaultPositionsForStrip(strip) {
    const length = Math.max(1, strip.length);
    return [0, 1 % length, 2 % length];
  }

  function normalizePositions(rawPositions, stripLength, fallbackPositions) {
    const safeStripLength = Math.max(1, stripLength);
    const fallback = Array.isArray(fallbackPositions)
      ? fallbackPositions.slice(0, 3)
      : defaultPositionsForStrip(new Array(safeStripLength));

    const source =
      Array.isArray(rawPositions) && rawPositions.length === 3 ? rawPositions : fallback;

    return source.map((value, index) => {
      const fallbackValue = fallback[index] || 0;
      const numeric = Number.parseInt(String(value), 10);
      if (!Number.isFinite(numeric)) {
        return fallbackValue % safeStripLength;
      }
      return ((numeric % safeStripLength) + safeStripLength) % safeStripLength;
    });
  }

  function normalizeStepCounts(rawStepCounts) {
    const source = Array.isArray(rawStepCounts) && rawStepCounts.length === 3 ? rawStepCounts : [0, 0, 0];
    return source.map((value) => {
      const numeric = Number.parseInt(String(value), 10);
      return Number.isFinite(numeric) ? Math.max(0, numeric) : 0;
    });
  }

  function clampSpinDuration(durationMs) {
    const numeric = Number.parseInt(String(durationMs), 10);
    if (!Number.isFinite(numeric)) {
      return 750;
    }
    return Math.min(750, Math.max(150, numeric));
  }

  function symbolAtPosition(strip, position) {
    if (!strip.length) return null;
    const length = strip.length;
    return strip[((position % length) + length) % length];
  }

  function setReelOffset(reel, offsetPx) {
    reel.style.setProperty("--slot-track-offset", `${Math.round(offsetPx)}px`);
  }

  function renderReelTrack(view, reelIndex, symbols, centeredIndex) {
    const cacheKey = `${symbols.join(",")}|${centeredIndex}`;
    const viewKey = view.key;

    if (!trackRenderCache[viewKey]) {
      trackRenderCache[viewKey] = [null, null, null];
    }

    if (trackRenderCache[viewKey][reelIndex] === cacheKey) {
      setReelOffset(view.els.reels[reelIndex], -(centeredIndex * REEL_STEP));
      return;
    }

    trackRenderCache[viewKey][reelIndex] = cacheKey;

    const track = view.els.tracks[reelIndex];
    while (track.firstChild) {
      track.removeChild(track.firstChild);
    }

    const frag = document.createDocumentFragment();
    for (let i = 0; i < symbols.length; i += 1) {
      const normalized = toSymbol(symbols[i]);
      const cell = document.createElement("div");
      cell.className = "anki-slot-machine-reel-cell";

      const symbolDiv = document.createElement("div");
      if (!normalized) {
        symbolDiv.className = "anki-slot-machine-symbol is-blank";
      } else {
        symbolDiv.className = "anki-slot-machine-symbol";
        symbolDiv.setAttribute("data-symbol", normalized);

        const sprite = document.createElement("span");
        sprite.className = "anki-slot-machine-symbol-sprite";
        sprite.setAttribute("data-slot-sprite", "");
        symbolDiv.appendChild(sprite);
      }

      cell.appendChild(symbolDiv);
      frag.appendChild(cell);
    }

    track.appendChild(frag);
    setReelOffset(view.els.reels[reelIndex], -(centeredIndex * REEL_STEP));
  }

  function renderReelAtPosition(view, reelIndex, position) {
    const strip = view.reelStrip.length ? view.reelStrip : SYMBOLS;
    const cells = [-1, 0, 1].map((offset) => symbolAtPosition(strip, position + offset));
    renderReelTrack(view, reelIndex, cells, 1);
  }

  function renderReelPositions(view, positions) {
    for (let i = 0; i < 3; i += 1) {
      renderReelAtPosition(view, i, positions[i] || 0);
    }
  }

  function stopSpinAnimation(view) {
    if (view.activeSpin && view.activeSpin.frameId != null) {
      cancelFrame(view.activeSpin.frameId);
    }
    view.activeSpin = null;
    view.pendingBreakdownEventId = null;
    for (let i = 0; i < view.els.reels.length; i += 1) {
      view.els.reels[i].classList.remove("is-spinning");
    }
  }

  function clearReels(view) {
    stopSpinAnimation(view);
    for (let i = 0; i < view.els.reels.length; i += 1) {
      const reel = view.els.reels[i];
      reel.classList.remove("is-bright");
      reel.classList.remove("is-pair");
    }
    renderReelPositions(view, view.reelPositions);
  }

  function easeOutCubic(progress) {
    return 1 - Math.pow(1 - progress, 3);
  }

  function stableHash(value) {
    const input = String(value || "");
    let hash = 0;
    for (let index = 0; index < input.length; index += 1) {
      hash = (hash * 31 + input.charCodeAt(index)) >>> 0;
    }
    return hash >>> 0;
  }

  function deterministicUnit() {
    let str = "";
    for (let i = 0; i < arguments.length; ++i) {
      if (i !== 0) {
        str += ":";
      }
      str += String(arguments[i]);
    }
    return (stableHash(str) % 1000) / 999;
  }

  function slotSpinProgress(progress, settleAmount) {
    const clamped = Math.min(Math.max(progress, 0), 1);
    const cruiseBoundary = 0.8;
    if (clamped <= cruiseBoundary) {
      const cruiseProgress = clamped / cruiseBoundary;
      return 0.88 * cruiseProgress;
    }
    const tailProgress = (clamped - cruiseBoundary) / (1 - cruiseBoundary);
    const tailBase = 0.88 + 0.12 * easeOutCubic(tailProgress);
    const overshoot = settleAmount * Math.sin(Math.PI * tailProgress) * (1 - tailProgress);
    return tailBase + overshoot;
  }

  function renderStaticResult(view, result, positions) {
    stopSpinAnimation(view);
    trackRenderCache[view.key] = [null, null, null];

    view.reelPositions = normalizePositions(
      positions,
      view.reelStrip.length,
      view.reelPositions,
    );

    const reels = view.els.reels;
    for (let i = 0; i < reels.length; i += 1) {
      reels[i].classList.remove("is-bright");
      reels[i].classList.remove("is-pair");
      reels[i].classList.remove("is-spinning");
    }

    renderReelPositions(view, view.reelPositions);

    if (!result) {
      return;
    }

    const symbols = (result.reels || []).map(toSymbol);
    const pairSymbol = !result.line_hit ? toSymbol(result.matched_symbol) : null;

    for (let i = 0; i < reels.length; i += 1) {
      if (result.line_hit) {
        reels[i].classList.add("is-bright");
      } else if (pairSymbol && symbols[i] === pairSymbol) {
        reels[i].classList.add("is-pair");
      }
    }
  }

  function revealSpinResult(view, result, positions, options) {
    const reels = view.els.reels;
    const highlight = Boolean(options && options.highlight);
    const pairHighlight = options && options.pairHighlight === false ? false : true;
    const onComplete = options && typeof options.onComplete === "function" ? options.onComplete : null;
    const symbols = (result.reels || []).map(toSymbol);
    const pairSymbol = !result.line_hit ? toSymbol(result.matched_symbol) : null;
    const stripLength = Math.max(1, view.reelStrip.length);
    const totalDuration = clampSpinDuration(view.spinDurationMs);
    const startPositions = normalizePositions(
      result.reel_start_positions,
      stripLength,
      view.reelPositions,
    );
    const endPositions = normalizePositions(
      result.reel_positions || positions,
      stripLength,
      positions,
    );
    const stepCounts = normalizeStepCounts(result.reel_step_counts);

    stopSpinAnimation(view);
    trackRenderCache[view.key] = [null, null, null];

    for (let i = 0; i < reels.length; i += 1) {
      reels[i].classList.remove("is-bright");
      reels[i].classList.remove("is-pair");
    }

    const spinState = { frameId: null };
    view.activeSpin = spinState;
    view.pendingBreakdownEventId = result.event_id || null;

    const finishFractions = [0.66, 0.84, 1];
    const delayFractions = [0, 0.04, 0.08];

    const reelStates = reels.map((reel, index) => {
      const timingSeed = `${result.event_id || "spin"}:${view.key}:${index}`;
      const startPosition = startPositions[index] || 0;
      const targetPosition = endPositions[index] || 0;
      const baseDelta = ((targetPosition - startPosition) % stripLength + stripLength) % stripLength;
      const fallbackSteps = baseDelta === 0 ? stripLength : baseDelta;
      const steps = Math.max(fallbackSteps, stepCounts[index] || 0);

      const sequence = [];
      for (let offset = -1; offset <= steps + 1; offset += 1) {
        sequence.push(symbolAtPosition(view.reelStrip, startPosition + offset));
      }

      renderReelTrack(view, index, sequence, 1);
      reel.classList.add("is-spinning");

      return {
        reel,
        steps,
        targetPosition,
        targetSymbol: symbols[index] || symbolAtPosition(view.reelStrip, targetPosition),
        delay: Math.round(
          totalDuration *
            (delayFractions[index] + 0.01 * deterministicUnit(timingSeed, "delay")),
        ),
        finishAt:
          index === 2
            ? totalDuration
            : Math.round(
                totalDuration *
                  Math.min(
                    0.97,
                    finishFractions[index] +
                      0.025 * (deterministicUnit(timingSeed, "finish") - 0.5),
                  ),
              ),
        settleAmount: 0.04 + 0.09 * deterministicUnit(timingSeed, "settle"),
        settled: false,
      };
    }).map((state) => ({
      ...state,
      duration: Math.max(220, state.finishAt - state.delay),
    }));

    const startTime =
      window.performance && typeof window.performance.now === "function"
        ? window.performance.now()
        : Date.now();

    const tick = (now) => {
      if (view.activeSpin !== spinState) {
        return;
      }

      let hasActiveReel = false;

      for (let i = 0; i < reelStates.length; i += 1) {
        const state = reelStates[i];
        const elapsed = now - startTime - state.delay;

        if (elapsed <= 0) {
          hasActiveReel = true;
          continue;
        }

        const progress = Math.min(1, elapsed / state.duration);
        const virtualIndex = 1 + state.steps * slotSpinProgress(progress, state.settleAmount);
        setReelOffset(state.reel, -(virtualIndex * REEL_STEP));

        if (progress < 1) {
          hasActiveReel = true;
          continue;
        }

        if (!state.settled) {
          state.settled = true;
          state.reel.classList.remove("is-spinning");
          if (highlight) {
            state.reel.classList.add("is-bright");
          } else if (pairHighlight && pairSymbol && state.targetSymbol === pairSymbol) {
            state.reel.classList.add("is-pair");
          }
        }
      }

      if (hasActiveReel) {
        spinState.frameId = requestFrame(tick);
        return;
      }

      view.reelPositions = endPositions.slice(0, 3);
      renderReelPositions(view, view.reelPositions);
      view.activeSpin = null;
      view.pendingBreakdownEventId = null;

      if (onComplete) {
        onComplete();
      }
    };

    spinState.frameId = requestFrame(tick);
  }

  function showAmount(view, text, tone) {
    const amount = view.els.amount;
    const numericValue = Math.abs(Number.parseFloat(String(text).replace(/[^0-9.\-]/g, "")) || 0);
    const fontScale = Math.max(1, Math.min(3.2, 1 + Math.pow(numericValue / 8, 0.6) * 0.95));

    amount.textContent = text;
    amount.style.setProperty("--slot-amount-font-scale", String(fontScale));
    amount.className = `anki-slot-machine-amount is-visible is-${tone}`;

    if (view.amountTimeout) {
      window.clearTimeout(view.amountTimeout);
      view.amountTimeout = null;
    }

    view.amountTimeout = window.setTimeout(() => {
      amount.style.removeProperty("--slot-amount-font-scale");
      amount.className = "anki-slot-machine-amount";
      amount.textContent = "";
      view.amountTimeout = null;
    }, 900);
  }

  function clearAmount(view) {
    if (view.amountTimeout) {
      window.clearTimeout(view.amountTimeout);
      view.amountTimeout = null;
    }
    view.els.amount.style.removeProperty("--slot-amount-font-scale");
    view.els.amount.className = "anki-slot-machine-amount";
    view.els.amount.textContent = "";
  }

  function clearStatus(view) {
    view.els.status.className = "anki-slot-machine-status";
    view.els.status.textContent = "";
  }

  function showStatus(view, text, tone) {
    view.els.status.className = `anki-slot-machine-status is-visible is-${tone}`;
    view.els.status.textContent = text;
  }

  function isNoSpinLikeResult(result) {
    if (!result) {
      return false;
    }
    if (result.no_spin) {
      return true;
    }
    if (result.bet != null && moneyNumber(result.bet) === 0) {
      return true;
    }
    if (!result.did_spin) {
      return true;
    }
    return result.base_reward != null && moneyNumber(result.base_reward) === 0;
  }

  function syncNoSpinStatus(view, result) {
    if (isNoSpinLikeResult(result)) {
      showStatus(view, "No spin", "neutral");
      return;
    }
    clearStatus(view);
  }

  function burstParticles(view, tone) {
    const container = view.els.particles;

    if (particleCleanupTimers[view.key]) {
      window.clearTimeout(particleCleanupTimers[view.key]);
      particleCleanupTimers[view.key] = null;
    }

    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }

    const frag = document.createDocumentFragment();
    for (let index = 0; index < 8; index += 1) {
      const particle = document.createElement("div");
      particle.className = `anki-slot-machine-particle is-${tone}`;
      particle.style.left = `${30 + Math.random() * 40}%`;
      particle.style.setProperty("--dx", `${-12 + Math.random() * 24}px`);
      particle.style.setProperty("--dy", `${-18 - Math.random() * 18}px`);
      particle.style.animationDelay = `${index * 18}ms`;
      frag.appendChild(particle);
    }
    container.appendChild(frag);

    particleCleanupTimers[view.key] = window.setTimeout(() => {
      while (container.firstChild) {
        container.removeChild(container.firstChild);
      }
      particleCleanupTimers[view.key] = null;
    }, 540);
  }

  function flashLoss(view) {
    const machine = view.els.machine;
    machine.classList.remove("is-loss");
    void machine.offsetWidth;
    machine.classList.add("is-loss");
    window.setTimeout(() => machine.classList.remove("is-loss"), 220);
  }

  function moneyNumber(value) {
    return Number.parseFloat(String(value == null ? 0 : value));
  }

  function signedMoney(value, options) {
    const numericValue = moneyNumber(value);
    const absoluteText = Math.abs(numericValue).toFixed(2);
    const showPositive = Boolean(options && options.showPositive);
    if (numericValue > 0) {
      return `${showPositive ? "+" : ""}$${absoluteText}`;
    }
    if (numericValue < 0) {
      return `-$${absoluteText}`;
    }
    return `${showPositive ? "+" : ""}$0.00`;
  }

  function renderBreakdown(view, result, options) {
    const baseNode = view.els.baseNode;
    const bonusNode = view.els.bonusNode;
    const totalNode = view.els.totalNode;
    const isPending = Boolean(options && options.pending);
    const payoutValue = result && result.payout != null ? result.payout : 0;
    const netChangeValue = result && result.net_change != null ? result.net_change : 0;
    const baseRewardValue = result && result.base_reward != null ? result.base_reward : 0;
    const slotMultiplierValue = result && result.slot_multiplier != null ? result.slot_multiplier : 0;
    const netChangeNumber = moneyNumber(netChangeValue);
    const isZeroPayout = moneyNumber(payoutValue) === 0;

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

    if (isPending) {
      baseNode.textContent = signedMoney(baseRewardValue, { showPositive: true });
      bonusNode.textContent = "";
      totalNode.className = "anki-slot-machine-breakdown-line is-total is-neutral";
      totalNode.textContent = "";
      return;
    }

    if (isNoSpinLikeResult(result)) {
      baseNode.className = "anki-slot-machine-breakdown-line is-neutral";
      bonusNode.className = "anki-slot-machine-breakdown-line is-neutral";
      baseNode.textContent =
        moneyNumber(baseRewardValue) === 0
          ? signedMoney(baseRewardValue)
          : signedMoney(baseRewardValue, { showPositive: true });
      bonusNode.textContent = "";
      totalNode.className = "anki-slot-machine-breakdown-line is-total is-neutral";
      totalNode.textContent = "";
      return;
    }

    baseNode.textContent = signedMoney(baseRewardValue, { showPositive: true });
    if (result.did_spin && result.matched_symbol) {
      const symbolName = String(result.matched_symbol).toLowerCase();
      const faceCountLabel = result.line_hit ? "3 faces" : "2 faces";
      bonusNode.innerHTML = `
        <span class="anki-slot-machine-multiplier">
          ${symbolMarkup(symbolName)}
          <span class="anki-slot-machine-multiplier-indicator">${faceCountLabel}</span>
          <span class="anki-slot-machine-multiplier-text">x ${slotMultiplierValue}</span>
        </span>
      `;
    } else {
      bonusNode.textContent = `x ${slotMultiplierValue}`;
    }
    totalNode.className =
      netChangeNumber > 0
        ? "anki-slot-machine-breakdown-line is-total is-positive"
        : netChangeNumber < 0
          ? "anki-slot-machine-breakdown-line is-total is-negative"
          : "anki-slot-machine-breakdown-line is-total is-neutral";
    totalNode.textContent = `= ${signedMoney(payoutValue, { showPositive: true })}`;
  }

  function maybeAnimate(view, result) {
    if (!result || !result.event_id) return;

    const payoutValue = result.payout != null ? result.payout : 0;
    const netChangeValue = result.net_change != null ? result.net_change : payoutValue;
    const netChangeNumber = moneyNumber(netChangeValue);
    const tone = netChangeNumber > 0 ? "win" : netChangeNumber < 0 ? "loss" : "neutral";
    if (result.event_id === view.lastAnimatedEventId) {
      return;
    }

    view.lastAnimatedEventId = result.event_id;
    clearAmount(view);
    clearStatus(view);

    if (!isNoSpinLikeResult(result) && result.did_spin && result.animation_enabled) {
      revealSpinResult(view, result, view.syncedReelPositions, {
        highlight: Boolean(result.line_hit),
        pairHighlight: Boolean(result.matched_symbol) && !result.line_hit,
        onComplete: () => {
          renderBreakdown(view, result);
          if (netChangeNumber < 0) {
            flashLoss(view);
            burstParticles(view, "loss");
          } else if (result.line_hit && netChangeNumber > 0) {
            burstParticles(view, "win");
          }
          showAmount(view, signedMoney(payoutValue, { showPositive: true }), tone);
        },
      });
      return;
    }

    renderStaticResult(view, result, view.syncedReelPositions);

    if (isNoSpinLikeResult(result)) {
      syncNoSpinStatus(view, result);
      return;
    }
    if (netChangeNumber < 0) {
      flashLoss(view);
      burstParticles(view, "loss");
    }
    showAmount(view, signedMoney(payoutValue, { showPositive: true }), tone);
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
    for (let index = 0; index < rawResults.length; index += 1) {
      const result = rawResults[index];
      if (result && !String(result.machine_key || "").trim()) {
        return result;
      }
    }
    return null;
  }

  function removeView(machineKey) {
    const view = machineViews[machineKey];
    if (!view) return;

    stopSpinAnimation(view);
    clearAmount(view);
    clearStatus(view);

    if (particleCleanupTimers[machineKey]) {
      window.clearTimeout(particleCleanupTimers[machineKey]);
      particleCleanupTimers[machineKey] = null;
    }

    if (view.els && view.els.particles) {
      while (view.els.particles.firstChild) {
        view.els.particles.removeChild(view.els.particles.firstChild);
      }
    }

    trackRenderCache[machineKey] = null;

    if (view.root && view.root.parentNode && typeof view.root.parentNode.removeChild === "function") {
      view.root.parentNode.removeChild(view.root);
    }

    delete machineViews[machineKey];
  }

  function syncState(nextState) {
    const state = nextState || {};
    const suppressAnimation = Boolean(state.suppress_animation);

    ensureControlPanel();

    const machines = Array.isArray(state.machines)
      ? state.machines
      : [{ key: "main", label: "Slot Machine" }];

    machineKeys = machines.map((machine) => String(machine.key || "main"));
    lastSyncedMachineCount = machines.length;

    const activeMachineKeys = new Set(machineKeys);
    const persistedLayouts =
      state.window_layouts && typeof state.window_layouts === "object" ? state.window_layouts : {};

    const existingKeys = Object.keys(machineViews);
    for (let i = 0; i < existingKeys.length; i += 1) {
      const machineKey = existingKeys[i];
      if (!activeMachineKeys.has(machineKey)) {
        removeView(machineKey);
      }
    }

    for (let index = 0; index < machines.length; index += 1) {
      const machine = machines[index];
      const key = String(machine.key || "main");
      const view = ensureView(machine);

      updateMachineTitle(view, machine.label);

      if (!view.hasHydratedLayout) {
        const savedLayout =
          persistedLayouts[key] ||
          (key === "main" ? state.window_layout : null) ||
          readStoredLayout(key) ||
          defaultLayout(index);

        applyLayout(view, savedLayout, { persist: false });
        view.hasHydratedLayout = true;
      } else if (!hasHydratedLayouts && persistedLayouts[key]) {
        applyLayout(view, persistedLayouts[key], { persist: false });
      }

      const balanceText = `$${state.balance || 0}`;
      if (view.els.balance.textContent !== balanceText) {
        view.els.balance.textContent = balanceText;
      }

      view.reelStrip = normalizeStrip(machine.reel_strip);
      view.syncedReelPositions = normalizePositions(
        machine.reel_positions,
        view.reelStrip.length,
        view.reelPositions,
      );
      view.spinDurationMs = clampSpinDuration(state.spin_animation_duration_ms);

      const machineResult = machineResultFor(state.last_result, key);

      if (!view.hasHydratedResult) {
        if (machineResult && machineResult.event_id) {
          view.lastAnimatedEventId = machineResult.event_id;
        }
        renderBreakdown(view, machineResult);
        clearAmount(view);
        syncNoSpinStatus(view, machineResult);

        renderStaticResult(view, machineResult, view.syncedReelPositions);
        view.hasHydratedResult = true;
        continue;
      }

      if (suppressAnimation) {
        if (machineResult && machineResult.event_id) {
          view.lastAnimatedEventId = machineResult.event_id;
        }

        renderBreakdown(view, machineResult);
        clearAmount(view);
        syncNoSpinStatus(view, machineResult);

        renderStaticResult(view, machineResult, view.syncedReelPositions);
        continue;
      }

      const shouldDelayBreakdown =
        Boolean(
          machineResult &&
            !isNoSpinLikeResult(machineResult) &&
            machineResult.did_spin &&
            machineResult.animation_enabled,
        ) &&
        (machineResult.event_id !== view.lastAnimatedEventId ||
          machineResult.event_id === view.pendingBreakdownEventId);

      const isSameEventAnimationInProgress = Boolean(
        machineResult &&
          view.activeSpin &&
          view.pendingBreakdownEventId &&
          machineResult.event_id === view.pendingBreakdownEventId,
      );

      renderBreakdown(view, machineResult, { pending: shouldDelayBreakdown });

      if (shouldDelayBreakdown) {
        clearStatus(view);
      } else {
        syncNoSpinStatus(view, machineResult);
      }

      if (
        machineResult &&
        machineResult.event_id &&
        machineResult.event_id !== view.lastAnimatedEventId
      ) {
        maybeAnimate(view, machineResult);
      } else if (!isSameEventAnimationInProgress) {
        renderStaticResult(view, machineResult, view.syncedReelPositions);
      }
    }

    updateControlPanelState(machines.length);
    hasHydratedLayouts = true;
  }

  window.AnkiSlotMachineInstances[INSTANCE_KEY] = { syncState };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => send("refresh"));
  } else {
    send("refresh");
  }
})();

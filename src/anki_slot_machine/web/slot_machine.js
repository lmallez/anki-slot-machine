(function () {
  if (window.AnkiSlotMachine) {
    return;
  }

  const PREFIX = "anki-slot-machine";
  const SYMBOLS = ["slot_1", "slot_2", "slot_3", "slot_4", "slot_5"];
  const LAYOUT_STORAGE_KEY = "anki-slot-machine-layout-v1";
  const DEFAULT_WIDTH = 316;
  const DEFAULT_HEIGHT = 480;
  const WINDOW_RATIO = DEFAULT_HEIGHT / DEFAULT_WIDTH;
  const MIN_WIDTH = 100;
  const MAX_WIDTH = 420;
  const VIEWPORT_MARGIN = 12;

  let root = null;
  let lastAnimatedEventId = null;
  let amountTimeout = null;
  let revealTimeouts = [];
  let currentLayout = null;
  let interaction = null;
  const defaultMoney = "1.00";
  const defaultMultiplier = "0.00";

  function send(command, value) {
    if (typeof pycmd !== "function") {
      return;
    }
    const suffix = value === undefined ? command : `${command}:${value}`;
    pycmd(`${PREFIX}:${suffix}`);
  }

  function toSymbol(symbol) {
    const normalized = String(symbol || "").toLowerCase();
    return SYMBOLS.includes(normalized) ? normalized : null;
  }

  function ensureRoot() {
    if (root && document.body.contains(root)) {
      return root;
    }

    root = document.createElement("div");
    root.id = "anki-slot-machine-root";
    root.innerHTML = `
      <button class="anki-slot-machine-launcher" data-slot-launcher type="button" aria-label="Reopen slot machine">
        <span class="anki-slot-machine-launcher-dot"></span>
        Reopen Slot
      </button>
      <div class="anki-slot-machine-machine" data-slot-machine>
        <div class="anki-slot-machine-machine-inner" data-slot-machine-inner>
          <div class="anki-slot-machine-titlebar" data-slot-drag-handle>
            <div class="anki-slot-machine-window-controls">
              <button class="anki-slot-machine-window-button is-close" data-slot-close type="button" aria-label="Close slot machine"></button>
            </div>
            <div class="anki-slot-machine-title">Slot Machine</div>
            <div class="anki-slot-machine-titlebar-actions">
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
        <button class="anki-slot-machine-resize" data-slot-resize-handle type="button" aria-label="Resize slot machine"></button>
      </div>
    `;

    document.body.appendChild(root);
    bindWindowControls();
    applyLayout(loadLayout());
    return root;
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function readStoredLayout() {
    try {
      const raw = window.localStorage.getItem(LAYOUT_STORAGE_KEY);
      if (!raw) {
        return null;
      }
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch (_error) {
      return null;
    }
  }

  function saveLayout(layout) {
    try {
      window.localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(layout));
    } catch (_error) {
      // Ignore storage failures and keep the current in-memory layout.
    }
  }

  function persistLayout(layout) {
    saveLayout(layout);
    send("saveLayout", JSON.stringify(layout));
  }

  function defaultLayout() {
    const width = fitWidthToViewport(DEFAULT_WIDTH);
    const height = Math.round(width * WINDOW_RATIO);
    return {
      left: Math.max(VIEWPORT_MARGIN, window.innerWidth - width - 44),
      top: Math.max(VIEWPORT_MARGIN, Math.round((window.innerHeight - height) / 2)),
      width,
      height,
      mode: "open",
    };
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

  function normalizedLayout(layout) {
    const fallback = defaultLayout();
    const mode =
      layout && (layout.mode === "open" || layout.mode === "closed")
        ? layout.mode
        : layout && layout.closed
          ? "closed"
          : "open";
    const widthCandidate =
      Number(layout && layout.width) ||
      (Number(layout && layout.height) ? Number(layout.height) / WINDOW_RATIO : fallback.width);
    const width = fitWidthToViewport(widthCandidate);
    const height = Math.round(width * WINDOW_RATIO);
    const boundsWidth = width;
    const boundsHeight = height;
    const maxLeft = Math.max(VIEWPORT_MARGIN, window.innerWidth - boundsWidth - VIEWPORT_MARGIN);
    const maxTop = Math.max(VIEWPORT_MARGIN, window.innerHeight - boundsHeight - VIEWPORT_MARGIN);
    return {
      left: clamp(Number(layout && layout.left) || fallback.left, VIEWPORT_MARGIN, maxLeft),
      top: clamp(Number(layout && layout.top) || fallback.top, VIEWPORT_MARGIN, maxTop),
      width,
      height,
      mode,
    };
  }

  function loadLayout() {
    return normalizedLayout(readStoredLayout() || defaultLayout());
  }

  function layoutVariables(layout) {
    const scale = layout.width / DEFAULT_WIDTH;
    const symbolSize = 64;
    const reelHeight = 182;
    const windowWidth = 248;
    const breakdownWidth = 192;
    const amountTop = 76;
    const particlesTop = 94;
    return {
      scale,
      symbolSize,
      reelHeight,
      windowWidth,
      breakdownWidth,
      amountTop,
      particlesTop,
    };
  }

  function applyLayout(layout, options) {
    ensureRoot();
    currentLayout = normalizedLayout(layout || currentLayout || defaultLayout());
    const machine = root.querySelector("[data-slot-machine]");
    const launcher = root.querySelector("[data-slot-launcher]");
    const vars = layoutVariables(currentLayout);
    const isClosed = currentLayout.mode === "closed";

    if (isClosed) {
      root.style.left = "auto";
      root.style.top = "auto";
      root.style.right = `${VIEWPORT_MARGIN}px`;
      root.style.bottom = `${VIEWPORT_MARGIN}px`;
      root.style.width = "auto";
      root.style.height = "auto";
    } else {
      root.style.left = `${currentLayout.left}px`;
      root.style.top = `${currentLayout.top}px`;
      root.style.right = "auto";
      root.style.bottom = "auto";
      root.style.width = `${currentLayout.width}px`;
      root.style.height = `${currentLayout.height}px`;
    }
    root.style.setProperty("--slot-window-scale", `${vars.scale}`);
    root.style.setProperty("--slot-scale", "1");
    root.style.setProperty("--slot-machine-symbol-size", `${vars.symbolSize}px`);
    root.style.setProperty("--slot-machine-reel-height", `${vars.reelHeight}px`);
    root.style.setProperty("--slot-machine-window-width", `${vars.windowWidth}px`);
    root.style.setProperty("--slot-machine-breakdown-width", `${vars.breakdownWidth}px`);
    root.style.setProperty("--slot-machine-amount-top", `${vars.amountTop}px`);
    root.style.setProperty("--slot-machine-particles-top", `${vars.particlesTop}px`);
    root.classList.toggle("is-closed", isClosed);
    machine.hidden = isClosed;
    launcher.hidden = !isClosed;

    if (!options || options.persist !== false) {
      persistLayout(currentLayout);
    }
  }

  function updateLayout(patch, options) {
    applyLayout({ ...(currentLayout || defaultLayout()), ...patch }, options);
  }

  function endInteraction() {
    if (interaction && currentLayout) {
      persistLayout(currentLayout);
    }
    interaction = null;
    document.body.classList.remove("anki-slot-machine-is-dragging");
    document.body.classList.remove("anki-slot-machine-is-resizing");
  }

  function beginInteraction(mode, event) {
    if (!currentLayout) {
      applyLayout(defaultLayout());
    }
    interaction = {
      mode,
      startX: event.clientX,
      startY: event.clientY,
      layout: { ...currentLayout },
    };
    document.body.classList.add(
      mode === "move" ? "anki-slot-machine-is-dragging" : "anki-slot-machine-is-resizing",
    );
  }

  function onPointerMove(event) {
    if (!interaction) {
      return;
    }
    event.preventDefault();
    const dx = event.clientX - interaction.startX;
    const dy = event.clientY - interaction.startY;
    if (interaction.mode === "move") {
      applyLayout(
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
      {
        ...interaction.layout,
        width: interaction.layout.width + widthDelta,
      },
      { persist: false },
    );
  }

  function bindWindowControls() {
    if (root.dataset.controlsBound === "true") {
      return;
    }
    root.dataset.controlsBound = "true";

    const dragHandle = root.querySelector("[data-slot-drag-handle]");
    const resizeHandle = root.querySelector("[data-slot-resize-handle]");
    const closeButton = root.querySelector("[data-slot-close]");
    const launcher = root.querySelector("[data-slot-launcher]");

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
      updateLayout({ mode: "closed" });
    });
    closeButton.addEventListener("pointerdown", (event) => {
      event.stopPropagation();
    });

    launcher.addEventListener("click", () => {
      updateLayout({ mode: "open" });
      send("refresh");
    });

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", endInteraction);
    window.addEventListener("pointercancel", endInteraction);
    window.addEventListener("resize", () => applyLayout(currentLayout, { persist: false }));
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

  function clearRevealTimeouts() {
    revealTimeouts.forEach((timeoutId) => window.clearTimeout(timeoutId));
    revealTimeouts = [];
  }

  function clearReels() {
    root.querySelectorAll("[data-slot-reel]").forEach((reel) => {
      reel.classList.remove("is-bright");
      reel.classList.remove("is-pair");
      setReelSymbol(reel, null);
    });
  }

  function showAmount(text, tone) {
    const amount = root.querySelector("[data-slot-amount]");
    const numericValue = Math.abs(Number.parseFloat(String(text).replace(/[^0-9.\\-]/g, "")) || 0);
    const fontScale = Math.max(
      1,
      Math.min(3.2, 1 + Math.pow(numericValue / 8, 0.6) * 0.95),
    );
    amount.textContent = text;
    amount.style.setProperty("--slot-amount-font-scale", String(fontScale));
    amount.className = `anki-slot-machine-amount is-visible is-${tone}`;
    if (amountTimeout) {
      window.clearTimeout(amountTimeout);
    }
    amountTimeout = window.setTimeout(() => {
      amount.style.removeProperty("--slot-amount-font-scale");
      amount.className = "anki-slot-machine-amount";
      amount.textContent = "";
    }, 900);
  }

  function burstParticles(tone) {
    const container = root.querySelector("[data-slot-particles]");
    container.innerHTML = "";
    for (let index = 0; index < 8; index += 1) {
      const particle = document.createElement("div");
      particle.className = `anki-slot-machine-particle is-${tone}`;
      particle.style.left = `${30 + Math.random() * 40}%`;
      particle.style.setProperty("--dx", `${-12 + Math.random() * 24}px`);
      particle.style.setProperty("--dy", `${-18 - Math.random() * 18}px`);
      particle.style.animationDelay = `${index * 18}ms`;
      container.appendChild(particle);
      window.setTimeout(() => particle.remove(), 520);
    }
  }

  function flashLoss() {
    const machine = root.querySelector("[data-slot-machine]");
    machine.classList.remove("is-loss");
    void machine.offsetWidth;
    machine.classList.add("is-loss");
    window.setTimeout(() => machine.classList.remove("is-loss"), 220);
  }

  function maybeAnimate(result) {
    if (currentLayout && currentLayout.mode === "closed") {
      return;
    }
    if (!result || !result.event_id || result.event_id === lastAnimatedEventId) {
      return;
    }
    lastAnimatedEventId = result.event_id;
    clearRevealTimeouts();

    if (result.did_spin && result.animation_enabled) {
      if (result.answer_key === "again") {
        revealSpinResult(result, { highlight: false, pairHighlight: false });
        flashLoss();
        burstParticles("loss");
        showAmount(
          `-$${result.payout || 0}`,
          Number.parseFloat(String(result.payout || 0)) === 0 ? "neutral" : "loss",
        );
      } else if (result.line_hit) {
        revealSpinResult(result, { highlight: true });
        burstParticles("win");
        showAmount(`+$${result.payout}`, "win");
      } else {
        revealSpinResult(result, { highlight: false });
        showAmount(
          `+$${result.payout}`,
          Number.parseFloat(String(result.payout || 0)) > 0 ? "win" : "neutral",
        );
      }
      return;
    }

    renderStaticResult(result);

    if (result.answer_key === "again") {
      flashLoss();
      burstParticles("loss");
      showAmount(
        `-$${result.bet}`,
        Number.parseFloat(String(result.bet || 0)) === 0 ? "neutral" : "loss",
      );
      return;
    }

    if (result.answer_key === "hard") {
      showAmount(`$${result.payout}`, "neutral");
    }
  }

  function revealSpinResult(result, options) {
    const reels = root.querySelectorAll("[data-slot-reel]");
    const symbols = (result.reels || []).map(toSymbol);
    const highlight = Boolean(options && options.highlight);
    const pairHighlight = options && options.pairHighlight === false ? false : true;
    const pairSymbol = !result.line_hit ? toSymbol(result.matched_symbol) : null;
    clearReels();
    reels.forEach((reel, index) => {
      const timeoutId = window.setTimeout(() => {
        if (highlight) {
          reel.classList.add("is-bright");
        } else if (pairHighlight && pairSymbol && symbols[index] === pairSymbol) {
          reel.classList.add("is-pair");
        }
        setReelSymbol(reel, symbols[index] || null);
      }, index * 140);
      revealTimeouts.push(timeoutId);
    });
  }

  function renderStaticResult(result) {
    const reels = root.querySelectorAll("[data-slot-reel]");
    clearRevealTimeouts();
    if (!result || result.answer_key === "hard") {
      clearReels();
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

  function renderBreakdown(result) {
    const baseNode = root.querySelector("[data-slot-base]");
    const bonusNode = root.querySelector("[data-slot-bonus]");
    const totalNode = root.querySelector("[data-slot-total]");

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

  function syncState(nextState) {
    ensureRoot();
    if (nextState && nextState.window_layout) {
      applyLayout(nextState.window_layout, { persist: false });
    } else if (currentLayout == null) {
      applyLayout(loadLayout(), { persist: false });
    }
    root.querySelector("[data-slot-balance]").textContent = `$${nextState.balance || 0}`;
    renderBreakdown(nextState.last_result);
    if (
      nextState.last_result &&
      nextState.last_result.event_id &&
      nextState.last_result.event_id !== lastAnimatedEventId
    ) {
      maybeAnimate(nextState.last_result);
      return;
    }
    renderStaticResult(nextState.last_result);
  }

  window.AnkiSlotMachine = {
    syncState,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => send("refresh"));
  } else {
    send("refresh");
  }
})();

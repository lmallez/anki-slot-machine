(function () {
  if (window.AnkiSlotMachine) {
    return;
  }

  const PREFIX = "anki-slot-machine";
  const SYMBOLS = ["slot_1", "slot_2", "slot_3", "slot_4", "slot_5"];

  let root = null;
  let lastAnimatedEventId = null;
  let amountTimeout = null;
  let revealTimeouts = [];
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
      <div class="anki-slot-machine-machine" data-slot-machine>
        <div class="anki-slot-machine-lights">
          <div class="anki-slot-machine-light"></div>
          <div class="anki-slot-machine-light"></div>
          <div class="anki-slot-machine-light"></div>
          <div class="anki-slot-machine-light"></div>
          <div class="anki-slot-machine-light"></div>
          <div class="anki-slot-machine-light"></div>
          <div class="anki-slot-machine-light"></div>
        </div>
        <div class="anki-slot-machine-balance" data-slot-balance>$0</div>
        <div class="anki-slot-machine-amount" data-slot-amount></div>
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
        <div class="anki-slot-machine-particles" data-slot-particles></div>
      </div>
    `;

    document.body.appendChild(root);
    return root;
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
    amount.textContent = text;
    amount.className = `anki-slot-machine-amount is-visible is-${tone}`;
    if (amountTimeout) {
      window.clearTimeout(amountTimeout);
    }
    amountTimeout = window.setTimeout(() => {
      amount.className = "anki-slot-machine-amount";
      amount.textContent = "";
    }, 700);
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
    if (!result || !result.event_id || result.event_id === lastAnimatedEventId) {
      return;
    }
    lastAnimatedEventId = result.event_id;
    clearRevealTimeouts();

    if (result.did_spin && result.animation_enabled) {
      if (result.line_hit) {
        revealSpinResult(result, { highlight: true });
        burstParticles("win");
        showAmount(`+$${result.payout}`, "win");
      } else {
        revealSpinResult(result, { highlight: false });
        showAmount(`+$${result.payout}`, "neutral");
      }
      return;
    }

    renderStaticResult(result);

    if (result.answer_key === "again") {
      flashLoss();
      burstParticles("loss");
      showAmount(`-$${result.bet}`, "loss");
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
    const pairSymbol = !result.line_hit ? toSymbol(result.matched_symbol) : null;
    clearReels();
    reels.forEach((reel, index) => {
      const timeoutId = window.setTimeout(() => {
        if (highlight) {
          reel.classList.add("is-bright");
        } else if (pairSymbol && symbols[index] === pairSymbol) {
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
    if (!result || result.answer_key === "again" || result.answer_key === "hard") {
      clearReels();
      return;
    }
    const symbols = result.reels ? result.reels.map(toSymbol) : [];
    const pairSymbol = !result.line_hit ? toSymbol(result.matched_symbol) : null;
    reels.forEach((reel, index) => {
      if (result.line_hit) {
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
      baseNode.textContent = `-$${defaultMoney}`;
      bonusNode.textContent = "no spin";
      totalNode.className = "anki-slot-machine-breakdown-line is-total is-negative";
      totalNode.textContent = `= -$${defaultMoney}`;
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

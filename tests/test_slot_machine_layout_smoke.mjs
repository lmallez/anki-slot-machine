import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";


class ClassList {
  constructor() {
    this._classes = new Set();
  }

  add(...names) {
    names.forEach((name) => this._classes.add(name));
  }

  remove(...names) {
    names.forEach((name) => this._classes.delete(name));
  }

  toggle(name, force) {
    if (force === true) {
      this._classes.add(name);
      return true;
    }
    if (force === false) {
      this._classes.delete(name);
      return false;
    }
    if (this._classes.has(name)) {
      this._classes.delete(name);
      return false;
    }
    this._classes.add(name);
    return true;
  }
}


class StyleMap {
  constructor() {
    this._values = new Map();
  }

  setProperty(name, value) {
    this._values.set(name, String(value));
  }

  removeProperty(name) {
    this._values.delete(name);
  }

  getPropertyValue(name) {
    return this._values.get(name) || "";
  }
}


class FakeElement {
  constructor(tagName) {
    this.tagName = tagName;
    this.children = [];
    this.dataset = {};
    this.hidden = false;
    this.textContent = "";
    this.className = "";
    this.classList = new ClassList();
    this.style = new Proxy(new StyleMap(), {
      get(target, prop) {
        if (prop in target) {
          return target[prop].bind ? target[prop].bind(target) : target[prop];
        }
        return target.getPropertyValue(prop);
      },
      set(target, prop, value) {
        target.setProperty(prop, value);
        return true;
      },
    });
    this._selectorMap = new Map();
    this._selectorLists = new Map();
  }

  appendChild(child) {
    this.children.push(child);
    child.parentNode = this;
    return child;
  }

  addEventListener() {}

  querySelector(selector) {
    return this._selectorMap.get(selector) || null;
  }

  querySelectorAll(selector) {
    return this._selectorLists.get(selector) || [];
  }

  set innerHTML(value) {
    this._innerHTML = value;
    if (String(value).includes("data-slot-panel-add")) {
      const collapseButton = new FakeElement("button");
      const addButton = new FakeElement("button");
      const closeAllButton = new FakeElement("button");
      const confirmButton = new FakeElement("button");
      const cancelButton = new FakeElement("button");
      const expandButton = new FakeElement("button");
      this._selectorMap.set("[data-slot-panel-collapse]", collapseButton);
      this._selectorMap.set("[data-slot-panel-add]", addButton);
      this._selectorMap.set("[data-slot-panel-close-all]", closeAllButton);
      this._selectorMap.set("[data-slot-panel-confirm]", confirmButton);
      this._selectorMap.set("[data-slot-panel-cancel]", cancelButton);
      this._selectorMap.set("[data-slot-panel-expand]", expandButton);
      return;
    }
    if (!String(value).includes("data-slot-machine")) {
      return;
    }

    const launcher = new FakeElement("button");
    const machine = new FakeElement("div");
    const dragHandle = new FakeElement("div");
    const resizeHandle = new FakeElement("button");
    const closeButton = new FakeElement("button");
    const statsButton = new FakeElement("button");
    const balance = new FakeElement("div");
    const base = new FakeElement("div");
    const bonus = new FakeElement("div");
    const total = new FakeElement("div");
    const amount = new FakeElement("div");
    const particles = new FakeElement("div");

    const reels = Array.from({ length: 3 }, () => {
      const reel = new FakeElement("div");
      const symbol = new FakeElement("div");
      reel._selectorMap.set("[data-slot-symbol]", symbol);
      return reel;
    });

    this._selectorMap.set("[data-slot-launcher]", launcher);
    this._selectorMap.set("[data-slot-machine]", machine);
    this._selectorMap.set("[data-slot-drag-handle]", dragHandle);
    this._selectorMap.set("[data-slot-resize-handle]", resizeHandle);
    this._selectorMap.set("[data-slot-close]", closeButton);
    this._selectorMap.set("[data-slot-stats]", statsButton);
    this._selectorMap.set("[data-slot-balance]", balance);
    this._selectorMap.set("[data-slot-base]", base);
    this._selectorMap.set("[data-slot-bonus]", bonus);
    this._selectorMap.set("[data-slot-total]", total);
    this._selectorMap.set("[data-slot-amount]", amount);
    this._selectorMap.set("[data-slot-particles]", particles);
    this._selectorLists.set("[data-slot-reel]", reels);
  }
}


const messages = [];
const localStorageMap = new Map();

const document = {
  readyState: "complete",
  currentScript: {
    src: "http://127.0.0.1/_addons/anki_slot_machine/web/slot_machine.js",
  },
  body: {
    children: [],
    classList: new ClassList(),
    appendChild(child) {
      this.children.push(child);
      child.parentNode = this;
      return child;
    },
    contains(child) {
      return this.children.includes(child);
    },
  },
  createElement(tagName) {
    return new FakeElement(tagName);
  },
  addEventListener() {},
};

const windowObject = {
  document,
  innerWidth: 1440,
  innerHeight: 900,
  localStorage: {
    getItem(key) {
      return localStorageMap.has(key) ? localStorageMap.get(key) : null;
    },
    setItem(key, value) {
      localStorageMap.set(key, String(value));
    },
  },
  addEventListener() {},
  setTimeout() {
    return 1;
  },
  clearTimeout() {},
  Math,
  Date,
};

function pycmd(message) {
  messages.push(message);
}

const context = vm.createContext({
  window: windowObject,
  document,
  pycmd,
  console,
  Math,
  Date,
  setTimeout: windowObject.setTimeout,
  clearTimeout: windowObject.clearTimeout,
});
windowObject.pycmd = pycmd;
windowObject.AnkiSlotMachineInstances = {};

const source = fs.readFileSync("src/anki_slot_machine/web/slot_machine.js", "utf8");
vm.runInContext(source, context, { filename: "slot_machine.js" });

assert.deepEqual(messages, ["anki-slot-machine:anki_slot_machine:refresh"]);
assert.equal(document.body.children.length, 0);

const instance = windowObject.AnkiSlotMachineInstances.anki_slot_machine;
assert.ok(instance, "slot machine instance should be registered");

function currentOpenLayout(element) {
  return {
    left: element.style.left,
    top: element.style.top,
    hidden: element.classList.toggle("is-closed", false),
  };
}

instance.syncState({
  balance: "100.00",
  window_layout: { left: 77, top: 88, width: 300, height: 456, mode: "open" },
});

assert.equal(document.body.children.length, 2);
const controlPanel = document.body.children[0];
const root = document.body.children[1];
assert.ok(controlPanel.querySelector("[data-slot-panel-add]"));
const restoredLayout = currentOpenLayout(root);
assert.equal(restoredLayout.left, "77px");
assert.equal(restoredLayout.top, "88px");
assert.equal(root.style.right, "auto");
assert.equal(root.style.bottom, "auto");

instance.syncState({
  balance: "101.00",
  window_layout: { left: 11, top: 22, width: 320, height: 486, mode: "open" },
});

const stableLayout = currentOpenLayout(root);
assert.equal(stableLayout.left, restoredLayout.left);
assert.equal(stableLayout.top, restoredLayout.top);

instance.syncState({
  balance: "103.45",
  machines: [
    { key: "alpha", label: "Alpha" },
    { key: "beta", label: "Beta" },
  ],
  window_layouts: {
    alpha: { left: 40, top: 50, width: 300, height: 456, mode: "open" },
    beta: { left: 80, top: 90, width: 300, height: 456, mode: "open" },
  },
  last_result: {
    event_id: "evt-1",
    machine_results: [
      {
        event_id: "evt-1",
        machine_key: "alpha",
        answer_key: "good",
        payout: "2.50",
        did_spin: true,
        animation_enabled: true,
        reels: ["SLOT_1", "SLOT_1", "SLOT_1"],
        line_hit: true,
      },
      {
        event_id: "evt-1",
        machine_key: "beta",
        answer_key: "good",
        payout: "0.95",
        did_spin: true,
        animation_enabled: true,
        reels: ["SLOT_2", "SLOT_5", "SLOT_2"],
        line_hit: false,
        matched_symbol: "SLOT_2",
      },
    ],
  },
});

assert.equal(document.body.children.length, 4);
const alphaRoot = document.body.children[2];
const betaRoot = document.body.children[3];
assert.equal(alphaRoot.style.left, "40px");
assert.equal(alphaRoot.style.top, "50px");
assert.equal(betaRoot.style.left, "80px");
assert.equal(betaRoot.style.top, "90px");

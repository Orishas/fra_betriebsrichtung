/**
 * Dashboard card tests. Run with: node --test tests/
 *
 * The card is plain DOM, so a tiny stub is enough — no jsdom, no build step.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import assert from "node:assert/strict";
import test from "node:test";

const cardPath = join(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "custom_components",
  "fra_betriebsrichtung",
  "www",
  "fra-betriebsrichtung-card.js",
);

const rendered = { html: "" };

globalThis.HTMLElement = class {
  attachShadow() {
    this.shadowRoot = {
      set innerHTML(value) {
        rendered.html = value;
      },
      get innerHTML() {
        return rendered.html;
      },
      querySelector: () => null,
      querySelectorAll: () => [],
    };
    return this.shadowRoot;
  }

  get isConnected() {
    return true;
  }

  dispatchEvent() {}
};
globalThis.customElements = { get: () => undefined, define: () => {} };
globalThis.window = { customCards: [], setInterval: () => 0, clearInterval: () => {} };
globalThis.document = { createElement: () => ({}) };
globalThis.CustomEvent = class {};

const Card = new Function(
  `${readFileSync(cardPath, "utf8")}\nreturn FraBetriebsrichtungCard;`,
)();

const hoursFromNow = (hours) =>
  new Date(Date.now() + hours * 3600000).toISOString();

function render(states, config = {}) {
  rendered.html = "";
  const card = new Card();
  card.setConfig({ type: "custom:fra-betriebsrichtung-card", ...config });
  card.hass = { locale: { language: "de", time_format: "24" }, states };
  card._render();
  return rendered.html;
}

function forecastStates(slots, extra = {}) {
  const now = new Date().toISOString();
  return {
    "sensor.fra_betriebsrichtung_forecast": {
      state: "BR 25",
      last_updated: now,
      attributes: { slots, source: "Umwelthaus", last_update: "Donnerstag, 6 Uhr" },
    },
    "sensor.fra_betriebsrichtung_current_direction": {
      state: "BR 25",
      last_updated: now,
      attributes: {
        label: "BR 25 West",
        current_since_start: hoursFromNow(-40),
        current_duration_minutes: 2400,
      },
    },
    "binary_sensor.fra_betriebsrichtung_aircraft_noise": {
      state: "on",
      last_updated: now,
      attributes: { noise_direction: "BR 25", current_direction: "BR 25" },
    },
    ...extra,
  };
}

const kinds = (html) =>
  [...html.matchAll(/data-kind="(\w+)"/g)].map((match) => match[1]);

/** Segments of one track, as {kind, width} — tracks are rendered in day order. */
const trackSegments = (html, index) => {
  const track = html.split('<div class="track')[index + 1] || "";
  return [
    ...track.matchAll(/flex: 0 0 ([\d.]+)%[\s\S]*?data-kind="(\w+)"/g),
  ].map((match) => ({ width: Number(match[1]), kind: match[2] }));
};

/** Midnight-anchored ISO timestamp, N days from today at the given hour. */
const atDay = (days, hour) => {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() + days);
  date.setHours(hour);
  return date.toISOString();
};

test("segment width follows slot duration, not slot count", () => {
  const html = render(
    forecastStates([
      { direction: "BR 25", start: atDay(1, 0), end: atDay(1, 6) },
      { direction: "BR 07", start: atDay(1, 6), end: atDay(2, 0) },
    ]),
  );
  const segments = trackSegments(html, 1);
  assert.deepEqual(
    segments.map((segment) => segment.kind),
    ["noise", "quiet"],
  );
  assert.ok(Math.abs(segments[0].width - 25) < 0.01, "6 h slot covers a quarter");
  assert.ok(Math.abs(segments[1].width - 75) < 0.01, "18 h slot covers the rest");
});

test("missing slots become a visible gap instead of stretching neighbours", () => {
  const html = render(
    forecastStates([
      { direction: "BR 25", start: atDay(1, 0), end: atDay(1, 6) },
      { direction: "BR 07", start: atDay(1, 12), end: atDay(2, 0) },
    ]),
  );
  const segments = trackSegments(html, 1);
  assert.deepEqual(
    segments.map((segment) => segment.kind),
    ["noise", "gap", "quiet"],
  );
  assert.deepEqual(
    segments.map((segment) => Math.round(segment.width)),
    [25, 25, 50],
  );
});

test("transition slots are classified as a change, not as noise", () => {
  const html = render(
    forecastStates([
      { direction: "BR 07/BR 25", start: hoursFromNow(-1), end: hoursFromNow(7) },
    ]),
  );
  assert.ok(kinds(html).includes("mixed"));
});

test("noise direction is taken from the integration, not from card config", () => {
  const states = forecastStates([
    { direction: "BR 07", start: hoursFromNow(-1), end: hoursFromNow(7) },
  ]);
  states["binary_sensor.fra_betriebsrichtung_aircraft_noise"].attributes.noise_direction =
    "BR 07";
  assert.ok(kinds(render(states)).includes("noise"));

  states["binary_sensor.fra_betriebsrichtung_aircraft_noise"].attributes.noise_direction =
    "BR 25";
  assert.ok(kinds(render(states)).includes("quiet"));
});

test("the now marker is rendered once, on today's row", () => {
  const html = render(
    forecastStates([
      { direction: "BR 25", start: hoursFromNow(-1), end: hoursFromNow(30) },
    ]),
  );
  assert.equal((html.match(/class="now"/g) || []).length, 1);
});

test("both layouts render without undefined values", () => {
  for (const layout of ["days", "compact"]) {
    const html = render(
      forecastStates([
        { direction: "BR 25", start: hoursFromNow(-2), end: hoursFromNow(6) },
        { direction: "BR 07", start: hoursFromNow(6), end: hoursFromNow(30) },
      ]),
      { layout },
    );
    assert.ok(!/undefined|NaN|Invalid Date/.test(html), `${layout} layout is clean`);
  }
});

test("a slot without ISO timestamps is skipped instead of breaking the card", () => {
  const html = render(
    forecastStates([{ from: "06:00", to: "14:00", direction: "BR 07" }]),
  );
  assert.ok(!/undefined|NaN|Invalid Date/.test(html));
});

test("without integration entities the card explains what to do", () => {
  const html = render({ "light.kitchen": { state: "on", attributes: {} } });
  assert.match(html, /FRA Betriebsrichtung/);
  assert.equal(kinds(html).length, 0);
});

test("stale forecast data is flagged", () => {
  const states = forecastStates([
    { direction: "BR 25", start: hoursFromNow(-2), end: hoursFromNow(6) },
  ]);
  states["sensor.fra_betriebsrichtung_forecast"].last_updated = hoursFromNow(-30);
  assert.match(render(states), /footer stale/);
});

test("invalid configuration is rejected", () => {
  const card = new Card();
  assert.throws(() => card.setConfig({ layout: "spiral" }), /layout/);
  assert.throws(() => card.setConfig({ days: 0 }), /days/);
});

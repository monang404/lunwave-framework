import { describe, it, expect, beforeEach } from "vitest";
import { dom, initDOM } from "../../web/static/shared/js/dom.js";

describe("dom.js", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    // Reset the shared `dom` object between tests since initDOM() mutates
    // the same exported object every call (Object.assign, no reset).
    Object.keys(dom).forEach((k) => delete dom[k]);
  });

  it("wires up dom.* to the matching elements by id when present", () => {
    document.body.innerHTML = `
      <div id="portal-screen"></div>
      <button id="admin-submit-btn"></button>
      <input id="search-input" />
    `;
    initDOM();

    expect(dom.portalScreen).toBe(document.getElementById("portal-screen"));
    expect(dom.adminSubmitBtn).toBe(document.getElementById("admin-submit-btn"));
    expect(dom.searchInput).toBe(document.getElementById("search-input"));
  });

  it("sets a property to null when the corresponding element is missing from the DOM", () => {
    initDOM();
    expect(dom.portalScreen).toBeNull();
    expect(dom.logoutBtn).toBeNull();
  });

  it("computes rowUnheardLabel from row-unheard's previous sibling when present", () => {
    document.body.innerHTML = `
      <div id="row-unheard-label-row"></div>
      <div id="row-unheard"></div>
    `;
    initDOM();
    expect(dom.rowUnheardLabel).toBe(document.getElementById("row-unheard-label-row"));
  });

  it("sets rowUnheardLabel to null when row-unheard itself is missing", () => {
    initDOM();
    expect(dom.rowUnheard).toBeNull();
    expect(dom.rowUnheardLabel).toBeNull();
  });

  it("resolves filterScopeHint via querySelector scoped under #tab-discover", () => {
    document.body.innerHTML = `
      <div id="tab-discover">
        <span class="filter-scope-hint">hint</span>
      </div>
    `;
    initDOM();
    expect(dom.filterScopeHint).not.toBeNull();
    expect(dom.filterScopeHint.textContent).toBe("hint");
  });
});

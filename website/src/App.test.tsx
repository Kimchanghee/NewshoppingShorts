import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const originalScrollIntoView = Object.getOwnPropertyDescriptor(Element.prototype, "scrollIntoView");
const originalScrollTo = Object.getOwnPropertyDescriptor(window, "scrollTo");

vi.mock("./pages/Index", () => ({
  default: () => (
    <div>
      home route
      <section id="pricing">pricing section</section>
    </div>
  ),
}));
vi.mock("./pages/Notice", () => ({ default: () => <div>notice route</div> }));
vi.mock("./pages/Contact", () => ({ default: () => <div>contact route</div> }));
vi.mock("./pages/NotFound", () => ({ default: () => <div>not found route</div> }));
vi.mock("@/components/Analytics", () => ({ default: () => null }));

beforeEach(() => {
  Object.defineProperty(window, "scrollTo", {
    configurable: true,
    value: vi.fn(),
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  if (originalScrollIntoView) {
    Object.defineProperty(Element.prototype, "scrollIntoView", originalScrollIntoView);
  } else {
    Reflect.deleteProperty(Element.prototype, "scrollIntoView");
  }
  if (originalScrollTo) {
    Object.defineProperty(window, "scrollTo", originalScrollTo);
  } else {
    Reflect.deleteProperty(window, "scrollTo");
  }
  window.history.replaceState({}, "", "/");
});

describe.each([
  ["/", "home route"],
  ["/notice/index.html", "notice route"],
  ["/notice/release-v1.5.64/index.html", "notice route"],
  ["/contact/index.html", "contact route"],
  ["/missing", "not found route"],
])("lazy route %s", (path, expectedText) => {
  it(`renders ${expectedText}`, async () => {
    window.history.replaceState({}, "", path);

    render(<App />);

    expect(await screen.findByText(expectedText)).toBeInTheDocument();
  });
});

it("scrolls to a hash target after its lazy route is mounted", async () => {
  const scrollIntoView = vi.fn();
  const scrollTo = vi.mocked(window.scrollTo);
  Object.defineProperty(Element.prototype, "scrollIntoView", {
    configurable: true,
    value: scrollIntoView,
  });
  window.history.replaceState({}, "", "/#pricing");

  render(<App />);

  await screen.findByText("pricing section");
  await waitFor(() => expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "start" }));
  expect(scrollTo).not.toHaveBeenCalled();
});

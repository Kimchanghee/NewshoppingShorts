import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import Navigation from "./Navigation";

function renderNavigation() {
  return render(
    <MemoryRouter>
      <Navigation />
    </MemoryRouter>,
  );
}

afterEach(() => {
  document.body.style.overflow = "";
});

describe("responsive navigation", () => {
  it("opens an accessible touch menu and closes it with Escape", () => {
    renderNavigation();

    const toggle = screen.getByRole("button", { name: "메뉴 열기" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle.className).toContain("h-11");
    expect(toggle.className).toContain("w-11");

    fireEvent.click(toggle);

    expect(screen.getByRole("button", { name: "메뉴 닫기", expanded: true })).toBeInTheDocument();
    expect(document.getElementById("site-mobile-menu")).toBeInTheDocument();
    expect(document.body.style.overflow).toBe("hidden");

    fireEvent.keyDown(window, { key: "Escape" });

    expect(screen.getByRole("button", { name: "메뉴 열기" })).toHaveAttribute("aria-expanded", "false");
    expect(document.getElementById("site-mobile-menu")).not.toBeInTheDocument();
  });
});

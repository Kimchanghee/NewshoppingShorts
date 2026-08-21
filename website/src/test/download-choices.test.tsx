import { readFileSync } from "node:fs";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DownloadChoices } from "@/components/DownloadChoices";
import {
  DIRECT_DOWNLOAD_URL,
  DIRECT_INSTALLER_CHANNEL,
  DIRECT_INSTALLER_RELEASE_DATE,
  DIRECT_INSTALLER_VERSION,
  LATEST_VERIFIED_BUILD_DATE,
  LATEST_VERIFIED_BUILD_VERSION,
  LATEST_VERIFIED_RELEASE_URL,
  MS_STORE_URL,
} from "@/constants/release";

afterEach(() => cleanup());

describe("download choices", () => {
  it("keeps the no-JavaScript fallback on the same immutable direct installer", () => {
    const staticHtml = readFileSync("index.html", "utf8");

    expect(staticHtml).toContain(`href="${DIRECT_DOWNLOAD_URL}"`);
    expect(staticHtml).toContain(`v${DIRECT_INSTALLER_VERSION} 일반 설치 파일 받기`);
    expect(staticHtml).not.toContain("releases/download/source-v");
  });

  it("offers the Microsoft Store and the public direct installer as distinct choices", () => {
    render(<DownloadChoices placement="test" />);

    expect(screen.getByRole("group", { name: "SSMaker 다운로드 방법" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Microsoft Store에서 SSMaker 설치(새 창)" })).toHaveAttribute(
      "href",
      MS_STORE_URL,
    );
    expect(screen.getByRole("link", { name: /일반 설치 파일 받기/ })).toHaveAttribute("href", DIRECT_DOWNLOAD_URL);
    expect(screen.getByRole("link", { name: `v${LATEST_VERIFIED_BUILD_VERSION} 릴리스 정보` })).toHaveAttribute(
      "href",
      LATEST_VERIFIED_RELEASE_URL,
    );
    expect(screen.getAllByText(new RegExp(`v${DIRECT_INSTALLER_VERSION.replaceAll(".", "\\.")}`)).length).toBeGreaterThan(0);
    expect(screen.getByText(/Store 심사·등록 상태에 따라 최신 버전 반영이 늦을 수 있습니다/)).toBeInTheDocument();
    expect(screen.getAllByText(new RegExp(LATEST_VERIFIED_BUILD_DATE.replaceAll(".", "\\."))).length).toBeGreaterThan(0);
    expect(screen.getAllByText(new RegExp(DIRECT_INSTALLER_RELEASE_DATE.replaceAll(".", "\\."))).length).toBeGreaterThan(0);
    expect(screen.getByText(new RegExp(`현재 안전하게 공개된 일반 설치 파일은 v${DIRECT_INSTALLER_VERSION.replaceAll(".", "\\.")}`))).toBeInTheDocument();
  });

  it("records the selected distribution channel without changing the existing event name", () => {
    const gtag = vi.fn();
    window.gtag = gtag;
    render(<DownloadChoices placement="hero" />);

    fireEvent.click(screen.getByRole("link", { name: /Microsoft Store에서 SSMaker 설치/ }));
    fireEvent.click(screen.getByRole("link", { name: /일반 설치 파일 받기/ }));

    expect(gtag).toHaveBeenCalledWith("event", "download_click", {
      placement: "hero",
      channel: "microsoft_store",
    });
    expect(gtag).toHaveBeenCalledWith("event", "download_click", {
      placement: "hero",
      channel: "direct_installer",
      distribution: DIRECT_INSTALLER_CHANNEL,
      version: DIRECT_INSTALLER_VERSION,
    });
  });
});

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DownloadChoices } from "@/components/DownloadChoices";
import {
  DIRECT_DOWNLOAD_URL,
  DIRECT_INSTALLER_RELEASE_DATE,
  LATEST_VERIFIED_BUILD_DATE,
  LATEST_VERIFIED_BUILD_VERSION,
  LATEST_VERIFIED_RELEASE_URL,
  MS_STORE_URL,
} from "@/constants/release";

afterEach(() => cleanup());

describe("download choices", () => {
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
    expect(screen.getAllByText(/v1\.5\.70/).length).toBeGreaterThan(0);
    expect(screen.getByText(new RegExp(`권장 · 자동 업데이트 · 앱 최신 v${LATEST_VERIFIED_BUILD_VERSION}`))).toBeInTheDocument();
    expect(screen.getAllByText(new RegExp(LATEST_VERIFIED_BUILD_DATE.replaceAll(".", "\\."))).length).toBeGreaterThan(0);
    expect(screen.getByText(new RegExp(DIRECT_INSTALLER_RELEASE_DATE.replaceAll(".", "\\.")))).toBeInTheDocument();
    expect(screen.getByText(/현재 안전하게 공개된 일반 설치 파일은 v1\.5\.70/)).toBeInTheDocument();
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
      distribution: "manual-direct",
      version: "1.5.70",
    });
  });
});

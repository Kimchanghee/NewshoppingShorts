import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HelmetProvider } from "react-helmet-async";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SAMPLE_VIDEO_COUNT, VIDEO_SAMPLES } from "@/data/samples";
import Samples from "./Samples";

const play = vi.fn(() => Promise.resolve());
const pause = vi.fn();

function renderPage() {
  return render(
    <HelmetProvider>
      <MemoryRouter>
        <Samples />
      </MemoryRouter>
    </HelmetProvider>,
  );
}

beforeEach(() => {
  vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(play);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(pause);
});

afterEach(() => {
  vi.restoreAllMocks();
  play.mockClear();
  pause.mockClear();
});

describe("Samples page", () => {
  it("renders ten Before/After pairs and twenty playable videos by default", () => {
    renderPage();

    expect(screen.getAllByTestId("sample-card")).toHaveLength(10);
    expect(screen.getAllByTestId("sample-video")).toHaveLength(SAMPLE_VIDEO_COUNT);
    expect(screen.getByRole("link", { name: "샘플" })).toHaveAttribute("href", "/samples/index.html");

    for (const video of screen.getAllByTestId("sample-video")) {
      expect(video).toHaveAttribute("controls");
      expect(video).toHaveAttribute("playsinline");
      expect(video).toHaveAttribute("preload", "metadata");
      expect(video.querySelector("source")).toHaveAttribute("type", "video/mp4");
    }
  });

  it("filters the page to the five new full-automation samples", () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "풀자동 제작 5" }));

    expect(screen.getAllByTestId("sample-card")).toHaveLength(5);
    expect(screen.getAllByTestId("sample-video")).toHaveLength(10);
    expect(screen.getByText("휴대용 미니 냉풍기")).toBeInTheDocument();
    expect(screen.queryByText("전동 우유 거품기")).not.toBeInTheDocument();
  });

  it("starts both videos from zero and mutes only the source when pair playback is requested", async () => {
    renderPage();
    const button = screen.getByRole("button", { name: "전동 우유 거품기 Before/After 동시에 재생" });
    const videos = screen.getAllByTestId("sample-video").slice(0, 2) as HTMLVideoElement[];
    videos[0].currentTime = 3;
    videos[1].currentTime = 4;

    fireEvent.click(button);

    await waitFor(() => expect(play).toHaveBeenCalledTimes(2));
    expect(videos[0].currentTime).toBe(0);
    expect(videos[1].currentTime).toBe(0);
    expect(videos[0].muted).toBe(true);
    expect(videos[1].muted).toBe(false);
  });

  it("uses twenty unique public release asset URLs", () => {
    const videos = VIDEO_SAMPLES.flatMap((sample) => [sample.beforeVideo, sample.afterVideo]);
    expect(new Set(videos)).toHaveProperty("size", 20);
    expect(videos).toHaveLength(20);
    for (const url of videos) {
      expect(new URL(url).protocol).toBe("https:");
      expect(url).toContain("/Kimchanghee/NewshoppingShorts/releases/download/");
      expect(url).toMatch(/\.mp4$/);
    }
  });

  it("publishes complete duration and upload metadata for every indexed video", () => {
    for (const sample of VIDEO_SAMPLES) {
      expect(Number.isNaN(Date.parse(sample.uploadDate))).toBe(false);
      expect(sample.beforeDuration).toMatch(/^PT\d+(?:\.\d+)?S$/);
      expect(sample.afterDuration).toMatch(/^PT\d+(?:\.\d+)?S$/);
      if (sample.category === "automation") {
        expect(sample.uploadDate).toMatch(/^2026-08-16T/);
        expect(sample.afterVideo).toContain("website-samples-scripted-20260816");
        expect(Number.parseFloat(sample.afterDuration.slice(2, -1))).toBeGreaterThanOrEqual(10);
      }
    }
  });
});

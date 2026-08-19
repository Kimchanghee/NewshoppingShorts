import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "@/App";
import { buildSoftwareApplicationSchema } from "@/lib/structuredData";

afterEach(() => cleanup());

describe("public website contracts", () => {
  it("describes the real link mix and sequential queue behavior", () => {
    const schema = buildSoftwareApplicationSchema();
    const features = schema.featureList as string[];

    expect(features).toContain("영상 링크 2~5개 믹스 및 순차 대기 목록 처리");
    expect(features.join(" ")).not.toMatch(/4개.*병렬|동시에.*4개/);
  });

  it("renders a localized not-found route", async () => {
    window.history.pushState({}, "", "/missing-page");
    render(<App />);

    expect(await screen.findByText("페이지를 찾을 수 없습니다.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "홈으로 돌아가기" })).toHaveAttribute("href", "/");
  });
});

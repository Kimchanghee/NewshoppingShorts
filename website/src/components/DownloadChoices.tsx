import { Button } from "@/components/ui/button";
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
import { gaEvent } from "@/lib/ga4";
import { cn } from "@/lib/utils";
import { Download, Store } from "lucide-react";

type DownloadChoicesProps = {
  placement: string;
  size?: "default" | "xl";
  showHint?: boolean;
  stacked?: boolean;
  className?: string;
};

export function DownloadChoices({
  placement,
  size = "xl",
  showHint = true,
  stacked = false,
  className,
}: DownloadChoicesProps) {
  return (
    <div className={cn("mx-auto w-full max-w-2xl", className)}>
      <p className="mb-4 text-center text-sm leading-relaxed text-muted-foreground">
        최신 검증 빌드{" "}
        <a
          href={LATEST_VERIFIED_RELEASE_URL}
          className="font-semibold text-primary underline-offset-4 hover:underline"
          aria-label={`v${LATEST_VERIFIED_BUILD_VERSION} 릴리스 정보`}
        >
          v{LATEST_VERIFIED_BUILD_VERSION}
        </a>
        <span> · {LATEST_VERIFIED_BUILD_DATE} 업데이트 · Windows 정식 빌드</span>
      </p>
      <div
        className={cn("grid w-full gap-3", !stacked && "sm:grid-cols-2")}
        role="group"
        aria-label="SSMaker 다운로드 방법"
      >
        <div className="flex min-w-0 flex-col gap-2">
          <Button variant="hero" size={size} asChild className="h-auto min-h-12 w-full px-4 py-3">
            <a
              href={MS_STORE_URL}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Microsoft Store에서 SSMaker 설치(새 창)"
              onClick={() =>
                gaEvent("download_click", {
                  placement,
                  channel: "microsoft_store",
                })
              }
            >
              <Store aria-hidden="true" className="h-5 w-5 shrink-0" />
              <span className="min-w-0 text-center leading-snug">Microsoft Store에서 설치</span>
            </a>
          </Button>
          <span className="text-center text-xs font-medium leading-relaxed text-primary">
            Store 심사·등록 상태에 따라 최신 버전 반영이 늦을 수 있습니다
          </span>
        </div>

        <div className="flex min-w-0 flex-col gap-2">
          <Button variant="hero-outline" size={size} asChild className="h-auto min-h-12 w-full px-4 py-3">
            <a
              href={DIRECT_DOWNLOAD_URL}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`SSMaker v${DIRECT_INSTALLER_VERSION} 일반 설치 파일 받기(새 창)`}
              onClick={() =>
                gaEvent("download_click", {
                  placement,
                  channel: "direct_installer",
                  distribution: DIRECT_INSTALLER_CHANNEL,
                  version: DIRECT_INSTALLER_VERSION,
                })
              }
            >
              <Download aria-hidden="true" className="h-5 w-5 shrink-0" />
              <span className="min-w-0 text-center leading-snug">일반 설치 파일 받기</span>
            </a>
          </Button>
          <span className="text-center text-xs text-muted-foreground">
            최신 정식판 v{DIRECT_INSTALLER_VERSION} · {DIRECT_INSTALLER_RELEASE_DATE} 공개 · Windows .exe
          </span>
        </div>
      </div>

      {showHint && (
        <p className="mt-4 text-center text-xs leading-relaxed text-muted-foreground">
          현재 안전하게 공개된 일반 설치 파일은 v{DIRECT_INSTALLER_VERSION}입니다. 두 설치 방식 중 하나만 선택하세요.
          일반 설치판은 Windows 보호 화면이 표시되면 추가 정보를 눌러 실행할 수 있습니다.
        </p>
      )}
    </div>
  );
}

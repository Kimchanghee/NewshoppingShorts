import { Button } from "@/components/ui/button";
import {
  DIRECT_DOWNLOAD_URL,
  DIRECT_INSTALLER_CHANNEL,
  DIRECT_INSTALLER_VERSION,
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
      <div
        className={cn("grid w-full gap-3", !stacked && "sm:grid-cols-2")}
        role="group"
        aria-label="SSMaker 다운로드 방법"
      >
        <div className="flex min-w-0 flex-col gap-2">
          <Button variant="hero" size={size} asChild className="h-auto min-h-12 w-full px-5 py-3">
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
              <Store aria-hidden="true" className="h-5 w-5" />
              Microsoft Store에서 설치
            </a>
          </Button>
          <span className="text-center text-xs font-medium text-primary">권장 · 자동 업데이트</span>
        </div>

        <div className="flex min-w-0 flex-col gap-2">
          <Button variant="hero-outline" size={size} asChild className="h-auto min-h-12 w-full px-5 py-3">
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
              <Download aria-hidden="true" className="h-5 w-5" />
              일반 설치 파일 받기
            </a>
          </Button>
          <span className="text-center text-xs text-muted-foreground">
            v{DIRECT_INSTALLER_VERSION} · 기존 일반판 사용자용 .exe
          </span>
        </div>
      </div>

      {showHint && (
        <p className="mt-4 text-center text-xs leading-relaxed text-muted-foreground">
          두 설치 방식 중 하나만 선택하세요. 일반 설치판은 Windows 보호 화면이 표시되면 추가 정보를 눌러 실행할 수
          있습니다.
        </p>
      )}
    </div>
  );
}

import { useState, useRef } from "react";
import { Play, Pause, Volume2, VolumeX, Maximize } from "lucide-react";
import { FadeIn } from "@/components/FadeIn";
import { DEMO_VIDEO_FALLBACK_URL, DEMO_VIDEO_PRIMARY_URL } from "@/constants/release";

export default function DemoVideo() {
    const videoRef = useRef<HTMLVideoElement>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [isMuted, setIsMuted] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [videoSrc, setVideoSrc] = useState(DEMO_VIDEO_PRIMARY_URL);

    const handleVideoError = () => {
        if (videoSrc !== DEMO_VIDEO_FALLBACK_URL) {
            setVideoSrc(DEMO_VIDEO_FALLBACK_URL);
            setTimeout(() => videoRef.current?.load(), 0);
            return;
        }
        // "\uB370\uBAA8 \uC601\uC0C1\uC744 \uBD88\uB7EC\uC624\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4. \uB9C1\uD06C/\uD30C\uC77C\uBA85\uC744 \uD655\uC778\uD574 \uC8FC\uC138\uC694."
        setLoadError("\uB370\uBAA8 \uC601\uC0C1\uC744 \uBD88\uB7EC\uC624\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4. \uB9C1\uD06C/\uD30C\uC77C\uBA85\uC744 \uD655\uC778\uD574 \uC8FC\uC138\uC694.");
    };

    const togglePlay = () => {
        if (videoRef.current) {
            if (isPlaying) {
                videoRef.current.pause();
            } else {
                setLoadError(null);
                const p = videoRef.current.play();
                // Some browsers reject play() if the media can't be loaded or the gesture policy blocks it.
                if (p && typeof (p as Promise<void>).catch === "function") {
                    (p as Promise<void>).catch(() => {
                        // Let onError/onPlay/onPause drive the UI; just surface a helpful message.
                        setLoadError("데모 영상을 재생할 수 없습니다. 영상 링크/파일명을 확인해 주세요.");
                    });
                }
            }
        }
    };

    const toggleMute = () => {
        if (videoRef.current) {
            videoRef.current.muted = !isMuted;
            setIsMuted(!isMuted);
        }
    };

    const toggleFullscreen = () => {
        if (videoRef.current) {
            if (document.fullscreenElement) {
                document.exitFullscreen();
            } else {
                videoRef.current.requestFullscreen();
            }
        }
    };

    const handleTimeUpdate = () => {
        if (videoRef.current) {
            setCurrentTime(videoRef.current.currentTime);
        }
    };

    const handleLoadedMetadata = () => {
        if (videoRef.current) {
            setDuration(videoRef.current.duration);
            setLoadError(null);
        }
    };

    const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
        const time = parseFloat(e.target.value);
        if (videoRef.current) {
            videoRef.current.currentTime = time;
            setCurrentTime(time);
        }
    };

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    return (
        <section id="demo-video" className="relative bg-secondary/20 py-16 sm:py-20 lg:py-28">
            <div className="container mx-auto px-4 sm:px-6">
                <FadeIn>
                    <div className="mb-10 text-center sm:mb-12">
                        <p className="mb-3 text-sm font-medium uppercase tracking-widest text-primary">
                            Demo Video
                        </p>
                        <h2 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">
                            실제 작동 모습을 확인하세요
                        </h2>
                        <p className="mt-4 text-muted-foreground">
                            SSMaker가 어떻게 중국 영상을 한국어 숏폼으로 변환하는지 직접 보세요
                        </p>
                    </div>
                </FadeIn>

                <FadeIn delay={0.2}>
                    <div className="max-w-4xl mx-auto">
                        <div className="glass-card rounded-2xl overflow-hidden border border-primary/20 shadow-glow-sm">
                            {/* Video Container */}
                            <div className="relative bg-black aspect-video">
                                <video
                                    ref={videoRef}
                                    className="w-full h-full"
                                    src={videoSrc}
                                    preload="metadata"
                                    playsInline
                                    muted={isMuted}
                                    onTimeUpdate={handleTimeUpdate}
                                    onLoadedMetadata={handleLoadedMetadata}
                                    onPlay={() => {
                                        setIsPlaying(true);
                                        setLoadError(null);
                                    }}
                                    onPause={() => setIsPlaying(false)}
                                    onEnded={() => setIsPlaying(false)}
                                    onError={handleVideoError}
                                    onClick={togglePlay}
                                >
                                    Your browser does not support the video tag.
                                </video>

                                {/* Play Overlay */}
                                {!isPlaying && (
                                    <div
                                        className="absolute inset-0 flex items-center justify-center bg-black/30 cursor-pointer transition-opacity hover:bg-black/40"
                                        onClick={togglePlay}
                                    >
                                        <div className="flex flex-col items-center gap-3 px-6">
                                            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/90 backdrop-blur-sm transition-transform hover:scale-110 sm:h-20 sm:w-20">
                                                <Play className="ml-1 h-8 w-8 text-primary-foreground sm:h-10 sm:w-10" />
                                            </div>
                                            {loadError && (
                                                <p className="text-center text-sm text-white/90 max-w-[420px]">
                                                    {loadError}
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Controls */}
                            <div className="space-y-3 bg-background/95 p-3 backdrop-blur-sm sm:p-4">
                                {/* Progress Bar */}
                                <div className="flex items-center gap-3">
                                    <span className="text-xs text-muted-foreground min-w-[40px]">
                                        {formatTime(currentTime)}
                                    </span>
                                    <input
                                        type="range"
                                        min="0"
                                        max={duration || 0}
                                        value={currentTime}
                                        onChange={handleSeek}
                                        className="flex-1 h-1 bg-secondary rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-moz-range-thumb]:w-3 [&::-moz-range-thumb]:h-3 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0"
                                    />
                                    <span className="text-xs text-muted-foreground min-w-[40px]">
                                        {formatTime(duration)}
                                    </span>
                                </div>

                                {/* Control Buttons */}
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={togglePlay}
                                            aria-label={isPlaying ? "영상 일시정지" : "영상 재생"}
                                            className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors hover:bg-primary/20"
                                        >
                                            {isPlaying ? (
                                                <Pause className="h-4 w-4" />
                                            ) : (
                                                <Play className="h-4 w-4" />
                                            )}
                                        </button>

                                        <button
                                            onClick={toggleMute}
                                            aria-label={isMuted ? "소리 켜기" : "음소거"}
                                            className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors hover:bg-primary/20"
                                        >
                                            {isMuted ? (
                                                <VolumeX className="h-4 w-4" />
                                            ) : (
                                                <Volume2 className="h-4 w-4" />
                                            )}
                                        </button>
                                    </div>

                                    <button
                                        onClick={toggleFullscreen}
                                        aria-label="전체 화면"
                                        className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors hover:bg-primary/20"
                                    >
                                        <Maximize className="h-4 w-4" />
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </FadeIn>
            </div>
        </section>
    );
}

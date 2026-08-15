import { useState, useEffect } from "react";
import { Slider } from "@/components/ui/slider";
import { FadeIn } from "@/components/FadeIn";

export default function ROICalculator() {
    const [videosPerDay, setVideosPerDay] = useState([5]);
    const [timePerVideo, setTimePerVideo] = useState([45]); // minutes
    const [hourlyRate, setHourlyRate] = useState([10000]); // KRW

    const [savedTime, setSavedTime] = useState(0); // hours per month
    const [savedMoney, setSavedMoney] = useState(0); // KRW per month

    useEffect(() => {
        // Estimate with a configurable manual-time baseline and a 3-minute automated-processing assumption.
        const manualTime = videosPerDay[0] * timePerVideo[0]; // minutes/day
        const autoTime = videosPerDay[0] * 3; // minutes/day - SSMaker time
        const timeDiffDaily = manualTime - autoTime;

        // Monthly (20 working days)
        const timeDiffMonthly = (timeDiffDaily * 20) / 60; // hours
        setSavedTime(Math.max(0, Math.round(timeDiffMonthly)));

        const moneyDiffMonthly = timeDiffMonthly * hourlyRate[0];
        setSavedMoney(Math.max(0, Math.round(moneyDiffMonthly)));

    }, [videosPerDay, timePerVideo, hourlyRate]);

    return (
        <div className="mt-16 w-full max-w-4xl mx-auto">
            <FadeIn delay={0.3}>
                <div className="glass-card rounded-2xl p-8 md:p-12 border border-primary/20 bg-background/50 backdrop-blur-md">
                    <div className="text-center mb-10">
                        <h3 className="text-2xl font-bold text-foreground">예상 작업 시간 계산하기</h3>
                        <p className="text-muted-foreground mt-2">현재 작업 시간과 비교해 자동 처리 기준의 예상 차이를 확인해보세요</p>
                    </div>

                    <div className="grid gap-12 md:grid-cols-2">

                        {/* Inputs */}
                        <div className="space-y-8">
                            <div className="space-y-4">
                                <div className="flex justify-between">
                                    <span className="font-medium text-foreground">하루 제작 영상 수</span>
                                    <span className="text-primary font-bold">{videosPerDay}개</span>
                                </div>
                                <Slider
                                    value={videosPerDay}
                                    onValueChange={setVideosPerDay}
                                    max={50}
                                    min={1}
                                    step={1}
                                    className="py-2"
                                />
                            </div>

                            <div className="space-y-4">
                                <div className="flex justify-between">
                                    <span className="font-medium text-foreground">현재 영상당 소요 시간</span>
                                    <span className="text-primary font-bold">{timePerVideo}분</span>
                                </div>
                                <Slider
                                    value={timePerVideo}
                                    onValueChange={setTimePerVideo}
                                    max={120}
                                    min={10}
                                    step={5}
                                    className="py-2"
                                />
                            </div>

                            <div className="space-y-4">
                                <div className="flex justify-between">
                                    <span className="font-medium text-foreground">시간당 인건비 가치</span>
                                    <span className="text-primary font-bold">{hourlyRate[0].toLocaleString()}원</span>
                                </div>
                                <Slider
                                    value={hourlyRate}
                                    onValueChange={setHourlyRate}
                                    max={50000}
                                    min={9860}
                                    step={100}
                                    className="py-2"
                                />
                            </div>
                        </div>

                        {/* Results */}
                        <div className="flex flex-col justify-center gap-6 bg-secondary/30 rounded-xl p-6 border border-white/5">
                            <div className="text-center">
                                <p className="text-sm font-medium text-muted-foreground mb-1">월 예상 단축 시간</p>
                                <div className="text-4xl font-extrabold text-gradient">
                                    {savedTime}시간
                                </div>
                                <p className="text-xs text-muted-foreground mt-1">자동 처리 3분 기준의 단순 계산값입니다</p>
                            </div>

                            <div className="h-px bg-white/10 w-full" />

                            <div className="text-center">
                                <p className="text-sm font-medium text-muted-foreground mb-1">월 예상 인건비 환산</p>
                                <div className="text-4xl font-extrabold text-gradient">
                                    {savedMoney.toLocaleString()}원
                                </div>
                                <p className="text-xs text-muted-foreground mt-1">사용자가 입력한 시간당 가치 기준입니다</p>
                            </div>
                        </div>

                    </div>
                </div>
            </FadeIn>
        </div>
    );
}

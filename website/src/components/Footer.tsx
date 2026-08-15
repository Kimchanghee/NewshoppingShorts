import { MessageCircle, MapPin } from "lucide-react";
import { Link } from "react-router-dom";
import {
  BUSINESS_ADDRESS,
  BUSINESS_NAME,
  BUSINESS_REGISTRATION_NUMBER,
  BUSINESS_REPRESENTATIVE,
  BUSINESS_TYPE,
} from "@/constants/site";

export default function Footer() {
  return (
    <footer className="border-t border-border/50 bg-secondary/10 py-12">
      <div className="container mx-auto px-6">
        {/* Top Section */}
        <div className="grid gap-8 md:grid-cols-3 mb-8">
          {/* Brand */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <span className="text-xl font-bold text-foreground">
                SS<span className="text-gradient">Maker</span>
              </span>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              중국 쇼핑 영상을 AI로 자동 변환하는 스마트 솔루션
            </p>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="font-semibold text-foreground mb-4">바로가기</h3>
            <div className="flex flex-col gap-2">
              <Link to="/#features" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                기능 소개
              </Link>
              <Link to="/#pricing" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                요금제
              </Link>
              <Link to="/#setup-guide" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                초기 세팅 가이드
              </Link>
              <Link to="/samples/index.html" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                영상 샘플
              </Link>
              <Link to="/notice/index.html" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                공지사항
              </Link>
              <Link to="/contact/index.html" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                문의하기
              </Link>
            </div>
          </div>

          {/* Contact */}
          <div>
            <h3 className="font-semibold text-foreground mb-4">문의</h3>
            <div className="flex flex-col gap-3">
              <Link
                to="/contact/index.html"
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <MessageCircle className="h-4 w-4" />
                카카오톡 문의
              </Link>
            </div>
          </div>
        </div>

        {/* Divider */}
        <div className="border-t border-border/50 my-8" />

        {/* Business Info */}
        <div className="space-y-2 mb-6">
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>상호: {BUSINESS_NAME}</span>
            <span>대표: {BUSINESS_REPRESENTATIVE}</span>
            <span>사업자등록번호: {BUSINESS_REGISTRATION_NUMBER}</span>
          </div>
          <div className="flex items-start gap-2 text-xs text-muted-foreground">
            <MapPin className="h-3 w-3 mt-0.5 flex-shrink-0" />
            <span>
              {BUSINESS_ADDRESS.addressRegion} {BUSINESS_ADDRESS.addressLocality} {BUSINESS_ADDRESS.streetAddress}
              (송도동, 송도타임스페이스)
            </span>
          </div>
          <div className="text-xs text-muted-foreground">
            <span>업태: {BUSINESS_TYPE}</span>
          </div>
        </div>

        {/* Copyright */}
        <p className="text-center text-xs text-muted-foreground">
          © 2026 {BUSINESS_NAME}. All rights reserved.
        </p>
      </div>
    </footer>
  );
}

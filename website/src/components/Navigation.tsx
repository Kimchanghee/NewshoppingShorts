import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Download, Menu, X } from "lucide-react";
import { Link } from "react-router-dom";
import { LATEST_VERIFIED_BUILD_VERSION } from "@/constants/release";

const navLinks = [
  { label: "기능", href: "#features" },
  { label: "효율성", href: "#efficiency" },
  { label: "요금제", href: "#pricing" },
  { label: "가이드", href: "#setup-guide" },
  { label: "FAQ", href: "#faq" },
  { label: "공지사항", href: "/notice/index.html" },
  { label: "문의", href: "/contact/index.html" },
];

export default function Navigation() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled ? "glass border-b border-border/50" : "bg-transparent"
      }`}
    >
      <nav className="container mx-auto flex min-h-16 items-center justify-between px-4 py-2 sm:px-6">
        <Link to="/" className="text-xl font-bold tracking-tight text-foreground">
          SS<span className="text-gradient">Maker</span>
        </Link>

        {/* Desktop */}
        <div className="hidden items-center gap-5 lg:flex xl:gap-8">
          {navLinks.map((link) => {
            const to = link.href.startsWith("#") ? `/${link.href}` : link.href;
            return (
              <Link key={to} to={to} className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                {link.label}
              </Link>
            );
          })}
          <Button variant="hero" size="sm" asChild>
            <a href="#download">
              <Download className="mr-1 h-4 w-4" />
              다운로드 v{LATEST_VERIFIED_BUILD_VERSION}
            </a>
          </Button>
        </div>

        {/* Mobile toggle */}
        <button
          className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md text-foreground hover:bg-secondary lg:hidden"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label={mobileOpen ? "메뉴 닫기" : "메뉴 열기"}
          aria-expanded={mobileOpen}
          aria-controls="mobile-navigation"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </nav>

      {/* Mobile menu */}
      {mobileOpen && (
        <div id="mobile-navigation" className="glass border-t border-border/50 lg:hidden">
          <div className="container mx-auto flex max-h-[calc(100svh-4rem)] flex-col gap-2 overflow-y-auto px-4 py-4 sm:px-6">
            {navLinks.map((link) => {
              const to = link.href.startsWith("#") ? `/${link.href}` : link.href;
              return (
                <Link
                  key={to}
                  to={to}
                  className="flex min-h-11 items-center rounded-md px-3 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                  onClick={() => setMobileOpen(false)}
                >
                  {link.label}
                </Link>
              );
            })}
            <Button variant="hero" size="sm" asChild>
              <a href="#download" onClick={() => setMobileOpen(false)}>
                <Download className="mr-1 h-4 w-4" />
                다운로드 v{LATEST_VERIFIED_BUILD_VERSION}
              </a>
            </Button>
          </div>
        </div>
      )}
    </header>
  );
}

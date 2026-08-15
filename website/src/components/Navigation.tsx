import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Download, Menu, X } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { DOWNLOAD_URL } from "@/constants/release";
import { gaEvent } from "@/lib/ga4";

const navLinks = [
  { label: "기능", href: "#features" },
  { label: "샘플", href: "/samples/index.html" },
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
  const location = useLocation();
  const downloadUrl = DOWNLOAD_URL;

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname, location.hash]);

  useEffect(() => {
    if (!mobileOpen) return;

    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false);
    };

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [mobileOpen]);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled || mobileOpen ? "glass border-b border-border/50" : "bg-transparent"
      }`}
    >
      <nav className="container relative z-20 mx-auto flex h-16 items-center justify-between px-4 sm:h-[72px] sm:px-6">
        <Link to="/" className="inline-flex min-h-11 items-center text-xl font-bold tracking-tight text-foreground">
          SS<span className="text-gradient">Maker</span>
        </Link>

        {/* Desktop */}
        <div className="hidden items-center gap-4 xl:flex xl:gap-5">
          {navLinks.map((link) => {
            const to = link.href.startsWith("#") ? `/${link.href}` : link.href;
            return (
              <Link key={to} to={to} className="inline-flex min-h-11 items-center text-sm text-muted-foreground transition-colors hover:text-foreground">
                {link.label}
              </Link>
            );
          })}
          <Button variant="hero" size="sm" asChild>
            <a href={downloadUrl} rel="noopener noreferrer" onClick={() => gaEvent("download_click", { placement: "nav_desktop" })}>
              <Download className="mr-1 h-4 w-4" />
              Store에서 받기
            </a>
          </Button>
        </div>

        {/* Mobile toggle */}
        <button
          type="button"
          className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-black/20 text-foreground transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary xl:hidden"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label={mobileOpen ? "메뉴 닫기" : "메뉴 열기"}
          aria-expanded={mobileOpen}
          aria-controls="site-mobile-menu"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </nav>

      {/* Mobile menu */}
      {mobileOpen && (
        <>
          <button
            type="button"
            aria-label="메뉴 닫기"
            className="fixed inset-x-0 bottom-0 top-16 z-0 cursor-default bg-black/55 backdrop-blur-[2px] sm:top-[72px] xl:hidden"
            onClick={() => setMobileOpen(false)}
          />
          <div
            id="site-mobile-menu"
            className="glass fixed inset-x-0 top-16 z-10 max-h-[calc(100svh-4rem)] overflow-y-auto border-t border-border/50 shadow-2xl sm:top-[72px] sm:max-h-[calc(100svh-4.5rem)] xl:hidden"
          >
          <div className="container mx-auto grid grid-cols-2 gap-2 px-4 py-4 sm:grid-cols-3 sm:px-6 sm:py-6 lg:grid-cols-4">
            {navLinks.map((link) => {
              const to = link.href.startsWith("#") ? `/${link.href}` : link.href;
              return (
                <Link
                  key={to}
                  to={to}
                  className="inline-flex min-h-11 items-center rounded-xl border border-transparent px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:border-white/10 hover:bg-white/5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  onClick={() => setMobileOpen(false)}
                >
                  {link.label}
                </Link>
              );
            })}
            <Button variant="hero" size="sm" asChild className="col-span-2 mt-2 min-h-11 sm:col-span-3 lg:col-span-4">
              <a href={downloadUrl} rel="noopener noreferrer" onClick={() => gaEvent("download_click", { placement: "nav_mobile" })}>
                <Download className="mr-1 h-4 w-4" />
                Store에서 받기
              </a>
            </Button>
          </div>
          </div>
        </>
      )}
    </header>
  );
}

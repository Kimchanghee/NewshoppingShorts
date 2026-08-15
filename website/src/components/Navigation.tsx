import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Download, Menu, X } from "lucide-react";
import { Link } from "react-router-dom";
import { DOWNLOAD_URL } from "@/constants/release";
import { gaEvent } from "@/lib/ga4";

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
  const downloadUrl = DOWNLOAD_URL;

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
      <nav className="container mx-auto flex h-16 items-center justify-between px-6">
        <Link to="/" className="text-xl font-bold tracking-tight text-foreground">
          SS<span className="text-gradient">Maker</span>
        </Link>

        {/* Desktop */}
        <div className="hidden items-center gap-8 md:flex">
          {navLinks.map((link) => {
            const to = link.href.startsWith("#") ? `/${link.href}` : link.href;
            return (
              <Link key={to} to={to} className="text-sm text-muted-foreground transition-colors hover:text-foreground">
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
          className="text-foreground md:hidden"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </nav>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="glass border-t border-border/50 md:hidden">
          <div className="container mx-auto flex flex-col gap-4 px-6 py-6">
            {navLinks.map((link) => {
              const to = link.href.startsWith("#") ? `/${link.href}` : link.href;
              return (
                <Link
                  key={to}
                  to={to}
                  className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                  onClick={() => setMobileOpen(false)}
                >
                  {link.label}
                </Link>
              );
            })}
            <Button variant="hero" size="sm" asChild>
              <a href={downloadUrl} rel="noopener noreferrer" onClick={() => gaEvent("download_click", { placement: "nav_mobile" })}>
                <Download className="mr-1 h-4 w-4" />
                Store에서 받기
              </a>
            </Button>
          </div>
        </div>
      )}
    </header>
  );
}

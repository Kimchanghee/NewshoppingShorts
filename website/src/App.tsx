import { lazy, Suspense } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import ScrollToHash from "@/components/ScrollToHash";
import { ThemeProvider } from "@/components/theme-provider";
import { HelmetProvider } from "react-helmet-async";
import Analytics from "@/components/Analytics";

const Index = lazy(() => import("./pages/Index"));
const Notice = lazy(() => import("./pages/Notice"));
const Contact = lazy(() => import("./pages/Contact"));
const Privacy = lazy(() => import("./pages/Privacy"));
const NotFound = lazy(() => import("./pages/NotFound"));

const queryClient = new QueryClient();

const App = () => (
  <HelmetProvider>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
            <Analytics />
            <ScrollToHash />
            <Suspense fallback={<div className="flex min-h-screen items-center justify-center">화면을 불러오는 중...</div>}>
              <Routes>
                <Route path="/" element={<Index />} />
                <Route path="/notice" element={<Notice />} />
                <Route path="/notice/index.html" element={<Notice />} />
                <Route path="/notice/:slug" element={<Notice />} />
                <Route path="/notice/:slug/index.html" element={<Notice />} />
                <Route path="/contact" element={<Contact />} />
                <Route path="/contact/index.html" element={<Contact />} />
                <Route path="/privacy" element={<Privacy />} />
                <Route path="/privacy/index.html" element={<Privacy />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </HelmetProvider>
);

export default App;

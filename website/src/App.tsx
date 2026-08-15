import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import ScrollToHash from "@/components/ScrollToHash";
import { ThemeProvider } from "@/components/theme-provider";
import { HelmetProvider } from "react-helmet-async";
import Analytics from "@/components/Analytics";

const Index = lazy(() => import("./pages/Index"));
const Notice = lazy(() => import("./pages/Notice"));
const Contact = lazy(() => import("./pages/Contact"));
const Samples = lazy(() => import("./pages/Samples"));
const NotFound = lazy(() => import("./pages/NotFound"));

const queryClient = new QueryClient();

const App = () => (
  <HelmetProvider>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
        <BrowserRouter>
          <Analytics />
          <Suspense fallback={<div className="min-h-screen bg-background" aria-busy="true" />}>
            <ScrollToHash />
            <Routes>
              <Route path="/" element={<Index />} />
              <Route path="/notice" element={<Notice />} />
              <Route path="/notice/index.html" element={<Notice />} />
              <Route path="/notice/:slug" element={<Notice />} />
              <Route path="/notice/:slug/index.html" element={<Notice />} />
              <Route path="/contact" element={<Contact />} />
              <Route path="/contact/index.html" element={<Contact />} />
              <Route path="/samples" element={<Samples />} />
              <Route path="/samples/index.html" element={<Samples />} />
              {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  </HelmetProvider>
);

export default App;

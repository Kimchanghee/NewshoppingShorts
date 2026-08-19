import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import ScrollToHash from "@/components/ScrollToHash";
import { ThemeProvider } from "@/components/theme-provider";
import { HelmetProvider } from "react-helmet-async";
import Analytics from "@/components/Analytics";
import Index from "./pages/Index";
import Notice from "./pages/Notice";
import Contact from "./pages/Contact";
import Privacy from "./pages/Privacy";
import NotFound from "./pages/NotFound";

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
              {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </HelmetProvider>
);

export default App;

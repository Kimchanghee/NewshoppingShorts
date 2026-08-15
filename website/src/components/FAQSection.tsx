import { FadeIn } from "@/components/FadeIn";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { FAQS } from "@/data/faqs";

export default function FAQSection() {
  return (
    <section id="faq" className="relative py-24 md:py-32">
      <div className="section-glow absolute inset-0" />
      <div className="container relative mx-auto px-6">
        <FadeIn>
          <div className="text-center">
            <p className="mb-3 text-sm font-medium uppercase tracking-widest text-primary">
              FAQ
            </p>
            <h2 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">
              자주 묻는 질문
            </h2>
          </div>
        </FadeIn>

        <FadeIn delay={0.2}>
          <div className="mx-auto mt-12 max-w-2xl">
            <Accordion type="single" collapsible className="space-y-3">
              {FAQS.map((faq, i) => (
                <AccordionItem
                  key={i}
                  value={`item-${i}`}
                  className="glass-card rounded-xl border-none px-6 data-[state=open]:shadow-glow-sm"
                >
                  <AccordionTrigger className="py-5 text-left text-[15px] font-medium text-foreground hover:no-underline">
                    {faq.question}
                  </AccordionTrigger>
                  <AccordionContent className="pb-5 text-sm leading-relaxed text-muted-foreground">
                    {faq.answer}
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}

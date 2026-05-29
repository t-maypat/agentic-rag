import { ArrowRight } from "lucide-react";
import { Suspense, lazy, useState } from "react";

const Dithering = lazy(() =>
  import("@paper-design/shaders-react").then((mod) => ({ default: mod.Dithering }))
);

type CTASectionProps = {
  onEnter: () => void;
};

export function CTASection({ onEnter }: CTASectionProps) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <section className="py-12 w-full flex justify-center items-center px-4 md:px-6 min-h-[calc(100vh-52px)]">
      <div
        className="w-full max-w-7xl relative"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <div className="relative overflow-hidden rounded-[48px] border border-border bg-card shadow-sm min-h-[600px] md:min-h-[600px] flex flex-col items-center justify-center duration-500">
          <Suspense fallback={<div className="absolute inset-0 bg-muted/20" />}>
            <div className="absolute inset-0 z-0 pointer-events-none opacity-40 mix-blend-multiply">
              <Dithering
                colorBack="#00000000"
                colorFront="#EC4E02"
                shape="warp"
                type="4x4"
                speed={isHovered ? 0.6 : 0.2}
                className="size-full"
                minPixelRatio={1}
              />
            </div>
          </Suspense>

          <div className="relative z-10 px-6 max-w-5xl mx-auto text-center flex flex-col items-center">
            <h2 className="font-serif text-5xl md:text-7xl lg:text-8xl font-medium tracking-tight text-foreground mb-8 leading-[1.05]">
              Ask better questions,
              <br />
              <span className="text-foreground/80">grounded in real research.</span>
            </h2>

            <p className="text-muted-foreground text-lg md:text-xl max-w-3xl mb-12 leading-relaxed">
              Research RAG Studio turns dense papers, retrieval benchmarks, and RAG references into
              a source-backed workspace with hybrid search, visible traces, and answers you can
              audit.
            </p>

            <button
              className="group relative inline-flex h-14 items-center justify-center gap-3 overflow-hidden rounded-full bg-black px-12 text-base font-medium text-white transition-all duration-300 hover:bg-black/90 hover:scale-105 active:scale-95 hover:ring-4 hover:ring-black/15"
              onClick={onEnter}
            >
              <span className="relative z-10">Enter the studio</span>
              <ArrowRight className="h-5 w-5 relative z-10 transition-transform duration-300 group-hover:translate-x-1" />
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

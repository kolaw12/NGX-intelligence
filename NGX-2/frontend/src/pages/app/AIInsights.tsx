import { PageHeader } from "@/components/common/PageHeader";
import { useAIInsights, useMarketSentiment } from "@/hooks/useAIInsights";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AIInsightCard } from "@/components/ai/AIInsightCard";
import { GaugeChart } from "@/components/charts/GaugeChart";
import { CardSkeleton, ChartSkeleton } from "@/components/common/LoadingSkeleton";
import { BrainCircuit } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function AIInsights() {
  const insights = useAIInsights();
  const sentiment = useMarketSentiment();

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Intelligence"
        title="Explainable AI insights"
        description="Confidence-scored, factor-attributed outlooks across the NGX universe — generated with reproducible model lineage."
      />

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BrainCircuit className="h-4 w-4 text-cyan" /> Market sentiment
            </CardTitle>
            <CardDescription>
              {sentiment.data?.source === "sentiment_pipeline_json" || sentiment.data?.source === "nlp_engine"
                ? "Primary source: NLP news sentiment"
                : "NLP-first sentiment with market fallback"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {sentiment.data ? (
              <>
                <p className="text-sm leading-relaxed text-muted-foreground">{sentiment.data.summary}</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {sentiment.data.drivers.map((d) => (
                    <div key={d.label} className="rounded-lg border border-border bg-surface-elevated/60 p-3">
                      <div className="flex items-center justify-between">
                        <Badge
                          variant={d.direction === "positive" ? "success" : d.direction === "negative" ? "danger" : "default"}
                        >
                          {d.direction}
                        </Badge>
                        <span className="text-[11px] tabular-nums text-muted-foreground">
                          {(d.weight * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p className="mt-2 text-sm text-foreground">{d.label}</p>
                    </div>
                  ))}
                </div>
              </>
            ) : <CardSkeleton rows={4} />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Sentiment gauge</CardTitle>
            <CardDescription>0 is extreme fear, 100 is extreme greed</CardDescription>
          </CardHeader>
          <CardContent>
            {sentiment.data ? <GaugeChart value={sentiment.data.score} label={sentiment.data.label} height={240} /> : <ChartSkeleton height={240} />}
          </CardContent>
        </Card>
      </div>

      <div>
        <h2 className="mb-4 text-base font-semibold text-foreground">Top-conviction outlooks</h2>
        {insights.isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} rows={3} />)}
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {insights.data?.map((i) => <AIInsightCard key={i.symbol} insight={i} />)}
          </div>
        )}
      </div>
    </div>
  );
}

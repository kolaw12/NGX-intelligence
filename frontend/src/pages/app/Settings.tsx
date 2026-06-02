import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useEngineHealth, useModelStatus } from "@/hooks/useEngineStatus";
import { useSentimentDiagnostics } from "@/hooks/useAIInsights";
import { authService, type ApiToken } from "@/services/auth.service";

interface ToggleRow {
  key: string;
  label: string;
  desc: string;
  defaultOn: boolean;
}

const NOTIFY_TOGGLES: ToggleRow[] = [
  { key: "alerts.email", label: "Email alerts", desc: "Receive alert events in your inbox.", defaultOn: true },
  { key: "alerts.push", label: "Push notifications", desc: "Browser push notifications for triggered alerts.", defaultOn: false },
  { key: "digest.daily", label: "Daily intelligence digest", desc: "Morning summary of overnight events and AI updates.", defaultOn: true },
  { key: "digest.weekly", label: "Weekly review", desc: "Friday end-of-week intelligence summary.", defaultOn: false },
];

const DISPLAY_TOGGLES: ToggleRow[] = [
  { key: "display.dark", label: "Dark theme", desc: "Use dark interface (recommended for trading hours).", defaultOn: true },
  { key: "display.tabular", label: "Tabular numerics", desc: "Monospaced numbers for table alignment.", defaultOn: true },
  { key: "display.dense", label: "Dense layout", desc: "Reduce spacing in tables and lists.", defaultOn: false },
];

export default function Settings() {
  const qc = useQueryClient();
  const modelStatus = useModelStatus();
  const engineHealth = useEngineHealth();
  const sentimentDiagnostics = useSentimentDiagnostics();
  const fundamentalsCheck = engineHealth.data?.checks.fundamentals_service;
  const fundamentalsSource = String(fundamentalsCheck?.source ?? "unavailable");
  const fundamentalsRows = Number(fundamentalsCheck?.fundamentalsRows ?? 0);
  const profileRows = Number(fundamentalsCheck?.profileRows ?? 0);
  const fundamentalsLabel =
    fundamentalsSource === "fundamentals" ? "Loaded" : fundamentalsSource === "market_data_fallback" ? "Fallback" : fundamentalsSource === "company_profiles" ? "Profiles" : "Unavailable";
  const fundamentalsVariant =
    fundamentalsSource === "fundamentals" || fundamentalsSource === "company_profiles"
      ? "success"
      : fundamentalsSource === "market_data_fallback"
        ? "warning"
        : "danger";
  const fundamentalsDescription =
    fundamentalsSource === "fundamentals"
      ? `${fundamentalsRows} filing rows`
      : fundamentalsSource === "company_profiles"
        ? `${profileRows} company profiles loaded`
        : fundamentalsSource === "market_data_fallback"
          ? "Market-data metrics available; real filings export not found."
          : "No fundamentals or market-data fallback is available.";
  const settings = useQuery({
    queryKey: ["profile", "settings"],
    queryFn: authService.getSettings,
  });
  const apiTokens = useQuery({
    queryKey: ["api-tokens"],
    queryFn: authService.listApiTokens,
  });
  const [newToken, setNewToken] = useState<string | null>(null);
  const [toggles, setToggles] = useState<Record<string, boolean>>(() => {
    const out: Record<string, boolean> = {};
    [...NOTIFY_TOGGLES, ...DISPLAY_TOGGLES].forEach((t) => (out[t.key] = t.defaultOn));
    return out;
  });

  useEffect(() => {
    if (!settings.data?.settings) return;
    setToggles((prev) => ({ ...prev, ...settings.data.settings }));
  }, [settings.data]);

  const saveSettings = useMutation({
    mutationFn: () => authService.updateSettings(toggles),
    onSuccess: () => {
      toast.success("Settings saved.");
      qc.invalidateQueries({ queryKey: ["profile", "settings"] });
    },
    onError: () => toast.error("Settings could not be saved."),
  });

  const createToken = useMutation({
    mutationFn: () => authService.createApiToken("Personal API token"),
    onSuccess: (token: ApiToken) => {
      setNewToken(token.token ?? null);
      toast.success("API token created. Copy it now; it will not be shown again.");
      qc.invalidateQueries({ queryKey: ["api-tokens"] });
    },
    onError: () => toast.error("API token could not be created."),
  });

  const revokeToken = useMutation({
    mutationFn: (id: string) => authService.revokeApiToken(id),
    onSuccess: () => {
      toast.success("API token revoked.");
      qc.invalidateQueries({ queryKey: ["api-tokens"] });
    },
    onError: () => toast.error("API token could not be revoked."),
  });

  function set(key: string, value: boolean) {
    setToggles((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Settings"
        title="Workspace settings"
        description="Customize notifications, display preferences, and account behavior."
      />

      <Card>
        <CardHeader>
          <CardTitle>Engine status</CardTitle>
          <CardDescription>Live backend model and data-engine state.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          <div className="rounded-lg border border-border bg-surface-elevated/40 p-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-semibold text-foreground">XGBoost</p>
              <Badge variant={modelStatus.data?.xgboost_loaded ? "success" : "danger"}>
                {modelStatus.isLoading ? "Checking" : modelStatus.data?.xgboost_loaded ? "Loaded" : "Unavailable"}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              {modelStatus.data
                ? `${modelStatus.data.xgb_feature_count} features from ${modelStatus.data.xgb_feature_list_path ?? "missing feature list"}`
                : modelStatus.error
                  ? "Model status unavailable."
                  : "Loading model status..."}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-surface-elevated/40 p-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-semibold text-foreground">Engine health</p>
              <Badge variant={engineHealth.data?.status === "ok" ? "success" : "warning"}>
                {engineHealth.isLoading ? "Checking" : engineHealth.data?.status ?? "Unavailable"}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              LSTM: {modelStatus.data?.use_lstm ? (modelStatus.data.lstm_loaded ? "enabled and loaded" : "enabled but unavailable") : "disabled"}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-surface-elevated/40 p-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-semibold text-foreground">Fundamentals</p>
              <Badge variant={fundamentalsVariant}>{fundamentalsLabel}</Badge>
            </div>
            <p className="text-xs text-muted-foreground">{fundamentalsDescription}</p>
          </div>
          <div className="rounded-lg border border-border bg-surface-elevated/40 p-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-semibold text-foreground">Sentiment</p>
              <Badge variant={sentimentDiagnostics.data?.fallbackActive ? "warning" : "success"}>
                {sentimentDiagnostics.data?.source ?? "Checking"}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              {sentimentDiagnostics.data
                ? `${sentimentDiagnostics.data.articlesLoaded} articles, ${sentimentDiagnostics.data.tickersCovered} tickers covered`
                : "Loading sentiment diagnostics..."}
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
          <CardDescription>Choose how and when you hear from the platform.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {NOTIFY_TOGGLES.map((t) => (
            <div key={t.key} className="flex items-start justify-between gap-4 border-b border-border/60 pb-4 last:border-0 last:pb-0">
              <div>
                <p className="text-sm font-semibold text-foreground">{t.label}</p>
                <p className="text-xs text-muted-foreground">{t.desc}</p>
              </div>
              <Switch checked={toggles[t.key]} onCheckedChange={(v) => set(t.key, v)} />
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Display</CardTitle>
          <CardDescription>Tune the workspace for your screen and reading style.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {DISPLAY_TOGGLES.map((t) => (
            <div key={t.key} className="flex items-start justify-between gap-4 border-b border-border/60 pb-4 last:border-0 last:pb-0">
              <div>
                <p className="text-sm font-semibold text-foreground">{t.label}</p>
                <p className="text-xs text-muted-foreground">{t.desc}</p>
              </div>
              <Switch checked={toggles[t.key]} onCheckedChange={(v) => set(t.key, v)} />
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>API access</CardTitle>
          <CardDescription>Personal access tokens for the upcoming public API.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {newToken ? (
            <div className="rounded-lg border border-success/40 bg-success/10 p-4">
              <p className="mb-2 text-sm font-semibold text-foreground">New token</p>
              <code className="block overflow-x-auto rounded-md bg-surface-muted px-3 py-2 text-xs text-foreground">
                {newToken}
              </code>
            </div>
          ) : null}
          {apiTokens.isLoading ? (
            <div className="rounded-lg border border-border bg-surface-elevated/40 p-4 text-sm text-muted-foreground">
              Loading API tokens...
            </div>
          ) : apiTokens.data?.length ? (
            <div className="space-y-2">
              {apiTokens.data.map((token) => (
                <div key={token.id} className="flex items-center justify-between rounded-lg border border-border bg-surface-elevated/40 p-4">
                  <div>
                    <p className="text-sm font-semibold text-foreground">{token.name}</p>
                    <p className="text-xs text-muted-foreground">
                      Prefix {token.prefix} - created {new Date(token.createdAt).toLocaleDateString()}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => revokeToken.mutate(token.id)}
                    disabled={revokeToken.isPending}
                  >
                    Revoke
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-surface-elevated/40 p-4 text-sm text-muted-foreground">
              No active API tokens.
            </div>
          )}
          <Button variant="outline" size="sm" onClick={() => createToken.mutate()} disabled={createToken.isPending}>
            Create API token
          </Button>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={() => saveSettings.mutate()} disabled={saveSettings.isPending || settings.isLoading}>
          Save changes
        </Button>
      </div>
    </div>
  );
}

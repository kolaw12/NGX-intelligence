import { http } from "./http.client";

export interface ModelStatus {
  xgboost_loaded: boolean;
  xgboost_model_path: string | null;
  xgb_feature_list_path: string | null;
  xgb_feature_count: number;
  xgb_error?: string | null;
  lstm_loaded: boolean;
  lstm_model_path: string | null;
  lstm_scaler_path: string | null;
  use_lstm: boolean;
  lstm_quality_passed: boolean;
  lstm_quality_reason: string | null;
  lstm_quality_requirements: Record<string, unknown>;
  lstm_used_in_final_decision: boolean;
  prediction_strategy: "xgboost_only" | "xgboost_led_lstm_ready" | "xgboost_lstm_weighted";
  main_model: "xgboost";
  backend_config_loaded: boolean;
  backend_config_path: string | null;
  xgb_metrics: Record<string, unknown>;
  lstm_metrics: Record<string, number>;
  last_loaded: string;
}

export interface EngineHealth {
  status: "ok" | "degraded";
  main_model: "xgboost";
  checks: Record<string, Record<string, unknown>>;
}

export const engineService = {
  modelStatus: async (): Promise<ModelStatus> => {
    return http.get<ModelStatus>("/model/status");
  },

  engineHealth: async (): Promise<EngineHealth> => {
    return http.get<EngineHealth>("/engine/health");
  },
};

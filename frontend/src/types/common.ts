export type AsyncStatus = "idle" | "loading" | "success" | "error";

export type Range = "1D" | "5D" | "1M" | "3M" | "6M" | "1Y" | "5Y" | "MAX";

export interface OHLC {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface SeriesPoint {
  time: string;
  value: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
}

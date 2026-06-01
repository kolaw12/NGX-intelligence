import type { AIOutlook } from "./stock";

export interface Sector {
  slug: string;
  name: string;
  performanceDay: number;
  performanceWeek: number;
  performanceMonth: number;
  performanceYtd: number;
  marketCap: number;
  componentCount: number;
  aiOutlook: AIOutlook;
  momentum: number;
  riskScore: number;
  sparkline: number[];
  summary: string;
  topConstituents: string[];
}

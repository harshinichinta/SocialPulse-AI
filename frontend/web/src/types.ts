export type Sentiment = "positive" | "neutral" | "negative";

export interface Post {
  post_id: string;
  text: string;
  processed_text: string;
  timestamp: string | null;
  platform: string;
  brand: string;
  sentiment: Sentiment;
  sentiment_confidence: number;
  sentiment_scores: Record<Sentiment, number>;
}

export interface Topic {
  topic_id: number;
  label: string;
  mentions: number;
  terms: string[];
  sentiment_distribution: Partial<Record<Sentiment, number>>;
  representative_posts: string[];
  coherence: number | null;
}

export interface Trend {
  topic: string;
  current_mentions: number;
  previous_mentions: number;
  absolute_change: number;
  growth_percent: number | null;
  rank_score: number;
  sentiment_distribution: Partial<Record<Sentiment, number>>;
  keywords: string[];
  representative_posts: string[];
  period_start: string;
  period_end: string;
  window_days: number;
  reason: string;
  score_method: string;
  limitation: string;
}

export interface Insight {
  title: string;
  topic: string | null;
  evidence: string;
  period: string;
  mentions: number;
  previous_mentions: number | null;
  growth_percent: number | null;
  sentiment_distribution: Record<string, number>;
  keywords: string[];
  representative_posts: string[];
  limitation: string;
  recommendation: string;
}

export interface BrandSummary {
  brand: string;
  mentions: number;
  positive: number;
  neutral: number;
  negative: number;
}

export interface DashboardData {
  dataset: Record<string, unknown>;
  summary: {
    total_posts: number;
    sentiment_counts: Record<Sentiment, number>;
    sentiment_model: { name: string; version: string; type: string };
    keywords: Array<{ keyword: string; count: number }>;
    hashtags: Array<{ hashtag: string; count: number }>;
    sentiment_over_time: Array<{ date: string; sentiment: Sentiment; count: number }>;
  };
  topics: {
    topics: Topic[];
    method: string;
    message: string;
    quality_metric?: string;
  };
  trends: { trends: Trend[]; window_days: number };
  records: Post[];
  analysis_mode: string;
  source: { name: string; type: string; status: string; is_live: boolean };
  insights: Insight[];
  brand_comparison: BrandSummary[];
  generated_at: string;
}

export interface ForecastResponse {
  topic: string;
  history: Array<{ date: string; count: number }>;
  forecast: Array<{
    date: string;
    predicted_count: number;
    lower_bound: number | null;
    upper_bound: number | null;
  }>;
  holdout_predictions: Array<{ date: string; actual: number; predicted: number }>;
  model: string;
  evaluation: {
    holdout_periods: number;
    mae: number;
    rmse: number;
    models: Record<string, { mae: number; rmse: number }>;
    split: string;
  };
  interval_method: string;
  warning: string;
}

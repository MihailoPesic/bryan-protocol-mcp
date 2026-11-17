export interface StanceSource {
  title: string;
  url: string;
}

export interface Stance {
  id: string;
  topic: string;
  category: string;
  status: string;
  summary: string;
  dosage_or_rule: string;
  rationale: string;
  changed_at: string;
  sources: StanceSource[];
}

export interface DocMatch {
  doc_id: string;
  tier: number;
  source_type: string;
  title: string;
  url: string;
  channel_or_site: string;
  published_at: string;
  updated_at: string;
  duration_sec: number;
  excerpt: string;
}

export interface SegmentHit {
  doc_id: string;
  tier: number;
  source_type: string;
  title: string;
  channel: string;
  published_at: string;
  timestamp: string;
  start_sec: number;
  deep_link: string;
  text: string;
}

export interface QueryDossier {
  question: string;
  explicit_stances: Stance[];
  tier1_official_protocol: DocMatch[];
  tier2_official_articles_and_videos: {
    documents: DocMatch[];
    timestamped_quotes: SegmentHit[];
  };
  tier3_external_podcasts: SegmentHit[];
}

export interface OverviewResponse {
  document_counts: Array<{ tier: number; source_type: string; count: number }>;
  segment_count: number;
  stance_counts: Array<{ status: string; count: number }>;
  tier1_official_pages: Array<{ id: string; title: string; url: string; updated_at: string }>;
}

export interface SourceItem {
  id: string;
  tier: number;
  source_type: string;
  title: string;
  url: string;
  channel_or_site: string;
  published_at: string;
  updated_at: string;
  duration_sec: number;
}

export interface DocumentDetail {
  id: string;
  tier: number;
  source_type: string;
  title: string;
  url: string;
  channel_or_site: string;
  published_at: string;
  updated_at: string;
  duration_sec: number;
  content: string;
  truncated: boolean;
  total_chars: number;
}

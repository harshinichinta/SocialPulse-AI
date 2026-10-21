import { AnimatePresence, motion } from "framer-motion";
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, BarChart3,
  Brain, Building2, CalendarDays, Check, ChevronDown, ChevronLeft, ChevronRight,
  CircleHelp, Clock3, Database, Download, Filter,
  Gauge, GitBranch, Globe2, Hash, LayoutDashboard, LoaderCircle, Menu,
  MessageSquareText, Moon, Network, RefreshCw, Search, Settings2, ShieldCheck,
  Sparkles, Sun, Target, TrendingUp,
} from "lucide-react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend,
  Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ChangeEvent, FormEvent, ReactNode } from "react";
import type { BrandSummary, DashboardData, ForecastResponse, Insight, Post, Sentiment, Trend } from "./types";

const API = ((import.meta.env.VITE_API_URL as string | undefined) ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const palette = { positive: "#63d6ac", neutral: "#8b9bb4", negative: "#ff7b82" };

const navigation = [
  { group: "WORKSPACE", items: [
    { label: "Executive Overview", icon: LayoutDashboard },
    { label: "Live Intelligence", icon: Activity },
    { label: "Sentiment Analysis", icon: Gauge },
    { label: "Topic Discovery", icon: Network },
    { label: "Emerging Trends", icon: TrendingUp },
    { label: "Trend Forecasting", icon: BarChart3 },
  ] },
  { group: "INVESTIGATE", items: [
    { label: "Brand Intelligence", icon: Building2 },
    { label: "Conversation Explorer", icon: MessageSquareText },
    { label: "AI Insights", icon: Sparkles },
  ] },
  { group: "PLATFORM", items: [
    { label: "Big Data Pipeline", icon: GitBranch },
    { label: "Model Evaluation", icon: Brain },
    { label: "Data Sources", icon: Database },
    { label: "Settings & Project", icon: Settings2 },
  ] },
];
const shortDate = (value: string) => new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
const number = (value: number) => new Intl.NumberFormat().format(value);

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail.slice(0, 350) || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [sources, setSources] = useState<{ mode: string; scheduler_active: boolean; sources: Array<Record<string, unknown>> } | null>(null);
  const [active, setActive] = useState("Executive Overview");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [dark, setDark] = useState(true);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [range, setRange] = useState("30 days");
  const [searchText, setSearchText] = useState("");
  const [sentimentFilter, setSentimentFilter] = useState("All sentiment");
  const [brandFilter, setBrandFilter] = useState("All brands");
  const [platformFilter, setPlatformFilter] = useState("All sources");
  const [topicFilter, setTopicFilter] = useState("All topics");
  const [page, setPage] = useState(1);
  const sourceType = data?.source.type ?? "synthetic";

  const loadDemo = useCallback(async (showSpinner = true) => {
    if (showSpinner) setLoading(true);
    setError("");
    try {
      const [dashboard, sourceInfo] = await Promise.all([
        api<DashboardData>("/demo/dashboard"),
        api<typeof sources>("/demo/sources"),
      ]);
      setData(dashboard);
      setSources(sourceInfo);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not connect to the SocialPulse API.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { void loadDemo(); }, [loadDemo]);

  const refresh = () => {
    setRefreshing(true);
    void loadDemo(false);
  };

  const importDataset = useCallback(async (
    file: File,
    columns: { text: string; timestamp: string; platform: string; brand: string },
  ) => {
    const body = new FormData();
    body.append("file", file);
    for (const [key, value] of Object.entries(columns)) {
      if (value.trim()) body.append(`${key}_column`, value.trim());
    }
    const imported = await api<DashboardData>("/analyze/import", { method: "POST", body });
    setData(imported);
    setError("");
    setPage(1);
    setRange("All history");
    setBrandFilter("All brands");
    setPlatformFilter("All sources");
    setSentimentFilter("All sentiment");
    setTopicFilter("All topics");
    setSearchText("");
    return imported;
  }, []);

  const records = useMemo(() => data?.records ?? [], [data?.records]);
  const filteredRecords = useMemo(() => {
    const end = records.reduce<Date | null>((latest, post) => {
      if (!post.timestamp) return latest;
      const date = new Date(post.timestamp);
      return !latest || date > latest ? date : latest;
    }, null);
    return records.filter((post) => {
      if (!post.timestamp || !end) return range === "All history";
      if (range !== "All history") {
        const days = range === "7 days" ? 7 : 30;
        if (new Date(post.timestamp).getTime() < end.getTime() - days * 86_400_000) return false;
      }
      if (brandFilter !== "All brands" && post.brand !== brandFilter) return false;
      if (platformFilter !== "All sources" && post.platform !== platformFilter) return false;
      if (sentimentFilter !== "All sentiment" && post.sentiment !== sentimentFilter.toLowerCase()) return false;
      if (topicFilter !== "All topics" && !post.text.toLowerCase().includes(topicFilter.toLowerCase())) return false;
      if (searchText && !post.text.toLowerCase().includes(searchText.toLowerCase())) return false;
      return true;
    });
  }, [records, range, brandFilter, platformFilter, sentimentFilter, topicFilter, searchText]);

  const counts = useMemo(() => filteredRecords.reduce<Record<Sentiment, number>>((result, post) => {
    result[post.sentiment] += 1;
    return result;
  }, { positive: 0, neutral: 0, negative: 0 }), [filteredRecords]);
  const selectedTotal = filteredRecords.length;
  const sentimentPercent = (sentiment: Sentiment) => selectedTotal ? counts[sentiment] / selectedTotal * 100 : 0;

  const volumeSeries = useMemo(() => {
    const grouped = new Map<string, number>();
    for (const post of filteredRecords) {
      if (post.timestamp) {
        const date = post.timestamp.slice(0, 10);
        grouped.set(date, (grouped.get(date) ?? 0) + 1);
      }
    }
    return [...grouped].sort(([a], [b]) => a.localeCompare(b))
      .map(([date, count]) => ({ date, label: shortDate(date), count }));
  }, [filteredRecords]);

  const sentimentSeries = useMemo(() => {
    const grouped = new Map<string, { positive: number; neutral: number; negative: number }>();
    for (const post of filteredRecords) {
      if (!post.timestamp) continue;
      const date = post.timestamp.slice(0, 10);
      const row = grouped.get(date) ?? { positive: 0, neutral: 0, negative: 0 };
      row[post.sentiment] += 1;
      grouped.set(date, row);
    }
    return [...grouped].sort(([a], [b]) => a.localeCompare(b))
      .map(([date, values]) => ({ date, label: shortDate(date), ...values }));
  }, [filteredRecords]);

  const topics = data?.topics.topics ?? [];
  const topicChart = topics.slice(0, 7).map((topic) => ({
    label: topic.label.split(",")[0], mentions: topic.mentions,
  }));
  const trendItems = data?.trends.trends ?? [];
  const brands = data?.brand_comparison ?? [];

  const downloadReport = () => {
    if (!data) return;
    const blob = new Blob([JSON.stringify({
      project: "SocialPulse AI",
      source: data.source,
      generated_at: data.generated_at,
      filtered_record_count: selectedTotal,
      filters: { range, brandFilter, platformFilter, sentimentFilter, topicFilter },
      sentiment: counts,
      trends: trendItems,
      insights: data.insights,
      analysis_mode: data.analysis_mode,
    }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "socialpulse-demo-report.json";
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className={`app-shell ${dark ? "theme-dark" : "theme-light"}`}>
      <aside className={`sidebar ${collapsed ? "sidebar-collapsed" : ""} ${mobileMenu ? "sidebar-mobile-open" : ""}`}>
        <div className="brand-lockup">
          <div className="brand-mark"><Activity size={19} strokeWidth={2.6} /></div>
          {!collapsed && <div className="brand-name">socialpulse<span>AI</span><small>INTELLIGENCE PLATFORM</small></div>}
          <button className="icon-button sidebar-collapse" aria-label="Collapse sidebar" onClick={() => setCollapsed(!collapsed)}>
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>
        <div className="workspace-picker">
          <div className="workspace-avatar">S</div>
          {!collapsed && <div className="workspace-name">SocialPulse Lab<small>Academic workspace</small></div>}
        </div>
        <nav className="side-nav" aria-label="Main navigation">
          {navigation.map((group) => (
            <section className="nav-group" key={group.group}>
              {!collapsed && <div className="nav-label">{group.group}</div>}
              {group.items.map(({ label, icon: Icon }) => (
                <button key={label} title={collapsed ? label : undefined}
                  aria-label={label}
                  className={`nav-item ${active === label ? "nav-item-active" : ""}`}
                  onClick={() => { setActive(label); setMobileMenu(false); }}>
                  <Icon size={17} strokeWidth={1.8} />
                  {!collapsed && <span>{label}</span>}
                  {!collapsed && label === "AI Insights" && data?.insights.length ? <span className="nav-count">{data.insights.length}</span> : null}
                </button>
              ))}
            </section>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="cluster-status"><span className="status-dot status-local" />{!collapsed && <><div><b>LOCAL PROCESSING</b><small>Pandas · scikit-learn</small></div><CircleHelp size={14} /></>}</div>
          <button className="profile-row" onClick={() => setActive("Settings & Project")}>
            <div className="profile-avatar">SP</div>{!collapsed && <div className="profile-name">Student Project<small>Local workspace</small></div>}
          </button>
        </div>
      </aside>

      {mobileMenu && <button className="mobile-overlay" aria-label="Close navigation" onClick={() => setMobileMenu(false)} />}
      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu-button" aria-label="Open navigation" onClick={() => setMobileMenu(true)}><Menu size={19} /></button>
            <div className="breadcrumbs"><span>SocialPulse</span><ChevronRight size={13} /><b>{active}</b></div>
          </div>
          <div className="topbar-actions">
            <div className={`source-mode source-mode-${sourceType}`}>
              <span className={`status-dot status-${sourceType}`} />DATA · {sourceType === "synthetic" ? "DEMO" : sourceType.toUpperCase()}
            </div>
            <span className="topbar-divider" />
            <button className="icon-button" aria-label="Toggle theme" onClick={() => setDark(!dark)}>{dark ? <Sun size={17} /> : <Moon size={17} />}</button>
            <div className="topbar-avatar">SP</div>
          </div>
        </header>
        <div className="page-wrap">
          {error && <div className="error-banner"><AlertTriangle size={17} /><div><b>Could not load dashboard data</b><span>{error}</span></div><button className="button button-secondary" onClick={() => void loadDemo()}>Retry</button></div>}
          {loading && !data ? <LoadingState /> : data ? (
            <AnimatePresence mode="wait">
              <motion.div key={active} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.16 }}>
                <PageHeader page={active} data={data} range={range} setRange={setRange}
                  brandFilter={brandFilter} setBrandFilter={setBrandFilter}
                  topicFilter={topicFilter} setTopicFilter={setTopicFilter}
                  refreshing={refreshing} onRefresh={refresh} onExport={downloadReport}
                  isOverview={active === "Executive Overview"} />
                <PageContent
                  active={active} data={data} sources={sources} records={filteredRecords}
                  counts={counts} percent={sentimentPercent} volume={volumeSeries}
                  sentimentTimeline={sentimentSeries} topicChart={topicChart} topics={topics}
                  trends={trendItems} brands={brands} reload={refresh}
                  searchText={searchText} setSearchText={setSearchText}
                  sentimentFilter={sentimentFilter} setSentimentFilter={setSentimentFilter}
                  brandFilter={brandFilter} setBrandFilter={setBrandFilter}
                  platformFilter={platformFilter} setPlatformFilter={setPlatformFilter}
                  topicFilter={topicFilter} setTopicFilter={setTopicFilter}
                  page={page} setPage={setPage} onImport={importDataset} />
              </motion.div>
            </AnimatePresence>
          ) : <EmptyState onRetry={() => void loadDemo()} />}
          <footer className="page-footer">
            <span><ShieldCheck size={13} /> Local processing · no personal identifiers stored</span>
            <span>SocialPulse AI <i>v1.0.0</i></span>
          </footer>
        </div>
      </main>
    </div>
  );
}

function PageHeader({ page, data, range, setRange, brandFilter, setBrandFilter, topicFilter, setTopicFilter, refreshing, onRefresh, onExport, isOverview }: {
  page: string; data: DashboardData; range: string; setRange: (range: string) => void;
  brandFilter: string; setBrandFilter: (value: string) => void;
  topicFilter: string; setTopicFilter: (value: string) => void;
  refreshing: boolean; onRefresh: () => void; onExport: () => void; isOverview: boolean;
}) {
  const descriptions: Record<string, string> = {
    "Executive Overview": "A clear view of what people are discussing and how those conversations are changing.",
    "Live Intelligence": "Review the most recent records in the selected dataset.",
    "Sentiment Analysis": "Explore baseline sentiment labels and their distribution across the selected data.",
    "Topic Discovery": "Recurring language and automatically suggested themes from the current dataset.",
    "Emerging Trends": "Topics with rising mention volume, surfaced with comparison-window evidence.",
    "Trend Forecasting": "Compare a daily-count model with a simple forecast baseline.",
    "Brand Intelligence": "Compare records using the supplied brand field.",
    "Conversation Explorer": "Search, filter, and inspect individual conversation records.",
    "AI Insights": "Evidence-linked observations and review suggestions calculated from this dataset.",
    "Big Data Pipeline": "Understand the distinction between local analytics and a genuine Hadoop cluster.",
    "Model Evaluation": "Evaluate the sentiment baseline only when you provide labeled reference data.",
    "Data Sources": "Inspect configured sources and their verified connection state.",
    "Settings & Project": "Project configuration, methods, and important interpretation guidance.",
  };
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow"><span className="eyebrow-line" />SOCIAL LISTENING · {page === "Executive Overview" ? "OVERVIEW" : "ANALYTICS"}</div>
        <div className="heading-row"><div><h1>{page}</h1><p>{descriptions[page]}</p></div></div>
        <div className="heading-meta">
          <span><Clock3 size={13} /> Refreshed {new Date(data.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
        </div>
      </div>
      <div className="heading-actions">
        {isOverview && <>
          <label className="select-wrap"><CalendarDays size={15} /><select value={range} onChange={(event) => setRange(event.target.value)} aria-label="Time range">
            <option>7 days</option><option>30 days</option><option>All history</option>
          </select><ChevronDown size={13} /></label>
          <label className="select-wrap overview-filter"><Building2 size={14} /><select value={brandFilter} onChange={(event) => setBrandFilter(event.target.value)} aria-label="Brand filter">
            <option>All brands</option>{data.brand_comparison.map((brand) => <option key={brand.brand}>{brand.brand}</option>)}
          </select><ChevronDown size={13} /></label>
          <label className="select-wrap overview-filter"><Hash size={14} /><select value={topicFilter} onChange={(event) => setTopicFilter(event.target.value)} aria-label="Topic filter">
            <option>All topics</option>{data.topics.topics.map((topic) => <option key={topic.topic_id}>{topic.terms[0]}</option>)}
          </select><ChevronDown size={13} /></label>
        </>}
        {data.source.type === "synthetic" && <button className="button button-secondary" onClick={onRefresh} disabled={refreshing}>
          <RefreshCw size={15} className={refreshing ? "spin" : ""} /> <span>{refreshing ? "Refreshing" : "Regenerate demo"}</span>
        </button>}
        {isOverview && <button className="button button-primary" onClick={onExport}><Download size={15} /><span>Export report</span></button>}
      </div>
    </div>
  );
}

function PageContent(props: {
  active: string; data: DashboardData; sources: { mode: string; scheduler_active: boolean; sources: Array<Record<string, unknown>> } | null;
  records: Post[]; counts: Record<Sentiment, number>; percent: (sentiment: Sentiment) => number;
  volume: Array<{ date: string; label: string; count: number }>;
  sentimentTimeline: Array<{ date: string; label: string; positive: number; neutral: number; negative: number }>;
  topicChart: Array<{ label: string; mentions: number }>; topics: DashboardData["topics"]["topics"];
  trends: DashboardData["trends"]["trends"]; brands: BrandSummary[]; reload: () => void;
  searchText: string; setSearchText: (value: string) => void;
  sentimentFilter: string; setSentimentFilter: (value: string) => void;
  brandFilter: string; setBrandFilter: (value: string) => void;
  platformFilter: string; setPlatformFilter: (value: string) => void;
  page: number; setPage: (value: number) => void;
  topicFilter: string; setTopicFilter: (value: string) => void;
  onImport: (file: File, columns: { text: string; timestamp: string; platform: string; brand: string }) => Promise<DashboardData>;
}) {
  const { active, data } = props;
  switch (active) {
    case "Executive Overview": return <Overview {...props} />;
    case "Live Intelligence": return <LivePage {...props} />;
    case "Sentiment Analysis": return <SentimentPage {...props} />;
    case "Topic Discovery": return <TopicsPage {...props} />;
    case "Emerging Trends": return <TrendsPage trends={props.trends} records={props.records} />;
    case "Trend Forecasting": return <ForecastPage records={props.records} data={data} />;
    case "Brand Intelligence": return <BrandPage brands={props.brands} records={props.records} topics={props.data.topics.topics} />;
    case "Conversation Explorer": return <ExplorerPage {...props} />;
    case "AI Insights": return <InsightsPage records={props.records} />;
    case "Big Data Pipeline": return <BigDataPage sources={props.sources} records={data.records} />;
    case "Model Evaluation": return <EvaluationPage />;
    case "Data Sources": return <SourcesPage sources={props.sources} data={data} onRefresh={props.reload} onImport={props.onImport} />;
    case "Settings & Project": return <SettingsPage data={data} />;
    default: return <Overview {...props} />;
  }
}

function useCurrentTrends(records: Post[], windowDays: number, minMentions: number, fallback: Trend[]) {
  const [trends, setTrends] = useState<Trend[]>(fallback);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    let active = true;
    if (!records.length) {
      setTrends([]);
      setError("");
      setLoading(false);
      return () => { active = false; };
    }
    setLoading(true);
    void api<{ trends: Trend[] }>("/analyze/trends", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        records: records.map(({ text, timestamp, sentiment }) => ({ text, timestamp, sentiment })),
        window_days: windowDays,
        min_mentions: minMentions,
      }),
    }).then((result) => {
      if (active) { setTrends(result.trends); setError(""); }
    }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : "Trend analysis failed.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [records, windowDays, minMentions]);
  return { trends, error, loading };
}

function Overview(props: Parameters<typeof PageContent>[0]) {
  const { data, records, counts, percent, volume, sentimentTimeline, topicChart } = props;
  const { trends } = useCurrentTrends(records, 7, 2, props.trends);
  const brands = data.brand_comparison;
  const topics = data.topics.topics;
  const insightCount = data.insights.length;
  const periodRows = sentimentTimeline;
  let sentimentShiftCount = 0;
  if (periodRows.length >= 14) {
    const current = periodRows.slice(-7).reduce((sum, day) => sum + day.negative, 0);
    const previous = periodRows.slice(-14, -7).reduce((sum, day) => sum + day.negative, 0);
    const currentN = periodRows.slice(-7).reduce((sum, day) => sum + day.positive + day.neutral + day.negative, 0);
    const previousN = periodRows.slice(-14, -7).reduce((sum, day) => sum + day.positive + day.neutral + day.negative, 0);
    if (currentN >= 8 && previousN >= 8 && Math.abs(current / currentN - previous / previousN) >= 0.08) sentimentShiftCount = 1;
  }

  const pieData = (["positive", "neutral", "negative"] as Sentiment[]).map((name) => ({
    name: name[0].toUpperCase() + name.slice(1), value: counts[name], fill: palette[name],
  }));
  return <>
    <div className="kpi-grid overview-kpis">
      <MetricCard label="Posts analyzed" value={number(records.length)} icon={<MessageSquareText size={17} />} detail="In selected period" accent="blue" />
      <MetricCard label="Positive sentiment" value={`${percent("positive").toFixed(1)}%`} icon={<ArrowUpRight size={17} />} detail={`${number(counts.positive)} classified posts`} accent="green" />
      <MetricCard label="Neutral sentiment" value={`${percent("neutral").toFixed(1)}%`} icon={<Activity size={17} />} detail={`${number(counts.neutral)} classified posts`} accent="blue" />
      <MetricCard label="Negative sentiment" value={`${percent("negative").toFixed(1)}%`} icon={<ArrowDownRight size={17} />} detail={`${number(counts.negative)} classified posts`} accent="red" />
      <MetricCard label="Growing keywords" value={number(trends.length)} icon={<TrendingUp size={17} />} detail="Full sample · growth only" accent="violet" />
      <MetricCard label="Sentiment shifts" value={number(sentimentShiftCount)} icon={<Activity size={17} />} detail="Meets sample threshold" accent="violet" />
    </div>
    <div className="dashboard-grid dashboard-grid-main">
      <Panel title="Conversation volume" subtitle="Daily post count · observed records" action={<span className="chart-legend"><i className="legend-dot legend-blue" />Mentions</span>} className="volume-panel">
        <div className="chart-large">
          {volume.length ? <ResponsiveContainer width="100%" height="100%"><AreaChart data={volume} margin={{ top: 12, right: 10, left: -18, bottom: 0 }}>
            <defs><linearGradient id="volumeGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#6d82ff" stopOpacity={0.27} /><stop offset="100%" stopColor="#6d82ff" stopOpacity={0.01} /></linearGradient></defs>
            <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 11 }} minTickGap={24} />
            <YAxis tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 11 }} />
            <Tooltip content={<ChartTooltip />} />
            <Area type="monotone" dataKey="count" name="Posts" stroke="#8494ff" strokeWidth={2.2} fill="url(#volumeGradient)" activeDot={{ r: 4, fill: "#8494ff" }} />
          </AreaChart></ResponsiveContainer> : <ChartEmpty />}
        </div>
        <div className="chart-footnote"><span><i className="dot-observed" />Historical observations</span><span>{volume.length} dated days</span></div>
      </Panel>
      <Panel title="Sentiment mix" subtitle="Classification of selected posts" className="sentiment-panel">
        <div className="sentiment-donut">
          <ResponsiveContainer width="100%" height="100%"><PieChart>
            <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={68} outerRadius={91} paddingAngle={3} stroke="none">
              {pieData.map((entry) => <Cell key={entry.name} fill={entry.fill} />)}
            </Pie><Tooltip content={<ChartTooltip />} />
          </PieChart></ResponsiveContainer>
          <div className="donut-center"><b>{number(records.length)}</b><span>posts</span></div>
        </div>
        <div className="sentiment-legend">
          {(["positive", "neutral", "negative"] as Sentiment[]).map((sentiment) => (
            <div className="sentiment-legend-row" key={sentiment}><span><i style={{ background: palette[sentiment] }} />{sentiment}</span><b>{percent(sentiment).toFixed(1)}% <small>{number(counts[sentiment])}</small></b></div>
          ))}
        </div>
      </Panel>
    </div>
    <div className="dashboard-grid dashboard-grid-lower">
      <Panel title="Sentiment over time" subtitle="Daily classified volume" className="timeline-panel">
        <div className="chart-medium"><ResponsiveContainer width="100%" height="100%"><AreaChart data={sentimentTimeline} margin={{ top: 12, right: 4, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="var(--grid)" />
          <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 10 }} minTickGap={24} />
          <YAxis tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 10 }} />
          <Tooltip content={<ChartTooltip />} /><Legend iconType="circle" wrapperStyle={{ fontSize: 11, paddingTop: 10 }} />
          <Area type="monotone" dataKey="positive" name="Positive" stackId="1" stroke={palette.positive} fill={palette.positive} fillOpacity={0.45} />
          <Area type="monotone" dataKey="neutral" name="Neutral" stackId="1" stroke={palette.neutral} fill={palette.neutral} fillOpacity={0.25} />
          <Area type="monotone" dataKey="negative" name="Negative" stackId="1" stroke={palette.negative} fill={palette.negative} fillOpacity={0.38} />
        </AreaChart></ResponsiveContainer></div>
      </Panel>
      <Panel title="Topics drawing attention" subtitle="Suggested labels · human review recommended" action={<span className="signal-count">Frequency</span>} className="topics-panel">
        {topicChart.length ? <div className="chart-medium"><ResponsiveContainer width="100%" height="100%"><BarChart data={topicChart} layout="vertical" margin={{ top: 3, right: 12, left: 14, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 5" horizontal={false} stroke="var(--grid)" />
          <XAxis type="number" hide /><YAxis type="category" dataKey="label" width={92} tickLine={false} axisLine={false} tick={{ fill: "var(--text-secondary)", fontSize: 11 }} />
          <Tooltip content={<ChartTooltip />} /><Bar dataKey="mentions" name="Posts" fill="#8190ff" radius={[0, 4, 4, 0]} barSize={12} />
        </BarChart></ResponsiveContainer></div> : <ChartEmpty />}
      </Panel>
    </div>
    <div className="dashboard-grid dashboard-grid-bottom">
      <Panel title="Emerging signals" subtitle="Flags are based on observed volume changes" action={<span className="signal-count">{trends.length} signals</span>} className="signals-panel">
        {trends.slice(0, 3).map((trend) => <TrendRow key={trend.topic} trend={trend} />)}
        {!trends.length && <InlineEmpty text="No topics met the current trend thresholds." />}
      </Panel>
      <Panel title="Intelligence brief" subtitle="Evidence-linked observations" className="brief-panel">
        <div className="brief-callout"><div className="brief-icon"><Sparkles size={16} /></div><div><b>{insightCount ? `${insightCount} evidence-linked observations` : "No qualifying findings"}</b><p>{insightCount ? data.insights[0].evidence : "The selected data did not meet the configured insight thresholds."}</p></div></div>
        <div className="brief-metrics"><div><span>Sentiment shifts</span><b>{sentimentShiftCount}</b></div><div><span>Brands in sample</span><b>{brands.length}</b></div><div><span>Topic suggestions</span><b>{topics.length}</b></div></div>
      </Panel>
    </div>
  </>;
}

function MetricCard({ label, value, icon, detail, accent }: { label: string; value: string; icon: ReactNode; detail: string; accent: string }) {
  return <div className="metric-card"><div className={`metric-icon metric-${accent}`}>{icon}</div><div className="metric-label">{label}</div><div className="metric-value">{value}</div><div className="metric-detail">{detail}</div></div>;
}

function Panel({ title, subtitle, action, children, className = "" }: { title: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`panel ${className}`}><div className="panel-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>{children}</section>;
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ name: string; value: number; color?: string; fill?: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><b>{label}</b>{payload.map((entry) => <span key={entry.name}><i style={{ background: entry.color ?? entry.fill }} />{entry.name}<strong>{number(entry.value)}</strong></span>)}</div>;
}

function ChartEmpty() { return <div className="chart-empty"><BarChart3 size={19} /><span>Not enough dated records to chart</span></div>; }
function InlineEmpty({ text }: { text: string }) { return <div className="inline-empty">{text}</div>; }
function TrendRow({ trend }: { trend: DashboardData["trends"]["trends"][number] }) {
  return <div className="trend-row"><div className="trend-icon"><TrendingUp size={16} /></div><div className="trend-copy"><b>{trend.topic}</b><span>{trend.reason}</span></div><div className="trend-growth">{trend.growth_percent === null ? <span className="growth-muted">—</span> : <><ArrowUpRight size={14} />{trend.growth_percent}%</>}<small>{trend.current_mentions} mentions</small></div></div>;
}

function LivePage({ records, data }: Parameters<typeof PageContent>[0]) {
  const latest = [...records].sort((a, b) => (b.timestamp ?? "").localeCompare(a.timestamp ?? "")).slice(0, 15);
  return <>
    <div className="live-status-grid"><MetricCard label="Records in dataset" value={number(records.length)} icon={<Database size={17} />} detail="Current filters applied" accent="blue" /><MetricCard label="Data source" value={data.source.type === "synthetic" ? "Demo" : "Imported"} icon={<Check size={17} />} detail={data.source.name} accent="green" /><MetricCard label="Automated refresh" value="Off" icon={<Clock3 size={17} />} detail="Manual refresh only" accent="violet" /></div>
    <Panel title="Recent records" subtitle="Author identifiers are not collected">
      <PostTable records={latest} />
    </Panel>
  </>;
}

function SentimentPage({ counts, percent, sentimentTimeline, records }: Parameters<typeof PageContent>[0]) {
  const [selected, setSelected] = useState<Sentiment | "all">("all");
  const matches = records.filter((record) => selected === "all" || record.sentiment === selected).slice(0, 6);
  return <>
    <div className="kpi-grid sentiment-kpis">{(["positive", "neutral", "negative"] as Sentiment[]).map((sentiment) => <MetricCard key={sentiment} label={`${sentiment[0].toUpperCase()}${sentiment.slice(1)} posts`} value={`${percent(sentiment).toFixed(1)}%`} icon={sentiment === "positive" ? <ArrowUpRight size={17} /> : sentiment === "negative" ? <ArrowDownRight size={17} /> : <Activity size={17} />} detail={`${number(counts[sentiment])} examples`} accent={sentiment === "positive" ? "green" : sentiment === "negative" ? "red" : "blue"} />)}</div>
    <div className="dashboard-grid dashboard-grid-main"><Panel title="Sentiment over time" subtitle="Daily post counts · observed demo records" className="wide-panel"><div className="chart-large"><ResponsiveContainer width="100%" height="100%"><LineChart data={sentimentTimeline} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}><CartesianGrid strokeDasharray="3 5" vertical={false} stroke="var(--grid)" /><XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 11 }} minTickGap={24} /><YAxis tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 11 }} /><Tooltip content={<ChartTooltip />} /><Legend /><Line type="monotone" dataKey="positive" name="Positive" stroke={palette.positive} strokeWidth={2} dot={false} /><Line type="monotone" dataKey="neutral" name="Neutral" stroke={palette.neutral} strokeWidth={2} dot={false} /><Line type="monotone" dataKey="negative" name="Negative" stroke={palette.negative} strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer></div></Panel><Panel title="Label distribution" subtitle="Rule-based baseline"><div className="sentiment-detail-list">{(["positive", "neutral", "negative"] as Sentiment[]).map((sentiment) => <div className="sentiment-detail" key={sentiment}><span><i style={{ background: palette[sentiment] }} />{sentiment}</span><b>{number(counts[sentiment])}</b><em>{percent(sentiment).toFixed(1)}%</em></div>)}</div><p className="note-copy">Scores are matched-word evidence from a small English lexicon. They are not calibrated probabilities and may misclassify sarcasm, slang, and other languages.</p></Panel></div>
    <Panel title="Representative posts" subtitle="Examples from current filtered records" action={<label className="select-wrap compact-select"><Filter size={13} /><select value={selected} onChange={(event) => setSelected(event.target.value as Sentiment | "all")}><option value="all">All sentiment</option><option value="positive">Positive</option><option value="neutral">Neutral</option><option value="negative">Negative</option></select><ChevronDown size={12} /></label>}><PostTable records={matches} showConfidence /></Panel>
  </>;
}

function TopicsPage({ data, records }: Parameters<typeof PageContent>[0]) {
  const [chosenTopic, setChosenTopic] = useState<string | null>(null);
  const [topicData, setTopicData] = useState(data.topics);
  const [topicError, setTopicError] = useState("");
  const [topicLoading, setTopicLoading] = useState(false);
  useEffect(() => {
    let active = true;
    if (!records.length) {
      setTopicData({ topics: [], method: "TF-IDF + NMF", message: "No records match the selected filters." });
      setTopicLoading(false);
      return () => { active = false; };
    }
    setTopicLoading(true);
    void api<DashboardData["topics"]>("/analyze/topics", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        texts: records.map((post) => post.text),
        sentiments: records.map((post) => post.sentiment),
      }),
    }).then((result) => {
      if (active) { setTopicData(result); setTopicError(""); }
    }).catch((reason: unknown) => {
      if (active) setTopicError(reason instanceof Error ? reason.message : "Topic analysis failed.");
    }).finally(() => { if (active) setTopicLoading(false); });
    return () => { active = false; };
  }, [records]);
  const topics = topicData.topics;
  const topic = topics.find((item) => item.label === chosenTopic) ?? topics[0];
  const wordCounts = new Map<string, number>();
  for (const record of records) {
    for (const word of record.processed_text.split(/\s+/)) {
      if (word.length > 2) wordCounts.set(word, (wordCounts.get(word) ?? 0) + 1);
    }
  }
  const words = [...wordCounts].sort((a, b) => b[1] - a[1])
    .slice(0, 12).map(([keyword, count]) => ({ keyword, count }));
  return <>
    {topicError && <div className="inline-error">{topicError}</div>}
    <div className="dashboard-grid dashboard-grid-main">
      <Panel title="Suggested topics" subtitle={`${topicData.method} · generated labels require review`} className="wide-panel">
        {topicLoading ? <InlineEmpty text="Calculating topics from the selected records…" /> : <div className="topic-list">{topics.map((item, index) => <button className={`topic-card ${topic?.label === item.label ? "topic-card-selected" : ""}`} key={item.topic_id} onClick={() => setChosenTopic(item.label)}><span className="topic-rank">{String(index + 1).padStart(2, "0")}</span><span className="topic-info"><b>{item.label}</b><small>{item.terms.slice(0, 5).join(" · ")}</small></span><span className="topic-count">{item.mentions}<small>posts</small></span><ChevronRight size={15} /></button>)}</div>}
      </Panel>
      <Panel title="Frequently used terms" subtitle="Token frequency in analyzed text"><div className="keyword-cloud">{words.map((word, index) => <span key={word.keyword} className={`keyword-chip keyword-${index % 4}`}><Hash size={12} />{word.keyword}<b>{word.count}</b></span>)}</div><p className="note-copy">Word counts show association, not causation or a validated topic ontology.</p></Panel>
    </div>
    {topic && <Panel title={`Topic evidence · ${topic.label}`} subtitle={`${topic.mentions} assigned posts · NMF top-term coherence ${topic.coherence === null ? "not available" : topic.coherence}`}>
      <div className="sentiment-detail-list">{(["positive", "neutral", "negative"] as Sentiment[]).map((sentiment) => <div className="sentiment-detail" key={sentiment}><span><i style={{ background: palette[sentiment] }} />{sentiment}</span><b>{number(topic.sentiment_distribution[sentiment] ?? 0)}</b></div>)}</div>
      <div className="evidence-tags">{topic.terms.map((term) => <span key={term}>{term}</span>)}</div>
      <h3 className="subsection-heading">Representative assigned posts</h3>
      {topic.representative_posts.map((post, index) => <blockquote className="evidence-quote" key={`${post}-${index}`}>{post}</blockquote>)}
      <p className="note-copy">{topicData.quality_metric ?? topicData.message}</p>
    </Panel>}
  </>;
}

function TrendsPage({ trends: fallback, records }: { trends: DashboardData["trends"]["trends"]; records: Post[] }) {
  const [windowDays, setWindowDays] = useState(7);
  const [minMentions, setMinMentions] = useState(2);
  const { trends, error, loading } = useCurrentTrends(records, windowDays, minMentions, fallback);
  const [selected, setSelected] = useState<string | null>(null);
  const active = trends.find((trend) => trend.topic === selected) ?? trends[0];
  return <>
    {error && <div className="inline-error">{error}</div>}
    <div className="dashboard-grid trends-layout"><Panel title={`Ranked signals · ${trends.length}`} subtitle="Rank: log(1 + current posts) × change / max(previous posts, 1)" className="trend-list-panel">
      <div className="trend-controls"><label>Window<select value={windowDays} onChange={(event) => setWindowDays(Number(event.target.value))}><option value={7}>7 days</option><option value={14}>14 days</option><option value={30}>30 days</option></select></label><label>Minimum posts<input type="number" min={1} max={100000} value={minMentions} onChange={(event) => setMinMentions(Math.max(1, Number(event.target.value) || 1))} /></label></div>
      {loading ? <InlineEmpty text="Recalculating counts for the selected windows…" /> : trends.map((trend) => <button key={trend.topic} className={`trend-select-row ${active?.topic === trend.topic ? "trend-select-active" : ""}`} onClick={() => setSelected(trend.topic)}><div className="trend-select-topic"><span className="trend-dot" /><b>{trend.topic}</b></div><span>{trend.current_mentions} ({trend.previous_mentions})</span><strong className={trend.growth_percent === null ? "growth-muted" : "trend-rate"}>{trend.growth_percent === null ? `+${trend.absolute_change}` : `+${trend.growth_percent}%`}</strong><ChevronRight size={14} /></button>)}
    </Panel>
      <Panel title={active ? `Evidence · ${active.topic}` : "No qualifying trend"} subtitle={active ? `${active.window_days}-day windows · ${active.period_start} to ${active.period_end}` : "Trend evidence"}>{active ? <div className="evidence-content"><div className="evidence-stat-grid"><div><span>Current window</span><b>{active.current_mentions}</b><small>posts</small></div><div><span>Previous window</span><b>{active.previous_mentions}</b><small>posts</small></div><div><span>Absolute change</span><b>{active.absolute_change > 0 ? "+" : ""}{active.absolute_change}</b><small>{active.growth_percent === null ? "percentage withheld: low baseline" : `${active.growth_percent}% window over window`}</small></div></div><div className="evidence-reason"><Sparkles size={16} /><span>Rank score {active.rank_score}. {active.reason}</span></div><div className="evidence-tags">{active.keywords.map((word) => <span key={word}>#{word}</span>)}</div><div className="sentiment-detail-list">{Object.entries(active.sentiment_distribution).map(([label, count]) => <div className="sentiment-detail" key={label}><span><i style={{ background: palette[label as Sentiment] }} />{label}</span><b>{count}</b></div>)}</div><h3 className="subsection-heading">Evidence posts from current window</h3>{active.representative_posts.map((post, index) => <blockquote className="evidence-quote" key={index}>{post}</blockquote>)}<details className="methodology-note"><summary>Trend interpretation</summary><p>{active.limitation} The score ranks volume change and current volume; it is not a significance test and does not establish persistence.</p></details></div> : <InlineEmpty text="No topics passed the selected volume threshold." />}</Panel>
    </div>
  </>;
}

function ForecastPage({ records, data }: { records: Post[]; data: DashboardData }) {
  const topics = useMemo(() => [...new Set(data.topics.topics.flatMap((item) => item.terms))].slice(0, 50), [data.topics.topics]);
  const [topic, setTopic] = useState("");
  const selectedTopic = topics.includes(topic) ? topic : topics[0] ?? "";
  const [horizon, setHorizon] = useState(7);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const buildForecast = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(""); setForecast(null);
    const daily = new Map<string, number>();
    for (const record of records) {
      if (record.timestamp && record.text.toLowerCase().includes(selectedTopic.toLowerCase())) {
        const date = record.timestamp.slice(0, 10);
        daily.set(date, (daily.get(date) ?? 0) + 1);
      }
    }
    try {
      const result = await api<ForecastResponse>("/forecast", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: selectedTopic, points: [...daily].map(([date, count]) => ({ date, count })), horizon }),
      });
      setForecast(result);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not create forecast."); }
    finally { setBusy(false); }
  };
  const chart = forecast ? [
    ...forecast.history.map((point) => ({
      date: shortDate(point.date),
      observed: point.count,
      heldout_prediction: forecast.holdout_predictions.find((test) => test.date === point.date)?.predicted,
    })),
    ...forecast.forecast.map((point) => ({
      date: shortDate(point.date),
      future_prediction: point.predicted_count,
      lower_bound: point.lower_bound,
      upper_bound: point.upper_bound,
    })),
  ] : [];
  return <>
    <Panel title="Forecast configuration" subtitle="Generate an estimate from daily topic counts"><form className="forecast-form" onSubmit={(event) => void buildForecast(event)}><label>Topic or keyword<select value={selectedTopic} onChange={(event) => setTopic(event.target.value)}>{topics.map((word) => <option key={word}>{word}</option>)}</select></label><label>Forecast horizon<select value={horizon} onChange={(event) => setHorizon(Number(event.target.value))}>{[3, 7, 14, 30].map((days) => <option key={days} value={days}>{days} days</option>)}</select></label><button className="button button-primary" type="submit" disabled={busy || !topics.length}>{busy ? <LoaderCircle size={15} className="spin" /> : <TrendingUp size={15} />}{busy ? "Calculating" : "Generate forecast"}</button></form>{error && <div className="inline-error">{error}</div>}</Panel>
    {forecast && <>
      <div className="kpi-grid forecast-kpis">
        <MetricCard label="Selected model MAE" value={forecast.evaluation.mae.toFixed(2)} icon={<Target size={17} />} detail={`${forecast.evaluation.holdout_periods} chronological test days`} accent="blue" />
        <MetricCard label="Selected model RMSE" value={forecast.evaluation.rmse.toFixed(2)} icon={<BarChart3 size={17} />} detail={forecast.model} accent="violet" />
        <MetricCard label="Forecast horizon" value={String(forecast.forecast.length)} icon={<CalendarDays size={17} />} detail="Daily estimates" accent="green" />
      </div>
      <Panel title={`Holdout and future estimates · ${forecast.topic}`} subtitle={`${forecast.model}; baseline and Holt models were scored on held-out days`}>
        <div className="chart-large forecast-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={chart} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}><CartesianGrid strokeDasharray="3 5" vertical={false} stroke="var(--grid)" /><XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 11 }} minTickGap={20} /><YAxis tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 11 }} /><Tooltip content={<ChartTooltip />} /><Legend /><Line type="monotone" dataKey="observed" name="Actual" stroke="#8290ff" strokeWidth={2} dot={{ r: 2 }} connectNulls={false} /><Line type="monotone" dataKey="heldout_prediction" name="Held-out prediction" stroke={palette.negative} strokeWidth={2} dot={{ r: 2 }} connectNulls={false} /><Line type="monotone" dataKey="future_prediction" name="Future forecast" stroke={palette.positive} strokeWidth={2} dot={{ r: 2 }} connectNulls={false} /><Line type="monotone" dataKey="lower_bound" name="Empirical lower band" stroke={palette.positive} strokeWidth={1} strokeDasharray="4 4" dot={false} connectNulls={false} /><Line type="monotone" dataKey="upper_bound" name="Empirical upper band" stroke={palette.positive} strokeWidth={1} strokeDasharray="4 4" dot={false} connectNulls={false} /></ComposedChart></ResponsiveContainer></div>
        <div className="model-comparison">{Object.entries(forecast.evaluation.models).map(([model, scores]) => <div key={model}><b>{model.replaceAll("_", " ")}</b><span>MAE {scores.mae} · RMSE {scores.rmse}</span></div>)}</div>
        <details className="methodology-note"><summary>Forecast evaluation and intervals</summary><p>{forecast.evaluation.split} {forecast.interval_method} {forecast.warning}</p></details>
      </Panel>
    </>}
  </>;
}

function BrandPage({ brands, records, topics }: { brands: BrandSummary[]; records: Post[]; topics: DashboardData["topics"]["topics"] }) {
  const brandNames = brands.map((brand) => brand.brand);
  const [selected, setSelected] = useState(brandNames[0] ?? "");
  const current = brands.find((brand) => brand.brand === selected);
  const [sourceFilter, setSourceFilter] = useState("All sources");
  const [sentimentFilter, setSentimentFilter] = useState("All sentiment");
  const [topicFilter, setTopicFilter] = useState("All topics");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const posts = records.filter((post) => post.brand === selected
    && (sourceFilter === "All sources" || post.platform === sourceFilter)
    && (sentimentFilter === "All sentiment" || post.sentiment === sentimentFilter.toLowerCase())
    && (topicFilter === "All topics" || post.text.toLowerCase().includes(topicFilter.toLowerCase()))
    && (!dateFrom || (post.timestamp ?? "").slice(0, 10) >= dateFrom)
    && (!dateTo || (post.timestamp ?? "").slice(0, 10) <= dateTo));
  const associatedTopicCount = topics.filter((item) =>
    posts.some((post) => item.terms.some((term) => post.text.toLowerCase().includes(term)))
  ).length;
  const dayMap = new Map<string, Record<string, number>>();
  for (const post of posts) if (post.timestamp) {
    const day = post.timestamp.slice(0, 10);
    const item = dayMap.get(day) ?? { positive: 0, neutral: 0, negative: 0 };
    item[post.sentiment] += 1; dayMap.set(day, item);
  }
  const series = [...dayMap].sort(([a], [b]) => a.localeCompare(b)).map(([date, values]) => ({ date: shortDate(date), ...values }));
  return <>
    <Panel title="Compare brands in the selected data" subtitle="Counts use the imported brand field; no entity verification is performed."><div className="brand-compare-grid">{brands.map((brand) => <button key={brand.brand} className={`brand-card ${selected === brand.brand ? "brand-card-selected" : ""}`} onClick={() => setSelected(brand.brand)}><div className="brand-card-top"><div className="brand-symbol">{brand.brand.slice(0, 1)}</div><ChevronRight size={15} /></div><b>{brand.brand}</b><span>{brand.mentions} mentions</span><div className="brand-stacked"><i style={{ width: `${brand.mentions ? brand.positive / brand.mentions * 100 : 0}%`, background: palette.positive }} /><i style={{ width: `${brand.mentions ? brand.neutral / brand.mentions * 100 : 0}%`, background: palette.neutral }} /><i style={{ width: `${brand.mentions ? brand.negative / brand.mentions * 100 : 0}%`, background: palette.negative }} /></div><small>Positive {brand.positive} · Neutral {brand.neutral} · Negative {brand.negative}</small></button>)}</div></Panel>
    {current && <>        <div className="section-subhead"><div><h2>{selected} intelligence</h2><p>Matched using the dataset's brand field</p></div></div><div className="explorer-toolbar"><label className="select-wrap"><Globe2 size={14} /><select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)}><option>All sources</option>{[...new Set(records.map((post) => post.platform))].map((platform) => <option key={platform}>{platform}</option>)}</select><ChevronDown size={12} /></label><label className="select-wrap"><Filter size={14} /><select value={sentimentFilter} onChange={(event) => setSentimentFilter(event.target.value)}><option>All sentiment</option><option>Positive</option><option>Neutral</option><option>Negative</option></select><ChevronDown size={12} /></label><label className="select-wrap"><Hash size={14} /><select value={topicFilter} onChange={(event) => setTopicFilter(event.target.value)}><option>All topics</option>{topics.map((item) => <option key={item.topic_id}>{item.terms[0]}</option>)}</select><ChevronDown size={12} /></label><label className="date-filter">From<input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label><label className="date-filter">To<input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} /></label></div><div className="kpi-grid"><MetricCard label="Mentions" value={number(posts.length)} icon={<MessageSquareText size={17} />} detail="Matching filters" accent="blue" /><MetricCard label="Positive" value={posts.length ? `${(posts.filter((post) => post.sentiment === "positive").length / posts.length * 100).toFixed(1)}%` : "—"} icon={<ArrowUpRight size={17} />} detail={`${posts.filter((post) => post.sentiment === "positive").length} posts`} accent="green" /><MetricCard label="Negative" value={posts.length ? `${(posts.filter((post) => post.sentiment === "negative").length / posts.length * 100).toFixed(1)}%` : "—"} icon={<ArrowDownRight size={17} />} detail={`${posts.filter((post) => post.sentiment === "negative").length} posts`} accent="red" /><MetricCard label="Topics associated" value={String(associatedTopicCount)} icon={<Network size={17} />} detail="Suggested topic matches" accent="violet" /></div><div className="dashboard-grid dashboard-grid-main"><Panel title="Sentiment over time" subtitle={`${selected} · daily counts`}><div className="chart-medium"><ResponsiveContainer width="100%" height="100%"><LineChart data={series}><CartesianGrid strokeDasharray="3 5" vertical={false} stroke="var(--grid)" /><XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 10 }} minTickGap={20} /><YAxis tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 10 }} /><Tooltip content={<ChartTooltip />} /><Line dataKey="positive" name="Positive" stroke={palette.positive} dot={false} /><Line dataKey="negative" name="Negative" stroke={palette.negative} dot={false} /><Line dataKey="neutral" name="Neutral" stroke={palette.neutral} dot={false} /></LineChart></ResponsiveContainer></div></Panel><Panel title="Matched examples" subtitle="Posts from the selected records"><PostTable records={posts.slice(0, 6)} /></Panel></div></>}
  </>;
}

function ExplorerPage(props: Parameters<typeof PageContent>[0]) {
  const { records, searchText, setSearchText, sentimentFilter, setSentimentFilter, brandFilter, setBrandFilter, platformFilter, setPlatformFilter, page, setPage } = props;
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sortOrder, setSortOrder] = useState("Newest first");
  const explorerRecords = useMemo(() => records.filter((record) => {
    const date = record.timestamp?.slice(0, 10) ?? "";
    return (!dateFrom || date >= dateFrom) && (!dateTo || date <= dateTo);
  }).sort((a, b) => {
    const comparison = (a.timestamp ?? "").localeCompare(b.timestamp ?? "");
    return sortOrder === "Newest first" ? -comparison : comparison;
  }), [records, dateFrom, dateTo, sortOrder]);
  const pageSize = 12;
  const pageCount = Math.max(1, Math.ceil(explorerRecords.length / pageSize));
  const rows = explorerRecords.slice((page - 1) * pageSize, page * pageSize);
  useEffect(() => setPage(1), [searchText, sentimentFilter, brandFilter, platformFilter, props.topicFilter, dateFrom, dateTo, sortOrder, setPage]);
  return <>
    <div className="explorer-toolbar"><label className="search-field"><Search size={16} /><input value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="Search conversation text…" /></label><label className="select-wrap"><Filter size={14} /><select value={sentimentFilter} onChange={(event) => setSentimentFilter(event.target.value)}><option>All sentiment</option><option>Positive</option><option>Neutral</option><option>Negative</option></select><ChevronDown size={12} /></label><label className="select-wrap"><Building2 size={14} /><select value={brandFilter} onChange={(event) => setBrandFilter(event.target.value)}><option>All brands</option>{props.data.brand_comparison.map((brand) => <option key={brand.brand}>{brand.brand}</option>)}</select><ChevronDown size={12} /></label><label className="select-wrap"><Globe2 size={14} /><select value={platformFilter} onChange={(event) => setPlatformFilter(event.target.value)}><option>All sources</option>{[...new Set(props.data.records.map((record) => record.platform))].map((platform) => <option key={platform}>{platform}</option>)}</select><ChevronDown size={12} /></label><label className="select-wrap"><Hash size={14} /><select value={props.topicFilter} onChange={(event) => props.setTopicFilter(event.target.value)}><option>All topics</option>{props.data.topics.topics.map((topic) => <option key={topic.topic_id}>{topic.terms[0]}</option>)}</select><ChevronDown size={12} /></label><label className="date-filter">From<input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label><label className="date-filter">To<input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} /></label><label className="select-wrap"><span>Sort</span><select value={sortOrder} onChange={(event) => setSortOrder(event.target.value)}><option>Newest first</option><option>Oldest first</option></select><ChevronDown size={12} /></label></div>
    <Panel title="Conversations" subtitle={`${number(explorerRecords.length)} records match the selected filters`} action={<button className="text-action" onClick={() => { const text = ["post_id,text,timestamp,platform,brand,sentiment", ...explorerRecords.map((post) => [post.post_id, post.text, post.timestamp, post.platform, post.brand, post.sentiment].map(csvCell).join(","))].join("\n"); downloadText(text, "socialpulse-conversations.csv", "text/csv"); }}><Download size={14} />Export CSV</button>}><PostTable records={rows} showConfidence /><div className="pagination"><span>Showing {explorerRecords.length ? (page - 1) * pageSize + 1 : 0}–{Math.min(page * pageSize, explorerRecords.length)} of {explorerRecords.length}</span><div><button className="icon-button" disabled={page <= 1} onClick={() => setPage(Math.max(1, page - 1))} aria-label="Previous page"><ChevronLeft size={15} /></button><span>Page {page} of {pageCount}</span><button className="icon-button" disabled={page >= pageCount} onClick={() => setPage(Math.min(pageCount, page + 1))} aria-label="Next page"><ChevronRight size={15} /></button></div></div></Panel>
  </>;
}

function PostTable({ records, showConfidence = false }: { records: Post[]; showConfidence?: boolean }) {
  if (!records.length) return <InlineEmpty text="No conversation records match this view." />;
  return <div className="table-scroll"><table className="data-table"><thead><tr><th>CONVERSATION</th><th>BRAND / TOPIC</th><th>SOURCE</th><th>TIME</th><th>SENTIMENT</th>{showConfidence && <th>SCORE</th>}</tr></thead><tbody>{records.map((post) => <tr key={post.post_id}><td><div className="post-text">{post.text}</div><small className="post-id">{post.post_id}</small></td><td><span className="plain-tag">{post.brand || "—"}</span></td><td>{post.platform || "—"}</td><td>{post.timestamp ? new Date(post.timestamp).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}</td><td><SentimentBadge sentiment={post.sentiment} /></td>{showConfidence && <td className="confidence-cell">{(post.sentiment_confidence * 100).toFixed(0)}%</td>}</tr>)}</tbody></table></div>;
}

function SentimentBadge({ sentiment }: { sentiment: Sentiment }) {
  return <span className={`sentiment-badge badge-${sentiment}`}><i />{sentiment}</span>;
}

function InsightsPage({ records }: { records: Post[] }) {
  const { trends, error } = useCurrentTrends(records, 7, 2, []);
  const scopedInsights: Insight[] = trends.filter((trend) => trend.current_mentions >= 8).map((trend) => ({
    title: `More recent mentions of “${trend.topic}”`,
    topic: trend.topic,
    evidence: trend.reason,
    period: `${trend.period_start} to ${trend.period_end}`,
    mentions: trend.current_mentions,
    previous_mentions: trend.previous_mentions,
    growth_percent: trend.growth_percent,
    sentiment_distribution: trend.sentiment_distribution,
    keywords: trend.keywords,
    representative_posts: trend.representative_posts,
    limitation: trend.limitation,
    recommendation: "Review the representative posts and validate this signal against a broader data source.",
  }));
  const negativeCount = records.filter((post) => post.sentiment === "negative").length;
  if (records.length >= 8 && negativeCount / records.length >= 0.35) {
    scopedInsights.push({
      title: "Negative sentiment is a sizeable share of the selected sample",
      topic: null,
      evidence: `${negativeCount} of ${records.length} posts (${(negativeCount / records.length * 100).toFixed(1)}%) were classified negative by the lexicon baseline.`,
      period: "Selected records",
      mentions: negativeCount,
      previous_mentions: null,
      growth_percent: null,
      sentiment_distribution: {
        positive: records.filter((post) => post.sentiment === "positive").length,
        neutral: records.filter((post) => post.sentiment === "neutral").length,
        negative: negativeCount,
      },
      keywords: [],
      representative_posts: records.filter((post) => post.sentiment === "negative").slice(0, 3).map((post) => post.text),
      limitation: "The lexicon is an uncalibrated baseline; this share is not evidence about a broader population.",
      recommendation: "Inspect the supporting records and compare with an independently labeled sample.",
    });
  }
  const insights = scopedInsights;
  return <>
    {error && <div className="inline-error">{error}</div>}
    {insights.length ? <div className="insight-list">{insights.map((insight, index) => <article className="insight-card" key={`${insight.title}-${index}`}><div className="insight-card-head"><div className="insight-badge"><Sparkles size={16} /></div><div><span className="section-eyebrow">OBSERVED SIGNAL · {insight.period}</span><h2>{insight.title}</h2></div></div><p className="insight-evidence">{insight.evidence}</p><div className="insight-metrics"><div><small>Current mentions</small><b>{insight.mentions}</b></div><div><small>Previous mentions</small><b>{insight.previous_mentions ?? "Not compared"}</b></div><div><small>Volume change</small><b>{insight.growth_percent === null ? "Guarded" : `${insight.growth_percent}%`}</b></div><div><small>Associated terms</small><b>{insight.keywords.slice(0, 3).join(", ") || "Not available"}</b></div></div>{insight.representative_posts.length > 0 && <div className="insight-quotes">{insight.representative_posts.slice(0, 2).map((post) => <blockquote key={post}>{post}</blockquote>)}</div>}<div className="recommendation-box"><Target size={15} /><div><b>Suggested human follow-up</b><span>{insight.recommendation}</span></div></div><p className="note-copy">{insight.limitation}</p></article>)}</div> : <Panel title="No qualifying findings" subtitle="Insights are generated only when evidence thresholds are met"><InlineEmpty text="Current metrics did not meet the configured evidence threshold." /></Panel>}
  </>;
}

function BigDataPage({ sources, records }: { sources: Parameters<typeof PageContent>[0]["sources"]; records: Post[] }) {
  const hadoop = sources?.sources.find((source) => String(source.name).includes("Hadoop"));
  return <>
    <div className="pipeline-overview"><div className="pipeline-step completed"><div><Check size={17} /></div><b>Current dataset</b><span>{number(records.length)} records loaded</span><small>Local application input</small></div><i className="pipeline-connector" /><div className="pipeline-step completed"><div><Check size={17} /></div><b>Local analytics</b><span>Analysis available</span><small>Single-machine mode</small></div><i className="pipeline-connector" /><div className="pipeline-step pending"><div><Database size={17} /></div><b>HDFS / Hadoop</b><span>{String(hadoop?.status ?? "not connected")}</span><small>Separate installation required</small></div><i className="pipeline-connector" /><div className="pipeline-step pending"><div><BarChart3 size={17} /></div><b>Hive queries</b><span>Not executed</span><small>Cluster not configured</small></div></div>
    <div className="dashboard-grid dashboard-grid-main">
      <Panel title="Processing mode" subtitle="Execution status">
        <div className="mode-status"><div className="status-big-icon"><Gauge size={21} /></div><div><b>Local single-machine processing</b><p>Current dashboard computations run with Python, Pandas, and scikit-learn.</p></div><span className="badge-local">LOCAL</span></div>
        <div className="source-detail-list"><div><span>Data records</span><b>{number(records.length)}</b></div><div><span>Processing duration</span><b>Not measured</b></div><div><span>HDFS / Hadoop</span><b>Not connected</b></div><div><span>Hive</span><b>Not executed</b></div><div><span>Spark job</span><b>Not executed</b></div></div>
      </Panel>
      <Panel title="Hadoop Streaming" subtitle="Run in a configured Hadoop or WSL environment">
        <div className="code-window"><div><i /><i /><i /><span>MAPREDUCE</span></div><pre>{`hdfs dfs -mkdir -p /socialpulse/input\nhdfs dfs -put data.csv /socialpulse/input/\nhadoop jar "$STREAMING_JAR" \\\\\n  -files mapper.py,reducer.py \\\\\n  -mapper "python3 mapper.py" \\\\\n  -reducer "python3 reducer.py" \\\\\n  -input /socialpulse/input/* \\\\\n  -output /socialpulse/output/wordcount-001\nhdfs dfs -cat /socialpulse/output/wordcount-001/part-*`}</pre></div>
        <p className="note-copy">Separate mapper examples provide word frequency, hashtag frequency, and date/topic/sentiment aggregation.</p>
      </Panel>
    </div>
    <Panel title="PySpark transformations" subtitle="Word, hashtag, and lexicon sentiment aggregates">
      <div className="code-window"><div><i /><i /><i /><span>LOCAL SPARK OR CLUSTER</span></div><pre>{`python -m pip install -r bigdata/spark/requirements.txt\nspark-submit --master "local[*]" \\\\\n  bigdata/spark/socialpulse_spark.py \\\\\n  data/sample/socialpulse_sample.csv data/spark-output\n\n# On a configured YARN cluster:\nspark-submit --master yarn bigdata/spark/socialpulse_spark.py \\\\\n  hdfs:///socialpulse/input/posts.csv hdfs:///socialpulse/output/spark-001`}</pre></div>
      <p className="note-copy">Spark writes word/hashtag frequencies, sentiment counts, and normalized posts to separate output paths. Local Spark is not distributed. The sentiment transformation uses the documented English lexicon; it is not model inference.</p>
    </Panel>
  </>;
}

function EvaluationPage() {
  const [file, setFile] = useState<File | null>(null);
  const [columns, setColumns] = useState<string[]>([]);
  const [textColumn, setTextColumn] = useState("");
  const [labelColumn, setLabelColumn] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const onFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected); setResult(null); setError("");
    if (!selected) return;
    try {
      const firstLine = (await selected.slice(0, 8192).text()).split(/\r?\n/, 1)[0];
      const parsed = firstLine.split(",").map((column) => column.trim().replace(/^"|"$/g, ""));
      setColumns(parsed); setTextColumn(parsed.find((column) => ["text", "content", "post"].includes(column.toLowerCase())) ?? parsed[0] ?? "");
      setLabelColumn(parsed.find((column) => ["sentiment", "label", "target"].includes(column.toLowerCase())) ?? parsed[parsed.length - 1] ?? "");
    } catch { setError("Could not read the labeled CSV header."); }
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) return;
    setBusy(true); setError(""); setResult(null);
    const body = new FormData(); body.append("file", file); body.append("text_column", textColumn); body.append("label_column", labelColumn);
    try {
      const response = await api<Record<string, unknown>>("/evaluate/sentiment", { method: "POST", body });
      setResult(response);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Evaluation failed."); }
    finally { setBusy(false); }
  };
  return <>
    <Panel title="Evaluate sentiment baseline" subtitle="Upload a labeled CSV with text and positive / neutral / negative reference labels"><form className="evaluation-form" onSubmit={(event) => void submit(event)}><label className="file-picker"><input type="file" accept=".csv,text/csv" onChange={(event) => void onFile(event)} /><Download size={17} /><span>{file?.name ?? "Choose a labeled CSV file"}</span><small>Maximum file size: 5 MB</small></label>{columns.length > 0 && <div className="forecast-form"><label>Text column<select value={textColumn} onChange={(event) => setTextColumn(event.target.value)}>{columns.map((column) => <option key={column}>{column}</option>)}</select></label><label>Label column<select value={labelColumn} onChange={(event) => setLabelColumn(event.target.value)}>{columns.map((column) => <option key={column}>{column}</option>)}</select></label><button className="button button-primary" disabled={busy || !file}>{busy ? <LoaderCircle size={15} className="spin" /> : <Brain size={15} />}{busy ? "Evaluating" : "Calculate metrics"}</button></div>}</form>{error && <div className="inline-error">{error}</div>}<details className="methodology-note"><summary>Evaluation method</summary><p>Metrics compare actual baseline inference with the reference labels supplied in this file. They are descriptive of this sample, not evidence of general model accuracy.</p></details></Panel>
    {result && <EvaluationResults result={result} />}
  </>;
}

function EvaluationResults({ result }: { result: Record<string, unknown> }) {
  const metrics = result.per_class as Record<string, Record<string, number>>;
  const labels = result.labels as string[];
  const matrix = result.confusion_matrix as number[][];
  return <><div className="kpi-grid"><MetricCard label="Accuracy" value={`${(Number(result.accuracy) * 100).toFixed(1)}%`} icon={<Target size={17} />} detail={`${result.examples} labeled examples`} accent="blue" />{labels.map((label) => <MetricCard key={label} label={`${label} F1`} value={`${((metrics[label]?.["f1-score"] ?? 0) * 100).toFixed(1)}%`} icon={<Brain size={17} />} detail="Per-class score" accent={label === "positive" ? "green" : label === "negative" ? "red" : "violet"} />)}</div><div className="dashboard-grid dashboard-grid-main"><Panel title="Per-class report" subtitle="Precision, recall, F1, and support"><div className="table-scroll"><table className="data-table"><thead><tr><th>LABEL</th><th>PRECISION</th><th>RECALL</th><th>F1</th><th>SUPPORT</th></tr></thead><tbody>{labels.map((label) => <tr key={label}><td>{label}</td>{["precision", "recall", "f1-score", "support"].map((key) => <td key={key}>{(metrics[label]?.[key] ?? 0).toFixed(key === "support" ? 0 : 3)}</td>)}</tr>)}</tbody></table></div></Panel><Panel title="Confusion matrix" subtitle="Rows = reference; columns = predicted"><div className="matrix-grid"><div /><span>Pred Pos</span><span>Pred Neu</span><span>Pred Neg</span>{labels.flatMap((label, row) => [<b key={`${row}-label`}>{label}</b>, ...(matrix[row] ?? []).map((value, col) => <span className={row === col ? "matrix-hit" : "matrix-miss"} key={`${row}-${col}`}>{value}</span>)])}</div></Panel></div><p className="note-copy">{String(result.note)}</p></>;
}

function SourcesPage({ sources, data, onRefresh, onImport }: {
  sources: Parameters<typeof PageContent>[0]["sources"];
  data: DashboardData;
  onRefresh: () => void;
  onImport: (file: File, columns: { text: string; timestamp: string; platform: string; brand: string }) => Promise<DashboardData>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [columns, setColumns] = useState({ text: "", timestamp: "", platform: "", brand: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await onImport(file, columns);
      setNotice(`Imported ${number(result.summary.total_posts)} records from ${file.name}.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Dataset import failed.");
    } finally {
      setBusy(false);
    }
  };
  return <>
    <Panel title="Import a dataset" subtitle="CSV or JSON records · local processing">
      <form className="source-import-form" onSubmit={(event) => void submit(event)}>
        <label className="file-picker"><input type="file" accept=".csv,.json,text/csv,application/json" onChange={(event) => { setFile(event.target.files?.[0] ?? null); setNotice(""); }} /><Download size={17} /><span>{file?.name ?? "Choose CSV or JSON file"}</span><small>Maximum file size: 5 MB</small></label>
        <div className="source-column-grid">
          {(["text", "timestamp", "platform", "brand"] as const).map((column) => <label key={column}>{column === "text" ? "Text column" : `${column[0].toUpperCase()}${column.slice(1)} column`}<input value={columns[column]} onChange={(event) => setColumns({ ...columns, [column]: event.target.value })} placeholder={column === "text" ? "Auto-detect if blank" : "Optional"} /></label>)}
        </div>
        <button className="button button-primary" type="submit" disabled={!file || busy}>{busy ? <LoaderCircle size={15} className="spin" /> : <Database size={15} />}{busy ? "Importing…" : "Import and analyze"}</button>
      </form>
      {error && <div className="inline-error">{error}</div>}
      {notice && <p className="import-success">{notice}</p>}
      <details className="methodology-note"><summary>Authorized API connectors</summary><p>No social-platform API adapter or credentials are configured in this workspace. LIVE status will remain unavailable unless a provider-specific, authorized connector is implemented and its API access is verified; importing a file never marks a source live.</p></details>
    </Panel>
    <div className="source-cards">{(sources?.sources ?? []).map((source) => <article className="source-card" key={String(source.name)}><div className="source-card-head"><div className="source-icon">{source.live === true ? <Globe2 size={19} /> : <Database size={19} />}</div><span className={source.connection_verified === true ? "source-state state-available" : "source-state state-offline"}><i />{String(source.status)}</span></div><h2>{String(source.name)}</h2><span className="source-type">{String(source.type)}</span><p>{String(source.description)}</p><div className="source-card-meta"><span>Connection verified</span><b>{source.connection_verified === true ? "Yes" : "No"}</b><span>Live data</span><b>{source.live === true ? "Yes" : "No"}</b>{source.name === "SocialPulse synthetic demo" && <><span>Generated records</span><b>{number(data.records.length)}</b><span>Last generated</span><b>{new Date(data.generated_at).toLocaleTimeString()}</b></>}</div>{source.name === "SocialPulse synthetic demo" && <button className="button button-secondary source-refresh" onClick={onRefresh}><RefreshCw size={14} />Regenerate demo sample</button>}</article>)}</div>
    <Panel title="Current source" subtitle="Data mode follows the loaded dataset"><div className="mode-status"><div className="status-big-icon"><Database size={21} /></div><div><b>{data.source.name}</b><p>{data.records.length.toLocaleString()} analyzed records · {data.source.type === "synthetic" ? "generated demo data" : "user-imported data"}</p></div><span className={`source-mode source-mode-${data.source.type}`}>{data.source.type === "synthetic" ? "DEMO" : data.source.type.toUpperCase()}</span></div><div className="source-detail-list"><div><span>Live API connector</span><b>Not configured</b></div><div><span>Automatic collection</span><b>Inactive</b></div><div><span>Refresh policy</span><b>Manual</b></div></div></Panel>
  </>;
}

function SettingsPage({ data }: { data: DashboardData }) {
  const settings = [
    ["Application", "SocialPulse AI", "Explainable social intelligence prototype"],
    ["Data mode", data.source.type === "synthetic" ? "Demo" : "Imported", data.source.name],
    ["Sentiment", data.summary.sentiment_model.name, "English lexicon baseline · not calibrated"],
    ["Topic discovery", data.topics.method, "Suggested labels require human review"],
    ["Analytics execution", "Local single-machine", "Pandas and scikit-learn; not distributed"],
    ["Persistence", "SQLite aggregate history", "Post text is not persisted"],
    ["Automatic refresh", "Disabled", "Refresh is user-triggered"],
  ];
  return <>
    <div className="settings-hero"><div className="settings-hero-mark"><Activity size={26} /></div><div><span>ACADEMIC PROJECT · VERSION 1.0.0</span><h2>SocialPulse AI</h2><p>Explainable Social Media Intelligence and Emerging Trend Forecasting Using Big Data Analytics</p></div></div>
    <div className="settings-grid">{settings.map(([label, value, note]) => <div className="setting-row" key={label}><div><span>{label}</span><small>{note}</small></div><b>{value}</b></div>)}</div>
    <div className="dashboard-grid dashboard-grid-main"><Panel title="Methodology and limitations" subtitle="Expand for model and interpretation details"><ul className="limitation-list"><li>Sentiment labels are English lexicon inference, not calibrated confidence or verified correctness.</li><li>Topic names are derived suggestions; inspect assigned posts and UMass coherence before interpretation.</li><li>Trend rankings compare equal adjacent windows; rankings are not significance tests or evidence of persistence.</li><li>Brand matching uses the supplied brand field and does not verify identity.</li><li>Demo records are synthetic and must never be described as live public opinion.</li><li>Only a cluster execution can be described as Hadoop, Hive, or Spark processing.</li></ul><details className="methodology-note"><summary>Algorithm details</summary><p>Text is normalized into word tokens. Topic suggestions use TF-IDF and seeded non-negative matrix factorization (NMF); representative posts are assigned by their largest topic weight. UMass coherence summarizes top-term co-occurrence and is not a ground-truth quality score.</p><p>Trend windows are complete calendar-day ranges; mentions count at most once per post and term. Ranking score = log(1 + current posts) × absolute change / max(previous posts, 1). Growth percentage is withheld when the prior count is below the configured minimum. No statistical significance is claimed.</p><p>Forecasts fill missing dates with zero within the observed date span and compare last-value and fixed-parameter Holt damped-trend models on a chronological holdout. MAE/RMSE and model selection are specific to this input series. Empirical error bands are omitted unless at least ten held-out errors are available; they are not calibrated confidence intervals.</p><p>The English positive/negative lexicon scores are rule-based matched-word evidence, not model correctness probabilities. Evaluate against an independent labeled dataset before making accuracy claims.</p></details></Panel><Panel title="Architecture" subtitle="Local analytics remain single-machine"><div className="architecture-lines"><span><b>React · TypeScript · Vite</b><small>Interactive analytics dashboard</small></span><ChevronDown size={15} /><span><b>FastAPI · Python</b><small>Validated HTTP analytics endpoints</small></span><ChevronDown size={15} /><span><b>Pandas · scikit-learn · SQLite</b><small>Local analytics and aggregate history</small></span></div></Panel></div>
  </>;
}

function LoadingState() {
  return <div className="loading-state"><div className="loading-orbit"><LoaderCircle size={24} className="spin" /></div><b>Preparing your demo workspace</b><span>Loading the synthetic dataset and calculating current analytics…</span></div>;
}

function EmptyState({ onRetry }: { onRetry: () => void }) {
  return <div className="loading-state error-empty"><div className="loading-orbit"><AlertTriangle size={22} /></div><b>Demo data is temporarily unavailable</b><span>Check that the FastAPI backend is running at {API}.</span><button className="button button-primary" onClick={onRetry}><RefreshCw size={15} />Try again</button></div>;
}

function csvCell(value: string | null) { return `"${String(value ?? "").replaceAll("\"", "\"\"")}"`; }
function downloadText(text: string, filename: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a"); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}

export default App;

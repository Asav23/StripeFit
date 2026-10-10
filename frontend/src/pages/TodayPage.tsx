import { CalendarDays, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { CalendarStatus, DailyResponse, DailySettingsOut, Day, DayEvent } from "../api/types";
import CalendarCard from "../components/CalendarCard";
import NotificationSettings from "../components/NotificationSettings";
import OutfitCard from "../components/OutfitCard";
import StyleCard from "../components/StyleCard";
import { Button, LinkButton, Notice, PageHeader, Skeleton, Tabs } from "../components/ui";
import { useToast } from "../context";
import { OCCASION_LABELS, TIMEZONE } from "../lib/format";

const EVENING_FROM_HOUR = 15; // from mid-afternoon, open on tomorrow's outfit

function dublinHour(): number {
  return Number(new Intl.DateTimeFormat("en-IE", { timeZone: TIMEZONE, hour: "numeric", hourCycle: "h23" }).format(new Date()));
}

function dayDate(isoDay: string): string {
  return new Intl.DateTimeFormat("en-IE", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" }).format(new Date(`${isoDay}T12:00:00Z`));
}

function time(iso: string): string {
  return new Intl.DateTimeFormat("en-IE", { timeZone: TIMEZONE, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(iso));
}

const CALENDAR_RETURN: Record<string, { message: string; tone: "success" | "info" | "error" }> = {
  connected: { message: "Google Calendar connected. Outfits now plan around your day.", tone: "success" },
  cancelled: { message: "Google Calendar wasn't connected.", tone: "info" },
  error: { message: "Couldn't connect Google Calendar. Try again.", tone: "error" },
};

/** The day's events as the planner sees them; the one the outfit is dressed for is highlighted. */
function DayEvents({ events, mainOccasion, connected, demo }: { events: DayEvent[]; mainOccasion: string; connected: boolean; demo: boolean }) {
  const mainIndex = events.findIndex((e) => e.occasion === mainOccasion);
  if (!events.length) {
    return (
      <p className="flex items-center gap-2 text-[13px] text-ink-2">
        <CalendarDays className="h-4 w-4 text-muted" />
        {connected || demo ? "Nothing on your calendar, so it's a casual day." : "A casual day. Connect Google Calendar to plan around your events."}
      </p>
    );
  }
  return (
    <ol className="divide-y divide-line rounded-xl border border-line bg-card shadow-[var(--shadow-xs)]" aria-label="Your day">
      {events.map((e, i) => (
        <li key={`${e.start}-${i}`} className={`flex items-center gap-3 px-4 py-2.5 ${i === mainIndex ? "bg-accent-soft/60" : ""}`}>
          <span className="w-12 shrink-0 font-mono text-[12px] text-ink-2">{e.all_day ? "All day" : time(e.start)}</span>
          <span className="min-w-0 flex-1 truncate text-[14px]">{e.title}</span>
          {e.occasion ? (
            <span className={`tag ${i === mainIndex ? "bg-accent text-white" : ""}`}>
              {i === mainIndex ? "Dressed for: " : ""}
              {OCCASION_LABELS[e.occasion] ?? e.occasion}
            </span>
          ) : (
            <span className="text-[11px] text-muted">no outfit change</span>
          )}
        </li>
      ))}
    </ol>
  );
}

export default function TodayPage() {
  const { notify, showError } = useToast();
  const [params, setParams] = useSearchParams();
  const asked = params.get("day");
  const [day, setDay] = useState<Day>(asked === "today" || asked === "tomorrow" ? asked : dublinHour() >= EVENING_FROM_HOUR ? "tomorrow" : "today");
  const [data, setData] = useState<DailyResponse | null>(null);
  const [settings, setSettings] = useState<DailySettingsOut | null>(null);
  const [calendar, setCalendar] = useState<CalendarStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [another, setAnother] = useState(false);
  const [blocker, setBlocker] = useState<{ message: string; nextStep?: string; code: string } | null>(null);

  const loadCalendar = useCallback(() => api.calendarStatus().then(setCalendar).catch(() => undefined), []);

  const load = useCallback(
    async (which: Day) => {
      setLoading(true);
      setBlocker(null);
      try {
        const d = await api.daily(which);
        setData(d);
        setSettings(d.settings);
      } catch (e) {
        setData(null);
        if (e instanceof ApiError && ["empty_wardrobe", "nothing_available"].includes(e.code)) {
          setBlocker({ message: e.message, nextStep: e.nextStep, code: e.code });
          setSettings(await api.dailySettings().catch(() => null));
        } else {
          showError(e);
        }
      } finally {
        setLoading(false);
      }
    },
    [showError],
  );

  useEffect(() => {
    void load(day);
  }, [day, load]);

  useEffect(() => {
    void loadCalendar();
    const result = params.get("calendar");
    if (result && CALENDAR_RETURN[result]) {
      notify(CALENDAR_RETURN[result].message, CALENDAR_RETURN[result].tone);
      params.delete("calendar");
      setParams(params, { replace: true });
    }
    // run once on arrival (handles the redirect back from Google)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pickDay = (next: Day) => {
    setDay(next);
    setParams({ day: next }, { replace: true });
  };

  const newOption = async () => {
    setAnother(true);
    try {
      setData(await api.dailyAnother(day));
    } catch (e) {
      showError(e);
    } finally {
      setAnother(false);
    }
  };

  const calendarChanged = () => {
    void loadCalendar();
    void load(day);
  };

  return (
    <div>
      <PageHeader
        kicker="Every day"
        title={day === "tomorrow" ? "What to wear tomorrow" : "What to wear today"}
        description="Planned from your calendar, the forecast for the whole day, and the clothes you have clean."
      />

      <Tabs<Day>
        label="Which day"
        value={day}
        onChange={pickDay}
        options={[
          { value: "today", label: "Today" },
          { value: "tomorrow", label: "Tomorrow" },
        ]}
      />

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="min-w-0 space-y-4">
          {data && (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-[13px] font-medium text-ink-2">{dayDate(data.day)}</p>
              <Button variant="secondary" size="sm" onClick={newOption} loading={another} disabled={loading}>
                {!another && <RefreshCw className="h-3.5 w-3.5" />}
                {another ? "Finding another…" : "Another option"}
              </Button>
            </div>
          )}

          {data && calendar && (
            <DayEvents events={data.events} mainOccasion={data.outfit.parsed.occasion} connected={calendar.connected} demo={calendar.demo} />
          )}

          {blocker && (
            <Notice tone="warn">
              <p className="font-medium">{blocker.message}</p>
              {blocker.nextStep && <p className="text-ink-2">{blocker.nextStep}</p>}
              <div className="mt-3">
                <LinkButton to={blocker.code === "empty_wardrobe" ? "/add" : "/"} variant="secondary">
                  {blocker.code === "empty_wardrobe" ? "Add clothes" : "Go to wardrobe"}
                </LinkButton>
              </div>
            </Notice>
          )}

          {loading && !data && (
            <div className="space-y-3" aria-busy="true">
              <Skeleton className="h-12" />
              <Skeleton className="h-80" />
            </div>
          )}
          {data && (
            <div className={loading ? "pointer-events-none opacity-60 transition-opacity" : "transition-opacity"} aria-busy={loading}>
              <OutfitCard outfit={data.outfit} onChange={(outfit) => setData({ ...data, outfit })} />
            </div>
          )}
        </div>

        <aside className="space-y-4">
          {settings && <NotificationSettings settings={settings} onChange={setSettings} />}
          {calendar && <CalendarCard status={calendar} onChange={calendarChanged} />}
          <StyleCard />
        </aside>
      </div>
    </div>
  );
}

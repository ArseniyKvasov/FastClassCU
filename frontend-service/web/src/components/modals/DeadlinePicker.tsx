import { useEffect, useMemo, useRef, useState } from "react";

const RU_MONTHS_NOM = [
  "Январь",
  "Февраль",
  "Март",
  "Апрель",
  "Май",
  "Июнь",
  "Июль",
  "Август",
  "Сентябрь",
  "Октябрь",
  "Ноябрь",
  "Декабрь",
];
const RU_MONTHS_GEN = [
  "января",
  "февраля",
  "марта",
  "апреля",
  "мая",
  "июня",
  "июля",
  "августа",
  "сентября",
  "октября",
  "ноября",
  "декабря",
];

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function isSameDay(a: Date | null, b: Date | null): boolean {
  return !!a && !!b && a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function buildCalendarDays(viewMonth: Date): (Date | null)[] {
  const year = viewMonth.getFullYear();
  const month = viewMonth.getMonth();
  const firstOfMonth = new Date(year, month, 1);
  const leadingBlanks = (firstOfMonth.getDay() + 6) % 7;
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: (Date | null)[] = [];
  for (let i = 0; i < leadingBlanks; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));
  while (cells.length < 42) cells.push(null);
  return cells;
}

interface DeadlinePickerProps {
  value: string;
  onChange: (iso: string) => void;
}

/**
 * Ported from core/static/js/pages/homework_wizard.js's deadline picker
 * (buildCalendarDays / renderCalendar / populateTimeSelects / etc.) - a
 * calendar-then-time popover instead of a native datetime-local input, to
 * match the monolith's look exactly.
 */
export function DeadlinePicker({ value, onChange }: DeadlinePickerProps) {
  const fieldRef = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const [isOpen, setOpen] = useState(false);
  const [pane, setPane] = useState<"calendar" | "time">("calendar");
  const [pickerSelectedDate, setPickerSelectedDate] = useState<Date | null>(value ? new Date(value) : null);
  const [calendarViewMonth, setCalendarViewMonth] = useState(() => {
    const base = value ? new Date(value) : new Date();
    return new Date(base.getFullYear(), base.getMonth(), 1);
  });
  const [hour, setHour] = useState<number>(value ? new Date(value).getHours() : 12);
  const [minute, setMinute] = useState<number>(value ? new Date(value).getMinutes() : 0);
  const [popoverStyle, setPopoverStyle] = useState<{ top: number; left: number } | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    const onClickOutside = (event: MouseEvent) => {
      if (fieldRef.current && !fieldRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [isOpen]);

  const openPopover = () => {
    const base = pickerSelectedDate ?? new Date();
    setCalendarViewMonth(new Date(base.getFullYear(), base.getMonth(), 1));
    setPane("calendar");
    const rect = fieldRef.current?.getBoundingClientRect();
    if (rect) {
      const popoverWidth = 300;
      const maxLeft = window.innerWidth - popoverWidth - 12;
      const left = Math.min(rect.left, Math.max(12, maxLeft));
      setPopoverStyle({ top: rect.bottom + 8, left });
    }
    setOpen(true);
  };

  const todayStart = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const cells = useMemo(() => buildCalendarDays(calendarViewMonth), [calendarViewMonth]);

  const hourOptions = useMemo(() => {
    const now = new Date();
    const isToday = isSameDay(pickerSelectedDate, now);
    const options: number[] = [];
    for (let h = 0; h < 24; h++) {
      if (isToday && h < now.getHours()) continue;
      options.push(h);
    }
    return options.length ? options : [23];
  }, [pickerSelectedDate]);

  const minuteOptions = useMemo(() => {
    const now = new Date();
    const isToday = isSameDay(pickerSelectedDate, now);
    let todayMinMinute = Math.ceil((now.getMinutes() + 1) / 5) * 5;
    let todayMinHour = now.getHours();
    if (todayMinMinute >= 60) {
      todayMinMinute = 0;
      todayMinHour += 1;
    }
    const minMinute = isToday && hour === todayMinHour ? todayMinMinute : 0;
    const options: number[] = [];
    for (let m = 0; m < 60; m += 5) {
      if (m < minMinute) continue;
      options.push(m);
    }
    return options.length ? options : [0];
  }, [pickerSelectedDate, hour]);

  useEffect(() => {
    if (!hourOptions.includes(hour)) setHour(hourOptions[0]);
  }, [hourOptions, hour]);
  useEffect(() => {
    if (!minuteOptions.includes(minute)) setMinute(minuteOptions[0]);
  }, [minuteOptions, minute]);

  const selectDay = (day: Date) => {
    setPickerSelectedDate(day);
    setPane("time");
  };

  const confirmTime = () => {
    if (!pickerSelectedDate) return;
    const result = new Date(pickerSelectedDate);
    result.setHours(hour, minute, 0, 0);
    onChange(result.toISOString());
    setOpen(false);
  };

  const clear = (event: React.MouseEvent) => {
    event.stopPropagation();
    setPickerSelectedDate(null);
    onChange("");
    setOpen(false);
  };

  const displayText = pickerSelectedDate
    ? `${pickerSelectedDate.getDate()} ${RU_MONTHS_GEN[pickerSelectedDate.getMonth()]}, ${pad(hour)}:${pad(minute)}`
    : "Без дедлайна";

  return (
    <div className="hw-deadline-control" ref={fieldRef}>
      <button type="button" className="hw-deadline-trigger" onClick={() => (isOpen ? setOpen(false) : openPopover())}>
        <i className="bi bi-calendar3"></i>
        <span>{displayText}</span>
      </button>
      {pickerSelectedDate ? (
        <button type="button" className="hw-deadline-clear" onClick={clear} title="Убрать дедлайн">
          <i className="bi bi-x-lg"></i>
        </button>
      ) : null}

      {isOpen && popoverStyle ? (
        <div
          className="hw-deadline-popover"
          ref={popoverRef}
          style={{ top: popoverStyle.top, left: popoverStyle.left }}
        >
          <div className={`hw-deadline-pane ${pane === "calendar" ? "" : "d-none"}`}>
            <div className="hw-cal-header">
              <button
                type="button"
                className="hw-cal-nav"
                onClick={() => setCalendarViewMonth(new Date(calendarViewMonth.getFullYear(), calendarViewMonth.getMonth() - 1, 1))}
              >
                <i className="bi bi-chevron-left"></i>
              </button>
              <span className="hw-cal-month">
                {RU_MONTHS_NOM[calendarViewMonth.getMonth()]} {calendarViewMonth.getFullYear()}
              </span>
              <button
                type="button"
                className="hw-cal-nav"
                onClick={() => setCalendarViewMonth(new Date(calendarViewMonth.getFullYear(), calendarViewMonth.getMonth() + 1, 1))}
              >
                <i className="bi bi-chevron-right"></i>
              </button>
            </div>
            <div className="hw-cal-weekdays">
              <span>Пн</span>
              <span>Вт</span>
              <span>Ср</span>
              <span>Чт</span>
              <span>Пт</span>
              <span>Сб</span>
              <span>Вс</span>
            </div>
            <div className="hw-cal-grid">
              {cells.map((day, idx) => {
                if (!day) return <span key={idx} className="hw-cal-cell hw-cal-cell-empty"></span>;
                const isPast = day < todayStart;
                const classes = ["hw-cal-cell"];
                if (isSameDay(day, todayStart)) classes.push("is-today");
                if (isSameDay(day, pickerSelectedDate)) classes.push("is-selected");
                return (
                  <button
                    key={idx}
                    type="button"
                    className={classes.join(" ")}
                    disabled={isPast}
                    onClick={() => selectDay(day)}
                  >
                    {day.getDate()}
                  </button>
                );
              })}
            </div>
          </div>

          <div className={`hw-deadline-pane ${pane === "time" ? "" : "d-none"}`}>
            <button type="button" className="hw-time-back" onClick={() => setPane("calendar")}>
              <i className="bi bi-chevron-left"></i>
              <span>
                {pickerSelectedDate ? `${pickerSelectedDate.getDate()} ${RU_MONTHS_GEN[pickerSelectedDate.getMonth()]}` : ""}
              </span>
            </button>
            <div className="hw-time-row">
              <div className="hw-time-select-group">
                <label>Часы</label>
                <select value={hour} onChange={(event) => setHour(Number(event.target.value))}>
                  {hourOptions.map((h) => (
                    <option key={h} value={h}>
                      {pad(h)}
                    </option>
                  ))}
                </select>
              </div>
              <span className="hw-time-colon">:</span>
              <div className="hw-time-select-group">
                <label>Минуты</label>
                <select value={minute} onChange={(event) => setMinute(Number(event.target.value))}>
                  {minuteOptions.map((m) => (
                    <option key={m} value={m}>
                      {pad(m)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <button type="button" className="hw-time-confirm" onClick={confirmTime}>
              Установить дедлайн
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

// Convenção de horário do banco: relógio do broker (NY+7) — GMT+3 no verão americano, GMT+2 no inverno.
// Ver backend/timeconv.py.

// Helper: compute local time from a broker time string ("HH:MM", HH pode ser >= 24) + offset in hours
export function toLocalTime(utcTimeStr, offsetH) {
  if (!utcTimeStr || !offsetH) return null;
  const [hStr, mStr] = utcTimeStr.split(':');
  let h = (((parseInt(hStr, 10) + offsetH) % 24) + 24) % 24;
  return `${h.toString().padStart(2, '0')}:${mStr}`;
}

// Offset (em horas) a somar ao relógio do broker para obter o horário de Brasília (BRT) na data.
// Verão americano: broker GMT+3 → BRT = broker − 6. Inverno americano: broker GMT+2 → BRT = broker − 5.
export function brokerToBrtOffsetHours(dateStr) {
  let y, m, d;
  if (dateStr && dateStr.includes('-')) {
    [y, m, d] = dateStr.slice(0, 10).split('-').map(Number);
  } else {
    const now = new Date();
    y = now.getUTCFullYear(); m = now.getUTCMonth() + 1; d = now.getUTCDate();
  }
  const noonUtc = new Date(Date.UTC(y, m - 1, d, 15, 0));
  const nyHour = Number(new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York', hour: '2-digit', hourCycle: 'h23',
  }).format(noonUtc));
  const nyOffset = nyHour - 15; // −4 (EDT) ou −5 (EST)
  const brokerOffset = nyOffset + 7; // +3 ou +2
  return -3 - brokerOffset; // −6 ou −5
}

// Rótulo "HH:MM" de um timestamp ISO relativo ao dia da sessão.
// Pontos após a meia-noite do broker (ex.: after-market B3 no verão americano) viram "24:05",
// que parseTimeToTimestamp converte corretamente para o dia seguinte (Date.UTC faz o rollover).
export function sessionTimeLabel(tsStr, sessionDate) {
  if (!tsStr) return null;
  const hhmm = tsStr.substring(11, 16);
  if (!sessionDate || tsStr.length < 16) return hhmm;
  const tsDate = tsStr.substring(0, 10);
  if (tsDate <= sessionDate) return hhmm;
  const dayDiff = Math.round((Date.UTC(...tsDate.split('-').map((v, i) => i === 1 ? Number(v) - 1 : Number(v))) -
    Date.UTC(...sessionDate.split('-').map((v, i) => i === 1 ? Number(v) - 1 : Number(v)))) / 86400000);
  const h = parseInt(hhmm.slice(0, 2), 10) + 24 * dayDiff;
  return `${String(h).padStart(2, '0')}:${hhmm.slice(3, 5)}`;
}

// Helper: parse time string and date string into UTC UNIX timestamp
export function parseTimeToTimestamp(dateStr, timeStr) {
  if (!timeStr) return 0;
  let year, month, day;
  if (dateStr && dateStr.includes("-")) {
    const parts = dateStr.split("-").map(Number);
    if (parts.length === 3 && !parts.some(isNaN)) {
      [year, month, day] = parts;
    }
  }
  if (year === undefined) {
    const now = new Date();
    year = now.getUTCFullYear(); month = now.getUTCMonth() + 1; day = now.getUTCDate();
  }
  const [hour, minute] = timeStr.split(":").map(Number);
  if (isNaN(hour) || isNaN(minute)) return 0;
  // hour pode ser >= 24 (ponto do dia seguinte); Date.UTC faz o rollover
  return Math.floor(Date.UTC(year, month - 1, day, hour, minute) / 1000);
}

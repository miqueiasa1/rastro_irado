// Helper: compute local time from UTC time string + offset in hours
export function toLocalTime(utcTimeStr, offsetH) {
  if (!utcTimeStr || !offsetH) return null;
  const [hStr, mStr] = utcTimeStr.split(':');
  let h = (parseInt(hStr, 10) + offsetH + 24) % 24;
  return `${h.toString().padStart(2, '0')}:${mStr}`;
}

// Helper: parse time string and date string into UTC UNIX timestamp
export function parseTimeToTimestamp(dateStr, timeStr) {
  if (!timeStr) return 0;
  let year = 2026, month = 6, day = 26;
  if (dateStr && dateStr.includes("-")) {
    const parts = dateStr.split("-").map(Number);
    if (parts.length === 3 && !parts.some(isNaN)) {
      [year, month, day] = parts;
    }
  }
  const [hour, minute] = timeStr.split(":").map(Number);
  if (isNaN(hour) || isNaN(minute)) return 0;
  return Math.floor(Date.UTC(year, month - 1, day, hour, minute) / 1000);
}

// Returns a small status tag for a date string, or null if invalid/empty.
// { text, cls } — "geçti" (past), "bugün" (today), "yaklaşıyor" (upcoming, with
// day count when near).
export function dateTag(s) {
  if (!s) return null;
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return null;
  const now = new Date();
  const d0 = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const t0 = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const days = Math.round((d0 - t0) / 86400000);
  if (days > 0) {
    return {
      text: days <= 14 ? `yaklaşıyor · ${days} gün` : 'yaklaşıyor',
      cls: 'bg-green-500/15 text-green-300 border-green-500/40',
    };
  }
  if (days === 0) {
    return { text: 'bugün', cls: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/40' };
  }
  return { text: 'geçti', cls: 'bg-gray-600/30 text-gray-400 border-gray-600/50' };
}

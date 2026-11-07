const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2021-06-30" -> "30 Jun 2021". Pure string work, so server and client render the same text. */
export function fmtDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** 3245000 -> "₹32,45,000" (Indian digit grouping). */
export function fmtINR(n: number): string {
  return `₹${inr.format(Math.round(n))}`;
}

/** 3245000 -> "₹32.45 lakh"; 12500000 -> "₹1.25 crore". */
export function fmtINRShort(n: number): string {
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} crore`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)} lakh`;
  return fmtINR(n);
}

export function pct(x: number): string {
  return `${Math.round(x * 100)}%`;
}

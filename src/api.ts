export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch("/api" + path, {
    method: body === undefined ? "GET" : "POST",
    credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = data.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((e: { msg: string }) => e.msg).join("; ")
          : `Request failed (${response.status}).`,
    );
  }
  return response.json();
}
export const money = (cents: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    cents / 100,
  );
export const day = (date: string) =>
  new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(date.includes("T") ? date : date + "T12:00:00"));
export const statusLabel: Record<string, string> = {
  draft: "Studio review",
  awaiting: "Awaiting client",
  accepted: "Accepted · unpaid",
  accepted_no_payment: "Confirmed · no payment",
  declined: "Revision requested",
  superseded: "Replaced",
  paid: "Sandbox paid",
  demo_paid: "Demo payment",
};

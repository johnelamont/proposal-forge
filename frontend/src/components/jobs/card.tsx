import { DASH } from "@/lib/format";

export function Card({
  title,
  aside,
  children,
}: {
  title: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <header className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold tracking-wide text-neutral-500 uppercase">
          {title}
        </h2>
        {aside}
      </header>
      {children}
    </section>
  );
}

/** Label/value grid. A null value renders as a dash, never as 0 or blank. */
export function Facts({
  items,
}: {
  items: Array<[string, React.ReactNode | null | undefined]>;
}) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
      {items.map(([k, v]) => (
        <div key={k}>
          <dt className="text-xs text-neutral-500">{k}</dt>
          <dd className={v == null ? "text-neutral-400" : ""}>{v ?? DASH}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Bullets({ items }: { items: string[] }) {
  if (items.length === 0)
    return <p className="text-sm text-neutral-400">{DASH}</p>;
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm">
      {items.map((t, i) => (
        <li key={i}>{t}</li>
      ))}
    </ul>
  );
}

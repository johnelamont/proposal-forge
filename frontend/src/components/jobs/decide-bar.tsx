export function DecideBar({
  busy,
  onContinue,
  onAbandon,
}: {
  busy: string | null;
  onContinue: () => void;
  onAbandon: () => void;
}) {
  const disabled = busy !== null;
  return (
    <div className="bg-background fixed inset-x-0 bottom-0 border-t border-neutral-200 p-3 dark:border-neutral-800">
      <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-3">
        <button
          type="button"
          onClick={onAbandon}
          disabled={disabled}
          className="rounded border border-neutral-300 px-4 py-2 text-sm font-medium disabled:opacity-50 dark:border-neutral-700"
        >
          {busy === "abandon" ? "Recording…" : "Abandon"}
        </button>
        <button
          type="button"
          onClick={onContinue}
          disabled={disabled}
          className="rounded bg-neutral-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
        >
          {busy === "continue" ? "Recording…" : "Continue"}
        </button>
      </div>
    </div>
  );
}

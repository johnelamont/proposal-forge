"use client";

// The proposal workspace (F3/F4): the current draft's sections with Edit /
// Refine / Copy, the quote, an optional apply-form paste for missed
// questions, and the versions-and-approvals list.

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError, proposalsApi } from "@/lib/api";
import { sectionText } from "@/lib/copy";
import type { ProposalOut } from "@/lib/types/proposal";

import { CopyButton } from "./copy-button";
import { QuoteCard } from "./quote-card";
import { SectionCard } from "./section-card";
import { VersionsList } from "./versions-list";

export function ProposalWorkspace({ id }: { id: string }) {
  const [data, setData] = useState<ProposalOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [formPaste, setFormPaste] = useState("");
  const [showPaste, setShowPaste] = useState(false);

  useEffect(() => {
    proposalsApi
      .get(id)
      .then(setData)
      .catch((e: unknown) =>
        setError(
          e instanceof ApiError && e.status === 404
            ? "No such proposal (or it isn't yours)."
            : e instanceof Error
              ? e.message
              : "Could not load.",
        ),
      );
  }, [id]);

  async function run(action: string, call: () => Promise<ProposalOut>) {
    setError(null);
    setBusy(action);
    try {
      setData(await call());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      throw e;
    } finally {
      setBusy(null);
    }
  }

  const refresh = () =>
    void proposalsApi
      .get(id)
      .then(setData)
      .catch(() => {});

  const nav = (
    <nav className="flex gap-4 text-sm">
      <Link href="/" className="underline">
        Home
      </Link>
      {data && (
        <Link href={`/jobs/${data.proposal.job_post_id}`} className="underline">
          Job review
        </Link>
      )}
    </nav>
  );

  if (!data) {
    return (
      <section className="flex flex-col gap-4">
        {nav}
        {error ? (
          <p role="alert" className="text-sm text-red-700 dark:text-red-300">
            {error}
          </p>
        ) : (
          <p className="text-sm text-neutral-500">Loading…</p>
        )}
      </section>
    );
  }

  const { proposal, versions, approvals } = data;
  const current =
    versions.find((v) => v.id === proposal.current_version_id) ??
    versions[versions.length - 1];
  const s = current?.sections;
  const meta = current?.ai_meta ?? null;
  const failed = !!meta?.failure;
  const copiedCount = approvals.length;

  return (
    <section className="flex flex-col gap-5 pb-8">
      {nav}
      <header>
        <p className="text-xs tracking-wide text-neutral-500 uppercase">
          Proposal · {proposal.status}
          {copiedCount > 0 &&
            ` · ${copiedCount} cop${copiedCount === 1 ? "y" : "ies"} logged`}
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">
          {data.job_title ?? "Untitled job"}
        </h1>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          Nothing here is sent anywhere. Copy what you approve of into Upwork
          yourself; each copy is logged against its version.
        </p>
      </header>

      {error && (
        <p
          role="alert"
          className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
        >
          {error}
        </p>
      )}

      {failed && meta?.failure && (
        <div className="flex flex-col gap-2 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 sm:flex-row sm:items-center sm:justify-between dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          <p role="alert">
            Claude could not draft this — {meta.failure.message} The sections
            below are empty; draft again or write them with Edit.
          </p>
          <button
            type="button"
            disabled={busy !== null}
            onClick={() =>
              void run("draft", () => proposalsApi.redraft(id)).catch(() => {})
            }
            className="rounded border border-red-300 px-3 py-1.5 disabled:opacity-50 dark:border-red-700"
          >
            {busy === "draft" ? "Drafting… (20–40 s)" : "Draft again"}
          </button>
        </div>
      )}

      {meta && meta.warnings.length > 0 && !failed && (
        <p className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
          {meta.warnings.join(" ")}
        </p>
      )}

      {s && current && (
        <>
          <SectionCard
            title="Cover letter"
            text={s.cover_letter ?? ""}
            confidence={meta?.confidence.cover_letter}
            proposalId={id}
            versionId={current.id}
            section="cover_letter"
            index={null}
            busy={busy !== null}
            onEdit={(content) =>
              run("edit", () =>
                proposalsApi.edit(id, "cover_letter", null, content),
              )
            }
            onRefine={(instruction) =>
              run("refine", () =>
                proposalsApi.refine(id, "cover_letter", null, instruction),
              )
            }
            onApproved={refresh}
          />

          {s.answers.map((a, i) => (
            <SectionCard
              key={`${current.id}-${i}`}
              title={`Q${i + 1}. ${a.question}`}
              text={a.answer}
              confidence={meta?.confidence.answers}
              proposalId={id}
              versionId={current.id}
              section="answer"
              index={i}
              busy={busy !== null}
              onEdit={(content) =>
                run("edit", () => proposalsApi.edit(id, "answer", i, content))
              }
              onRefine={(instruction) =>
                run("refine", () =>
                  proposalsApi.refine(id, "answer", i, instruction),
                )
              }
              onApproved={refresh}
            />
          ))}

          <QuoteCard
            quote={s.quote}
            proposalId={id}
            versionId={current.id}
            busy={busy !== null}
            onEdit={(amount, note) =>
              run("edit", () =>
                proposalsApi.edit(id, "quote", null, note, amount),
              )
            }
            onApproved={refresh}
          />

          <div className="flex flex-col gap-3 rounded-lg border border-neutral-200 p-4 sm:flex-row sm:items-start sm:justify-between dark:border-neutral-800">
            <div className="text-sm">
              <p className="font-medium">Copy everything</p>
              <p className="text-xs text-neutral-500">
                Cover letter, each question with its answer, and the quote — in
                one go, for the phone.
              </p>
            </div>
            <CopyButton
              proposalId={id}
              versionId={current.id}
              section="all"
              index={null}
              text={sectionText(s, "all", null)}
              label="Copy all"
              onApproved={refresh}
            />
          </div>
        </>
      )}

      <section className="rounded-lg border border-neutral-200 p-4 text-sm dark:border-neutral-800">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p>
            <span className="font-medium">
              Questions on Upwork&apos;s apply form not shown above?
            </span>{" "}
            <span className="text-neutral-500">
              Paste the form; the next draft answers them.
            </span>
          </p>
          <div className="flex gap-3 text-xs">
            <button
              type="button"
              onClick={() => setShowPaste((v) => !v)}
              className="underline"
            >
              {showPaste ? "Hide" : "Paste apply form"}
            </button>
            <button
              type="button"
              disabled={busy !== null}
              onClick={() =>
                void run("draft", () => proposalsApi.redraft(id)).catch(
                  () => {},
                )
              }
              className="underline disabled:opacity-50"
            >
              {busy === "draft"
                ? "Drafting… (20–40 s)"
                : "Draft again (new version)"}
            </button>
          </div>
        </div>
        {showPaste && (
          <form
            className="mt-3 flex flex-col gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void run("questions", () =>
                proposalsApi.addQuestions(id, formPaste),
              )
                .then(() => {
                  setFormPaste("");
                  setShowPaste(false);
                })
                .catch(() => {});
            }}
          >
            <textarea
              value={formPaste}
              onChange={(e) => setFormPaste(e.target.value)}
              rows={6}
              placeholder="Select all on the apply form, copy, paste here…"
              className="w-full rounded border border-neutral-300 p-3 font-mono text-xs dark:border-neutral-700 dark:bg-neutral-900"
            />
            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={busy !== null || formPaste.trim().length < 10}
                className="rounded bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
              >
                {busy === "questions" ? "Reading…" : "Add questions"}
              </button>
              <span className="text-xs text-neutral-500">
                Then use “Draft again” to answer them.
              </span>
            </div>
          </form>
        )}
        {proposal.extra_questions.length > 0 && (
          <p className="mt-2 text-xs text-neutral-500">
            Added from the form: {proposal.extra_questions.join(" · ")}
          </p>
        )}
      </section>

      <VersionsList
        versions={versions}
        approvals={approvals}
        currentId={proposal.current_version_id}
      />
    </section>
  );
}

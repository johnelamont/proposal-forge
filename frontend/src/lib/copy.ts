// Copy-as-approval helpers (F3, R1/R2).
//
// The text written to the clipboard is composed here, identically to the
// backend's section_text(), and hashed with SHA-256; the approval posts that
// hash and the server recomputes it from the stored version. Composing on the
// client lets the clipboard write happen inside the click (browsers require
// it) before any network call.
import type { SectionName, Sections } from "@/lib/types/proposal";

export function sectionText(
  sections: Sections,
  section: SectionName,
  index: number | null,
): string {
  if (section === "cover_letter") return sections.cover_letter ?? "";
  if (section === "answer") {
    if (index === null || !sections.answers[index]) return "";
    return sections.answers[index].answer;
  }
  if (section === "quote") {
    const q = sections.quote;
    return q === null || q.amount === null ? "" : q.amount;
  }
  const parts: string[] = [sections.cover_letter ?? ""];
  for (const a of sections.answers) parts.push(`${a.question}\n${a.answer}`);
  if (sections.quote && sections.quote.amount !== null) {
    const unit = sections.quote.model === "hourly" ? "/hr" : "";
    parts.push(`Quote: $${sections.quote.amount}${unit}`);
  }
  return parts.filter((p) => p.trim()).join("\n\n");
}

export async function sha256Hex(text: string): Promise<string> {
  const data = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export const APPROVAL_STATEMENT =
  "Copying this content counts as your approval of it.";

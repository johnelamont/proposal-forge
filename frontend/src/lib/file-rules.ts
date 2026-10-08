// Browser-side mirror of backend/app/services/file_rules.py, for immediate
// feedback in the drop zone. The server screens again and is authoritative;
// this only decides what gets read and shown before Extract.

export const MAX_FILES = 5;
export const MAX_BYTES = 200_000;

const TEXT_EXTENSIONS = [".md", ".markdown", ".txt", ".rst", ".adoc"];
const MANIFEST_NAMES = [
  "package.json",
  "pyproject.toml",
  "cargo.toml",
  "go.mod",
  "composer.json",
  "gemfile",
  "setup.py",
  "setup.cfg",
  "pom.xml",
  "build.gradle",
];
const MANIFEST_PATTERNS = [/^requirements[^/\\]*\.txt$/, /\.csproj$/];

const REFUSED: Array<[RegExp, string]> = [
  [/^\.env($|\.)/, "environment file"],
  [/\.(pem|p12|pfx|key|crt|cer|der|jks|kdbx|ppk)$/, "key or certificate"],
  [/^id_(rsa|dsa|ecdsa|ed25519)/, "SSH key"],
  [
    /(^|[._-])(secret|secrets|credential|credentials|token)([._-]|$)/,
    "looks like a credentials file",
  ],
  [/\.(zip|tar|gz|tgz|bz2|7z|rar|xz)$/, "archive"],
  [/\.(csv|tsv|xlsx|xls|db|sqlite|sqlite3|parquet|sql|bak|dump)$/, "data file"],
  [/\.(json|ya?ml|toml|ini|cfg|conf|xml)$/, "config or data file"],
];

function isManifest(lower: string) {
  return (
    MANIFEST_NAMES.includes(lower) ||
    MANIFEST_PATTERNS.some((p) => p.test(lower))
  );
}

/** Reason a file name is refused, or null if it may be read and sent. */
export function nameRefusal(name: string): string | null {
  const lower = name.split(/[\\/]/).pop()!.toLowerCase();
  for (const [pattern, reason] of REFUSED) {
    if (pattern.test(lower)) return isManifest(lower) ? null : reason;
  }
  const dot = lower.lastIndexOf(".");
  const ext = dot >= 0 ? lower.slice(dot) : "";
  if (TEXT_EXTENSIONS.includes(ext) || isManifest(lower)) return null;
  return "unsupported type (text, Markdown, or a dependency manifest only)";
}

export function sizeRefusal(size: number): string | null {
  if (size === 0) return "empty file";
  if (size > MAX_BYTES) return `larger than ${MAX_BYTES / 1000} KB`;
  return null;
}

// Compact markdown renderer tuned for the synthesize node's output.
//
// It handles the subset the synth prompt produces (headings, bullet/ordered
// lists, paragraphs, blockquotes, fenced code, bold, inline code) and layers two
// Loupe-specific behaviours on top of the prose:
//   1. `[Sn]` citation markers become clickable chips (open the evidence drawer).
//   2. Once the claim audit arrives, each sentence gets a colored verdict
//      underline by matching its normalized text against the audited claims.
//
// This is a best-effort visual layer; the ClaimAuditTable is the authoritative
// verdict view. Code blocks are never chip-ified or underlined (they are never
// claim-audited server-side either).

import type { JSX, ReactNode } from "react";
import type { Verdict } from "./types";

const CITE_RE = /\[S\d+\]/g;

/** Normalize a sentence/claim for verdict matching (drop markers, punctuation, case). */
export function normalizeClaim(text: string): string {
  return text
    .replace(CITE_RE, "")
    .toLowerCase()
    .replace(/[\s]+/g, " ")
    .replace(/[.,;:!?"'`)(\]\[]+$/g, "")
    .trim();
}

export type MarkdownOptions = {
  /** normalized claim text -> verdict (empty until the audit arrives). */
  verdicts?: Map<string, Verdict>;
  /** invoked with the source id (e.g. "S1") when a citation chip is clicked. */
  onCite?: (sourceId: string) => void;
};

const VERDICT_CLASS: Record<Verdict, string> = {
  SUPPORTED: "claim-underline claim-supported",
  PARTIAL: "claim-underline claim-partial",
  UNSUPPORTED: "claim-underline claim-unsupported",
};

export function renderMarkdown(md: string, opts: MarkdownOptions = {}): ReactNode {
  const blocks = splitBlocks(md);
  return blocks.map((block, i) => renderBlock(block, i, opts));
}

type Block =
  | { kind: "code"; lang: string; text: string }
  | { kind: "heading"; level: number; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "quote"; text: string }
  | { kind: "p"; text: string };

function splitBlocks(md: string): Block[] {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.trim() === "") {
      i++;
      continue;
    }

    // Fenced code block.
    const fence = line.match(/^```(.*)$/);
    if (fence) {
      const lang = fence[1].trim();
      const body: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        body.push(lines[i]);
        i++;
      }
      i++; // consume closing fence
      blocks.push({ kind: "code", lang, text: body.join("\n") });
      continue;
    }

    // Heading.
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      blocks.push({ kind: "heading", level: heading[1].length, text: heading[2].trim() });
      i++;
      continue;
    }

    // Unordered list.
    if (/^\s*[-*+]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*+]\s+/, ""));
        i++;
      }
      blocks.push({ kind: "ul", items });
      continue;
    }

    // Ordered list.
    if (/^\s*\d+[.)]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+[.)]\s+/, ""));
        i++;
      }
      blocks.push({ kind: "ol", items });
      continue;
    }

    // Blockquote.
    if (/^\s*>\s?/.test(line)) {
      const body: string[] = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        body.push(lines[i].replace(/^\s*>\s?/, ""));
        i++;
      }
      blocks.push({ kind: "quote", text: body.join(" ") });
      continue;
    }

    // Paragraph: gather until a blank line or a block-starting line.
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() !== "" && !isBlockStart(lines[i])) {
      para.push(lines[i]);
      i++;
    }
    blocks.push({ kind: "p", text: para.join(" ") });
  }

  return blocks;
}

function isBlockStart(line: string): boolean {
  return (
    /^```/.test(line) ||
    /^#{1,6}\s+/.test(line) ||
    /^\s*[-*+]\s+/.test(line) ||
    /^\s*\d+[.)]\s+/.test(line) ||
    /^\s*>\s?/.test(line)
  );
}

function renderBlock(block: Block, key: number, opts: MarkdownOptions): ReactNode {
  switch (block.kind) {
    case "code":
      return (
        <pre key={key} className="md-code">
          <code>{block.text}</code>
        </pre>
      );
    case "heading": {
      const Tag = `h${Math.min(block.level + 1, 6)}` as keyof JSX.IntrinsicElements;
      return (
        <Tag key={key} className="md-heading">
          {renderInline(block.text, `${key}`, opts)}
        </Tag>
      );
    }
    case "ul":
      return (
        <ul key={key} className="md-list">
          {block.items.map((item, j) => (
            <li key={j}>{renderProse(item, `${key}-${j}`, opts)}</li>
          ))}
        </ul>
      );
    case "ol":
      return (
        <ol key={key} className="md-list md-list-ol">
          {block.items.map((item, j) => (
            <li key={j}>{renderProse(item, `${key}-${j}`, opts)}</li>
          ))}
        </ol>
      );
    case "quote":
      return (
        <blockquote key={key} className="md-quote">
          {renderProse(block.text, `${key}`, opts)}
        </blockquote>
      );
    case "p":
      return (
        <p key={key} className="md-p">
          {renderProse(block.text, `${key}`, opts)}
        </p>
      );
  }
}

// Split prose into sentence spans and underline any that match an audited claim.
function renderProse(text: string, keyBase: string, opts: MarkdownOptions): ReactNode {
  const verdicts = opts.verdicts;
  if (!verdicts || verdicts.size === 0) {
    return renderInline(text, keyBase, opts);
  }
  const sentences = splitSentences(text);
  return sentences.map((sentence, i) => {
    const verdict = verdicts.get(normalizeClaim(sentence));
    const inline = renderInline(sentence, `${keyBase}-s${i}`, opts);
    if (!verdict) return <span key={i}>{inline}</span>;
    return (
      <span key={i} className={VERDICT_CLASS[verdict]} title={`Claim: ${verdict}`}>
        {inline}
      </span>
    );
  });
}

function splitSentences(text: string): string[] {
  // Keep the delimiter with the preceding sentence; keep trailing space so
  // rejoined output reads naturally.
  const parts = text.match(/[^.!?]+[.!?]+(\s+|$)|[^.!?]+$/g);
  return parts ? parts : [text];
}

// Inline: **bold**, `code`, and [Sn] citation chips.
function renderInline(text: string, keyBase: string, opts: MarkdownOptions): ReactNode[] {
  const nodes: ReactNode[] = [];
  // Tokenize on the three inline constructs in one pass.
  const re = /(\*\*([^*]+)\*\*)|(`([^`]+)`)|(\[S\d+\])/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let n = 0;

  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push(text.slice(last, match.index));
    }
    if (match[1] !== undefined) {
      nodes.push(<strong key={`${keyBase}-b${n}`}>{match[2]}</strong>);
    } else if (match[3] !== undefined) {
      nodes.push(
        <code key={`${keyBase}-c${n}`} className="md-inline-code">
          {match[4]}
        </code>
      );
    } else if (match[5] !== undefined) {
      const sourceId = match[5].slice(1, -1); // "S1"
      nodes.push(
        <button
          key={`${keyBase}-cite${n}`}
          type="button"
          className="cite-chip"
          onClick={() => opts.onCite?.(sourceId)}
          title={`Open evidence ${sourceId}`}
        >
          {sourceId}
        </button>
      );
    }
    last = re.lastIndex;
    n++;
  }
  if (last < text.length) {
    nodes.push(text.slice(last));
  }
  return nodes;
}

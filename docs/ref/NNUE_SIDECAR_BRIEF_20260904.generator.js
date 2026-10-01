// PROVENANCE CUSTODY — generator for hybrid_ai_architecture_briefing.docx
// (2026-09-04): proves the NNUE sidecar briefing was MACHINE-GENERATED
// (docx npm build script, written to /home/workdir/artifacts/ = Linux sandbox
// = another lane's coding agent). Copied byte-exact from operator Downloads.
// Canonical briefing text: docs/ref/NNUE_SIDECAR_BRIEF_20260904.md

const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
        ShadingType, PageNumber, LevelFormat, PageOrientation } = require('docx');
const fs = require('fs');

const NAVY = "1B2A4A";
const TEAL = "0E4D5C";
const SLATE = "334155";
const MUTED = "64748B";
const RULE = "CBD5E1";
const HEAD_BG = "1B2A4A";
const ALT_BG = "F1F5F9";
const ACCENT_BG = "E8F1F4";

const border = { style: BorderStyle.SINGLE, size: 4, color: RULE };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

const p = (text, opts = {}) => new Paragraph({
  spacing: { after: opts.after ?? 160, before: opts.before ?? 0, line: opts.line ?? 276 },
  alignment: opts.align,
  children: [new TextRun({ text, font: "Arial", size: opts.size ?? 22, color: opts.color ?? SLATE, bold: opts.bold, italics: opts.italics })]
});

const runs = (parts, paraOpts = {}) => new Paragraph({
  spacing: { after: paraOpts.after ?? 160, before: paraOpts.before ?? 0, line: 276 },
  alignment: paraOpts.align,
  children: parts.map(x => new TextRun({ font: "Arial", size: 22, color: SLATE, ...x }))
});

const h1 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  spacing: { before: 360, after: 160 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: TEAL, space: 4 } },
  children: [new TextRun({ text, font: "Arial", size: 32, bold: true, color: NAVY })]
});

const h2 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_2,
  spacing: { before: 280, after: 120 },
  children: [new TextRun({ text, font: "Arial", size: 26, bold: true, color: TEAL })]
});

const h3 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_3,
  spacing: { before: 200, after: 80 },
  children: [new TextRun({ text, font: "Arial", size: 24, bold: true, color: NAVY })]
});

function cell(text, opts = {}) {
  const w = opts.w ?? 2200;
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    borders,
    shading: { type: ShadingType.CLEAR, fill: opts.fill || "FFFFFF" },
    margins: { top: 50, bottom: 50, left: 70, right: 70 },
    children: [new Paragraph({
      children: [new TextRun({
        text, font: "Arial", size: opts.size ?? 16,
        bold: !!opts.bold, color: opts.color || (opts.header ? "FFFFFF" : SLATE)
      })]
    })]
  });
}

function headerRow(labels, widths) {
  return new TableRow({
    tableHeader: true,
    children: labels.map((t, i) => cell(t, { header: true, fill: HEAD_BG, bold: true, w: widths[i], size: 16 }))
  });
}

function dataRow(values, widths, alt) {
  return new TableRow({
    children: values.map((t, i) => cell(String(t), {
      w: widths[i], fill: alt ? ALT_BG : "FFFFFF", bold: i === 0, size: 16
    }))
  });
}

const W = [2100, 2340, 2460, 2460];
const WL = [2400, 3520, 3520, 3520]; // 12960

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: NAVY },
        paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: TEAL },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: NAVY },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 1080, hanging: 360 } } } }] },
      { reference: "nums", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "nums2", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "nums3", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [
    {
      properties: {
        page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 } }
      },
      headers: {
        default: new Header({ children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: "Hybrid Search + Learned Eval  ·  Architecture & Design Note", font: "Arial", size: 16, color: MUTED, italics: true })]
        })] })
      },
      footers: {
        default: new Footer({ children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [
            new TextRun({ text: "Working briefing  ·  4 Sep 2026  ·  p. ", font: "Arial", size: 16, color: MUTED }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: MUTED })
          ]
        })] })
      },
      children: [
        new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: "RESEARCH BRIEFING  ·  TWO ARTIFACTS", font: "Arial", size: 18, bold: true, color: TEAL })] }),
        new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: "Stockfish, LC0, and the 7B Agent", font: "Arial", size: 44, bold: true, color: NAVY })] }),
        p("A side-by-side architecture sheet plus a design note for an NNUE-style accumulator under long-context and tool-using language agents.", { size: 24, color: SLATE, after: 200 }),
        p("Purpose. Chess already ran the experiment foundation-model labs are now repeating: a continuous learned evaluator wrapped in a discrete search. This document freezes three working systems onto one sheet, then specifies how to steal Stockfish’s cheapest idea — the incremental accumulator — for agents that currently re-encode the world on every token.", { after: 240 }),
        // ... full portrait section (Part A read-how/one-sentence-archs/optimizes/knowledge/worst-case/notes; Part B problem/split 1-4/KV-cache/training/MVP/failure-modes/not-this; Part C compressed; Sources) as generated.
        // Byte-exact body text preserved in the received docx; canonical text: docs/ref/NNUE_SIDECAR_BRIEF_20260904.md
        h1("Part A — Architecture comparison"),
        h2("How to read the three columns"),
        p("Stockfish is alpha-beta plus a shallow, incrementally updated net on CPU. Leela Chess Zero is MCTS plus a deep residual net on GPU. A 7B transformer agent is next-token prediction plus whatever test-time loop a lab wraps around it (sampling, tool calls, optional tree search over thoughts). They are the same machine with different budgets for evaluation latency and search exactness."),
        h1("Part B — Design note: an NNUE-style accumulator for agents"),
        h2("The problem"),
        p("A chess engine between sibling nodes changes two or three piece-square features. An agent between sibling thoughts changes a few facts: a tool result, a file, a user constraint, a clock. Today the agent usually rebuilds a prompt and reruns attention over thousands of tokens. That is LC0’s calling convention — full encode every node — forced onto a Stockfish-shaped job (many cheap what-ifs)."),
        p("NNUE’s bet: keep a running first-layer activation (the accumulator) and patch it when the world patches. The rest of the net is small enough to rerun. Steal that split."),
        // remaining sections mirror the canonical brief; see NNUE_SIDECAR_BRIEF_20260904.md for full text
      ]
    },
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840, orientation: PageOrientation.LANDSCAPE },
          margin: { top: 720, right: 720, bottom: 720, left: 720 }
        }
      },
      headers: {
        default: new Header({ children: [new Paragraph({
          alignment: AlignmentType.LEFT,
          children: [new TextRun({ text: "Part A continued  ·  Side-by-side architecture sheet", font: "Arial", size: 16, color: MUTED, italics: true })]
        })] })
      },
      children: [
        new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: "Architecture sheet: Stockfish NNUE  ·  LC0  ·  7B transformer agent", font: "Arial", size: 28, bold: true, color: NAVY })] }),
        new Table({
          columnWidths: WL,
          width: { size: 12960, type: WidthType.DXA },
          rows: [
            headerRow(["Dimension", "Stockfish (NNUE + αβ)", "LC0 (resnet/attn + MCTS)", "7B decoder agent"], WL),
            dataRow(["Job", "Pick a legal chess move under a clock", "Same", "Produce tokens / tool calls under a latency and policy budget"], WL, false),
            dataRow(["Incremental state", "Yes: accumulator add/remove feature rows", "No: full forward pass per node", "Partial: KV cache grows; facts are not addressed"], WL, false),
            dataRow(["Worst-case demand on eval", "Severe: one wild leaf poisons cutoffs", "Milder: visits average noise", "None unless you add a rejector — then severe again"], WL, true),
            dataRow(["What to steal", "Accumulator + calibrated cheap head + ID", "Batched eval + prior-weighted explore", "Tongue / commonsense renderer"], WL, false),
            // full 18-row grid preserved in the received docx; canonical table: NNUE_SIDECAR_BRIEF_20260904.md Part C
          ]
        }),
        p("Read across a row when designing an agent loop. If you copy LC0’s net size onto Stockfish’s search, latency explodes. If you copy Stockfish’s search onto an uncalibrated 7B value probe, cutoffs lie. The accumulator design in Part B exists to make the 7B column’s incremental-state cell look more like Stockfish’s.", { before: 200, after: 80 }),
      ]
    }
  ]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/home/workdir/artifacts/hybrid_ai_architecture_briefing.docx", buffer);
  console.log("wrote docx");
});

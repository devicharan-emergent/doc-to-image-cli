# doc-to-image

CLI tool that renders each page of a PDF or DOCX document as a PNG image. Used by Emergent agents to *see* document content — the produced PNGs are then read via the in-pod `view_file` MCP tool, which returns image content blocks to the LLM.

The companion skill `internal_skills/doc-to-image/SKILL.md` documents the agent-facing workflow.

## Install

```bash
pip install /path/to/doc-to-image           # editable in dev
pip install doc_to_image-*.whl              # from a built wheel
```

After install, the `doc-to-image` command is on `PATH`.

## Usage

```
doc-to-image INPUT_FILE [-o OUTPUT_DIR] [-d DPI] [-p PAGE_RANGE]
```

| Flag | Default | Notes |
|---|---|---|
| `-o, --out` | `./<basename>-pages/` | Output directory; created if missing |
| `-d, --dpi` | `144` | Render resolution (range 72–300) |
| `-p, --pages` | all | Range like `1-5`, or single page like `3` |

Prints one absolute PNG path per line on stdout. Errors and the summary go to stderr.

## Examples

```bash
doc-to-image /app/invoice.pdf                                  # → ./invoice-pages/invoice-page-001.png ...
doc-to-image /app/contract.docx -o /tmp/contract/              # → /tmp/contract/contract-page-001.png ...
doc-to-image /app/report.pdf -p 1-3 -d 240                     # first 3 pages at 240 DPI
doc-to-image /app/letter.docx -p 1                             # single page
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success (including "page range produced no pages") |
| 2 | Unsupported file type |
| 3 | Required library not installed |
| 4 | Render failure (corrupt file, etc.) |

## Build a wheel

```bash
cd /Users/devicharan/mono/doc-to-image
uv build --wheel -o dist/         # or: python -m build --wheel
```

## Caveats

- `aspose-words` (the DOCX renderer) is a heavy dep (~200 MB) and adds an evaluation watermark unless a license is loaded.
- `pymupdf` and `aspose-words` both ship platform-specific C extensions. Build wheels on a matching arch (x86_64 vs arm64) for the target pod.

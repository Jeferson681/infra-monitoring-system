# Diagrams — Architecture

This folder contains a Mermaid diagram of the system architecture.

Files:
- `architecture.mmd` — Mermaid source diagram.

How to render to PNG/SVG:

- Using npx (requires Node.js):
```powershell
npx @mermaid-js/mermaid-cli -i docs\diagrams\architecture.mmd -o docs\prints\architecture.png
```

- Using Docker (no local Node.js):
```powershell
# Pull once
docker run --rm -v ${PWD}:/workdir -w /workdir minlag/mermaid-cli -i docs/diagrams/architecture.mmd -o docs/prints/architecture.png
```

- Or open `architecture.mmd` with a Mermaid-capable editor/VSCode plugin and export as PNG.

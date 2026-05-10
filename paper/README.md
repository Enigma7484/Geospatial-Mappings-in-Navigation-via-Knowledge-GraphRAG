# How to Use This LaTeX Draft

This folder is the paper draft.

## What the files are

- `main.tex`: the main paper file. Compile this one.
- `sections/*.tex`: section text included by `main.tex`.
- `references.bib`: bibliography entries used by citations like `\cite{nasr2019}`.
- `main.pdf`: the compiled PDF output after LaTeX runs.

## Easiest option: Overleaf

1. Go to https://www.overleaf.com.
2. Create a new blank project.
3. Upload the whole `paper/` folder contents.
4. Make sure `main.tex` is the main document.
5. Click **Recompile**.
6. Edit text in either `main.tex` or the files inside `sections/`.

You do not need to copy-paste everything manually. Uploading the files is cleaner.

## Local Windows option

MiKTeX was installed with:

```powershell
winget install MiKTeX.MiKTeX --accept-package-agreements --accept-source-agreements
```

If `pdflatex` is not on your PATH yet, use the full path:

```powershell
cd "C:\Users\enigm\OneDrive\Desktop\ML\Geospatial Mappings in Navigation via (Knowledge)GraphRAG\paper"
& "$env:LOCALAPPDATA\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe" -halt-on-error -interaction=nonstopmode main.tex
& "$env:LOCALAPPDATA\Programs\MiKTeX\miktex\bin\x64\bibtex.exe" main
& "$env:LOCALAPPDATA\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe" -halt-on-error -interaction=nonstopmode main.tex
& "$env:LOCALAPPDATA\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe" -halt-on-error -interaction=nonstopmode main.tex
```

The repeated `pdflatex` runs are normal. LaTeX needs multiple passes to resolve citations, references, and page layout.

## What to edit first

Start with these:

1. `sections/introduction.tex`
2. `sections/related_work.tex`
3. `sections/results.tex`
4. `references.bib`

The current draft intentionally contains `TODO` markers and cautious wording. Do not remove caution around OSM pseudo-history until the data becomes cleaner.

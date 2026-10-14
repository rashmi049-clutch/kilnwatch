"""
Compile the project technical report to PDF.

The .tex file is the source of record; the PDF is a build artifact and is not
committed. Run twice internally so the table of contents resolves.

Requires a LaTeX distribution on PATH. TinyTeX is installed on this machine;
see the message printed on failure for options.
"""

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEX = HERE / "ncr_kilns_report.tex"
OUT = HERE / "build"

ENGINES = ["pdflatex", "xelatex", "lualatex", "tectonic"]

INSTALL_HELP = """
No LaTeX engine found on PATH. Install one of:

  TinyTeX  (~100 MB, recommended)
      https://yihui.org/tinytex/
      Then: tlmgr install booktabs enumitem fancyhdr caption geometry

  MiKTeX   (Windows, installs packages on demand)
      https://miktex.org/download

Re-run this script once installed.
"""


def find_engine() -> str | None:
    for e in ENGINES:
        if shutil.which(e):
            return e
    return None


def main() -> int:
    if not TEX.exists():
        print(f"Missing source: {TEX}")
        return 1

    engine = find_engine()
    if engine is None:
        print(INSTALL_HELP.strip())
        return 2

    OUT.mkdir(exist_ok=True)
    print(f"Engine: {engine}")

    # tectonic resolves references itself; the latex engines need two passes.
    passes = 1 if engine == "tectonic" else 2
    for i in range(1, passes + 1):
        if engine == "tectonic":
            cmd = [engine, "--outdir", str(OUT), str(TEX)]
        else:
            cmd = [engine, "-interaction=nonstopmode", "-halt-on-error",
                   "-output-directory", str(OUT), str(TEX)]

        print(f"  pass {i}/{passes} ...", end=" ", flush=True)
        r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
        if r.returncode != 0:
            print("FAILED\n")
            # LaTeX buries the real error; surface the lines that matter.
            for line in r.stdout.splitlines():
                if line.startswith("!") or "Error" in line or "not found" in line:
                    print("   ", line)
            print(f"\nFull log: {OUT / TEX.with_suffix('.log').name}")
            return r.returncode
        print("ok")

    pdf = OUT / TEX.with_suffix(".pdf").name
    if pdf.exists():
        print(f"\nWrote {pdf}  ({pdf.stat().st_size / 1024:.0f} KB)")
        return 0

    print("\nEngine reported success but no PDF was produced.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

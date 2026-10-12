#!/usr/bin/env python3
"""Unpack a child-session batch tarball (+ optional report) into raw/."""
import os, sys, tarfile, tempfile, shutil, glob
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
def ingest(tgz, report=None, batch=None):
    batch = batch or os.path.basename(tgz).split("_output")[0]
    tmp = tempfile.mkdtemp()
    with tarfile.open(tgz) as t: t.extractall(tmp)
    n = {"transcripts": 0, "extractions": 0}
    for kind, pat in (("transcripts", "*.txt"), ("transcripts", "*.segments.json"), ("extractions", "*.json")):
        for f in glob.glob(os.path.join(tmp, "**", kind, pat), recursive=True):
            dst = os.path.join(ROOT, "raw", kind, os.path.basename(f))
            shutil.copy2(f, dst); n[kind] += 1
    if report:
        shutil.copy2(report, os.path.join(ROOT, "raw", "reports", f"{batch}_report.md"))
    shutil.rmtree(tmp); print(batch, n)
if __name__ == "__main__":
    ingest(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)

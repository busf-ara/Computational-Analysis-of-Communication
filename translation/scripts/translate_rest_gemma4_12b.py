# Translate the still-missing rows with gemma4-12b; each new record gets a "model" field.
import json, sys, io, contextlib
nb = json.load(open("translate_5k.ipynb")  # run from the translation/ folder)
codes = [''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code']
g = {}
with contextlib.redirect_stdout(io.StringIO()):
    for i in (0, 1, 2, 3):
        exec(codes[i], g)
g["MODEL"] = "gemma4-12b"
_orig = g["translate_row"]
def translate_row(row_id, text):
    rec = _orig(row_id, text)
    rec["model"] = "gemma4-12b"
    return rec
g["translate_row"] = translate_row
sample = g["sample"]
limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
todo = sample[~sample["row_id"].isin(g["done_ids"]())]
rows = todo.head(limit) if limit else sample
for attempt in range(4):
    if g["run_batch"](rows) and (limit or len(sample) - len(g["done_ids"]()) == 0):
        break
print("FINAL:", len(g["done_ids"]()), "/ 5000 translated")

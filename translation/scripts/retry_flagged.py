# Re-translate the rows in to_check_by_hand.xlsx with gemma4-12b, new seed per try; append passing results to the checkpoint.
import json, re, io, contextlib, pandas as pd
from concurrent.futures import ThreadPoolExecutor
nb = json.load(open("translate_5k.ipynb")  # run from the translation/ folder)
codes = [''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code']
g = {}
with contextlib.redirect_stdout(io.StringIO()):
    for i in (0, 1, 2, 3):
        exec(codes[i], g)
g["MODEL"] = "gemma4-12b"
P = re.compile(r"\[(?:Gruppe 1|andere Gruppe)\]", re.I)
sample = g["sample"].set_index("row_id")
ids = pd.read_excel("to_check_by_hand.xlsx").row_id.tolist()

def passes(text, rec):
    ph = sorted(m.lower() for m in P.findall(text)) == sorted(m.lower() for m in P.findall(rec["translation"] or ""))
    return rec["error"] is None and rec["json_ok"] and ph and rec["length_ok"]

def fix(rid):
    text = sample.loc[rid, "text_block"]
    best = None
    for seed in (124, 125, 126):
        g["SEED"] = seed  # read at call time; fine across threads since all tries in a round use the same order
        rec = g["translate_row"](rid, text)
        rec.update(model="gemma4-12b", seed=seed, retry=True)
        if passes(text, rec):
            return rec, True
        if rec["error"] is None and (best is None or abs(rec["length_ratio"] - 1) < abs(best["length_ratio"] - 1)):
            best = rec
    return best, False

with ThreadPoolExecutor(1) as ex:   # one at a time, so the SEED global is unambiguous
    out = list(ex.map(fix, ids))
fixed = [r for r, ok in out if ok]
with open("translation_checkpoint.jsonl", "a", encoding="utf-8") as f:
    for r in fixed:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"fixed {len(fixed)} of {len(ids)}")
print("still failing:", [r["row_id"] if r else None for r, ok in out if not ok])

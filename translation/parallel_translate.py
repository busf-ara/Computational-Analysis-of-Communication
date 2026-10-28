"""
Translate the 5k sample into English with the uni API, using parallel calls.

What it does
    1. Loads the 5,000 sampled paragraphs (sample_for_llm.jsonl, made by sample5k.ipynb).
    2. Sends each paragraph with the professor's translation prompt to gemma4-26b.
       Several requests are sent at the same time (MAX_WORKERS), like
       parallel_calls in bacchuss_lyaeus().
    3. Saves every answer immediately to a checkpoint file, so a crash or a
       server outage loses nothing; running the script again continues.
    4. Uses ONE model only: paragraphs translated earlier with another model
       (gemma4-12b) are translated again with gemma4-26b.
    5. Writes the final file with gemma4-26b translations only.

The request is the same as bacchuss sends it:
    system message = the professor's prompt
    user message   = "Text: '<paragraph>'"
    temperature 0, fixed seed, JSON mode, no reasoning.

Run (from the translation/ folder):
    export UNI_API_KEY=sk-...        # never write the key into this file
    python parallel_translate.py --test 20          # small test batch first
    python parallel_translate.py                    # all remaining paragraphs
    python parallel_translate.py --workers 4        # change parallel calls
"""

import argparse
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

# ---------------------------------------------------------------- settings
HOST = "https://maki.uni-mannheim.de/v1"
MODEL = "gemma4-26b"
TEMPERATURE = 0
SEED = 123
MAX_WORKERS = 8            # parallel calls; lower it if the server returns errors
TIMEOUT = 180              # seconds to wait for one answer
MAX_RETRIES = 3            # tries per paragraph before it is marked as an error
STOP_AFTER_ERRORS = 20     # pause the whole run if this many fail in a row

SAMPLE_FILE = "../sample_for_llm.jsonl"
CHECKPOINT_FILE = "translation_checkpoint.jsonl"
OUTPUT_XLSX = "sample_5k_translated.xlsx"
OUTPUT_JSONL = "sample_5k_translated.jsonl"

# The professor's translation prompt (ILIAS), unchanged.
PROMPT = """You are a careful and attentive translator for news articles.

You will receive a multiparagraph in this form:

Text: <multi-paragraph>

You are given a multi-paragraph from a news article and translate it into clear English.
Preserve names and numbers exactly, translate quotes as directly as possible.
Return only the translation.
Do not comment on the translation.

If paragraphs contain sentence fragments, assume it is a headline or image description. Translate them as sentence fragments as well. Maintain the paragraph structure.

Some entity names will be masked as [Gruppe 1] and [andere Gruppe]. Maintain those names.

Output Format:

Return only a valid JSON object:

{
  "label": "<translated text>"
}

No additional explanations, no Markdown, and no text outside the JSON."""

API_KEY = os.environ.get("UNI_API_KEY", "")
PLACEHOLDER = re.compile(r"\[(Gruppe 1|Andere Gruppe|andere Gruppe)\]")
_write_lock = threading.Lock()


# ---------------------------------------------------------------- one request
def call_llm(text):
    """Send one paragraph to the server and return the answer (with retries)."""
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": f"Text: '{text}'"},
        ],
        "temperature": TEMPERATURE,
        "seed": SEED,
        "reasoning_effort": "none",
        "response_format": {"type": "json_object"},
    }
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(
                f"{HOST}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}"},
                json=body,
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            j = r.json()
            return {
                "output": j["choices"][0]["message"]["content"].strip(),
                "tokens_prompt": j["usage"]["prompt_tokens"],
                "tokens_response": j["usage"]["completion_tokens"],
                "error": None,
            }
        except Exception as e:
            last_error = str(e)[:300]
            time.sleep(5 * attempt)            # wait a bit longer after each failure
    return {"output": None, "tokens_prompt": None, "tokens_response": None, "error": last_error}


def translate_row(row_id, text):
    """Translate one paragraph and run quick quality checks."""
    start = time.time()
    res = call_llm(text)
    raw = res["output"]
    try:
        translation, json_ok = json.loads(raw)["label"], True
    except Exception:
        translation, json_ok = raw, False
    de = sorted(p.lower() for p in PLACEHOLDER.findall(text))
    en = sorted(p.lower() for p in PLACEHOLDER.findall(translation or ""))
    ratio = len(translation or "") / max(len(text), 1)
    return {
        "row_id": row_id,
        "translation": translation,
        "raw_output": raw,
        "json_ok": json_ok,
        "placeholder_ok": de == en,          # [Gruppe 1] / [andere Gruppe] kept
        "length_ratio": round(ratio, 2),
        "length_ok": 0.75 <= ratio <= 1.25,   # nothing left out or added
        "tokens_prompt": res["tokens_prompt"],
        "tokens_response": res["tokens_response"],
        "seconds": round(time.time() - start, 1),
        "error": res["error"],
        "model": MODEL,
        "seed": SEED,
    }


# ---------------------------------------------------------------- checkpoint
def model_of(rec):
    return rec.get("model") or "gemma4-26b"   # early rows had no model field; they were 26b


def read_checkpoint():
    if not os.path.exists(CHECKPOINT_FILE):
        return []
    with open(CHECKPOINT_FILE, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def done_ids():
    """row_ids already translated successfully with the current MODEL."""
    return {r["row_id"] for r in read_checkpoint()
            if r["error"] is None and r["translation"] and model_of(r) == MODEL}


def save(rec):
    with _write_lock:                          # threads must not write at the same time
        with open(CHECKPOINT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- parallel run
def run_parallel(rows, workers):
    """Translate rows with `workers` requests at the same time. Returns False if paused."""
    todo = rows[~rows["row_id"].isin(done_ids())]
    print(f"To translate: {len(todo)} | already done with {MODEL}: {len(rows) - len(todo)} | parallel calls: {workers}")
    if todo.empty:
        return True

    t0, n, n_err, in_a_row = time.time(), 0, 0, 0
    pool = ThreadPoolExecutor(max_workers=workers)
    futures = [pool.submit(translate_row, r.row_id, r.text_block) for r in todo.itertuples()]
    try:
        for fut in as_completed(futures):      # results arrive in whatever order they finish
            rec = fut.result()
            save(rec)
            n += 1
            n_err += rec["error"] is not None
            in_a_row = in_a_row + 1 if rec["error"] else 0
            if in_a_row >= STOP_AFTER_ERRORS:
                print(f"{in_a_row} errors in a row: server seems down. Paused; run again later.")
                return False
            if n % 50 == 0 or n == len(todo):
                el = time.time() - t0
                print(f"{n}/{len(todo)} | errors {n_err} | {n / (el / 60):.1f} per min | "
                      f"~{el / n * (len(todo) - n) / 60:.0f} min left")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return True


def write_output(sample):
    recs = [r for r in read_checkpoint()
            if model_of(r) == MODEL and r["error"] is None and r["translation"]]
    for r in recs:
        r["model"] = model_of(r)
    res = pd.DataFrame(recs).drop_duplicates("row_id", keep="last")
    final = sample.merge(res, on="row_id", how="left")
    ok = final["translation"].notna()
    print(f"Translated with {MODEL}: {ok.sum()} / {len(final)}")
    print(f"[Gruppe 1] changed: {(final.placeholder_ok == False).sum()} | "
          f"length suspicious: {(final.length_ok == False).sum()}")
    final.to_excel(OUTPUT_XLSX, index=False)
    final.to_json(OUTPUT_JSONL, orient="records", lines=True, force_ascii=False)
    print(f"Saved {OUTPUT_XLSX} and {OUTPUT_JSONL}")


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", type=int, help="only translate this many paragraphs (test batch)")
    ap.add_argument("--workers", type=int, default=MAX_WORKERS, help="parallel calls")
    args = ap.parse_args()

    if not API_KEY:
        raise SystemExit("Set the API key first:  export UNI_API_KEY=sk-...")

    sample = pd.read_json(SAMPLE_FILE, lines=True)
    sample.insert(0, "row_id", range(len(sample)))

    rows = sample
    if args.test:
        rows = sample[~sample["row_id"].isin(done_ids())].head(args.test)

    finished = run_parallel(rows, args.workers)
    if finished and not args.test:
        write_output(sample)

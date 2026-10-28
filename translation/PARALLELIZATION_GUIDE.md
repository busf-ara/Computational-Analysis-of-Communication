# Parallel calls to the uni API in Python: a simple guide

**For:** everyone in the group who sends paragraphs to the uni AI (translation, warmth, cold).
**Same idea as:** `parallel_calls` in the professor's R function `bacchuss_lyaeus()`.

---

## 1. The idea in one picture

Without parallel calls, we send one paragraph, **wait** for the answer, then send the next one:

```
[par 1]--wait--[par 2]--wait--[par 3]--wait--[par 4] ...        5,000 x 2 s = ~3 hours
```

With parallel calls, we send **several paragraphs at the same time**, and the server works on them together:

```
[par 1]
[par 2]
[par 3]      <- 8 requests "in flight" at once
...
[par 8]                                                          ~8x faster (if the server can cope)
```

Most of the time is spent **waiting for the server**, not computing on our laptop. So we can easily wait for 8 answers at the same time.

---

## 2. The Python tool: `ThreadPoolExecutor`

Python has this built in (`concurrent.futures`), so there's nothing extra to install.

- A **pool** of *N* workers (threads), each of which sends one request and waits for it
- `pool.submit(function, arguments)` puts a job in the queue
- `as_completed(...)` gives us each answer **as soon as it is ready** (not in the original order)

---

## 3. Minimal example (copy this)

This example codes **warmth**, but it works for any prompt: just change `PROMPT` and the label you read from the JSON.

```python
import os, json, time
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

HOST    = "https://maki.uni-mannheim.de/v1"
MODEL   = "gemma4-26b"
API_KEY = os.environ["UNI_API_KEY"]        # never write the key into the code
WORKERS = 8                                # how many requests at the same time

PROMPT = "...our warmth prompt, asking for JSON: {\"explanation\": \"...\", \"label\": \"...\"}..."

def ask_llm(row_id, text):
    """Send ONE paragraph and return the answer. Each worker runs this."""
    body = {
        "model": MODEL,
        "messages": [{"role": "system", "content": PROMPT},
                     {"role": "user",   "content": f"Text: '{text}'"}],   # same as bacchuss
        "temperature": 0,
        "seed": 123,
        "reasoning_effort": "none",
        "response_format": {"type": "json_object"},                       # JSON mode
    }
    for attempt in range(3):                                              # retry on errors
        try:
            r = requests.post(f"{HOST}/chat/completions",
                              headers={"Authorization": f"Bearer {API_KEY}"},
                              json=body, timeout=180)
            r.raise_for_status()
            answer = json.loads(r.json()["choices"][0]["message"]["content"])
            return {"row_id": row_id, "label": answer.get("label"),
                    "explanation": answer.get("explanation"), "error": None}
        except Exception as e:
            error = str(e)
            time.sleep(5 * (attempt + 1))                                 # wait, then try again
    return {"row_id": row_id, "label": None, "explanation": None, "error": error}


df = pd.read_json("sample_5k_translated.jsonl", lines=True)               # our translated data

results = []
with ThreadPoolExecutor(max_workers=WORKERS) as pool:
    jobs = [pool.submit(ask_llm, r.row_id, r.translation) for r in df.itertuples()]
    for i, job in enumerate(as_completed(jobs), 1):                       # answers arrive here
        results.append(job.result())
        if i % 50 == 0:
            print(f"{i}/{len(jobs)} done")

out = df.merge(pd.DataFrame(results), on="row_id")                        # match by row_id!
out.to_excel("warmth_results.xlsx", index=False)
```

---

## 4. Important rules

| Rule | Why |
|---|---|
| **Always keep a `row_id`** and merge the results by it | Answers come back in a **random order** (whatever finishes first). |
| **Start with a small test** (e.g. 20 paragraphs) | Check the output **before** sending 5,000 requests. |
| **Don't use too many workers** (start with 4–8) | The server is **shared by the whole course**. Too many → queue timeouts / `504` errors for everyone. |
| **If you see many errors, lower `WORKERS`** | Errors mean the server is overloaded. |
| **Save results as you go** (see `parallel_translate.py`) | If the laptop sleeps or the server goes down, you don't lose hours of work. |
| **Use one model for the whole dataset** (`gemma4-26b`) | Mixing models makes the results not comparable (professor's request). |
| **Never put the API key in the code / on GitHub** | Use `export UNI_API_KEY=sk-...` in the terminal, or `getpass`. |

---

## 5. How many workers is best?

It depends on how busy the server is. Measure it: run 3 rounds each with 2, 4, 8, 12 and 16 workers, and compare **paragraphs per minute**. Take the fastest setting that gives **no errors**. `translate_5k.ipynb` (STEP 4b) does this automatically.

---

## 6. Our full version

`translation/parallel_translate.py` is the complete translation script with everything above, plus:
- a **checkpoint file**, so that running it again continues where it stopped
- an **automatic pause** if the server fails 20 times in a row
- **quality checks** (JSON valid, `[Gruppe 1]` kept, length OK)
- **one model only**: rows made with another model are redone with `gemma4-26b`

```bash
export UNI_API_KEY=sk-...
cd translation
python parallel_translate.py --test 20      # test batch
python parallel_translate.py                # everything that is left
python parallel_translate.py --workers 4    # fewer parallel calls if the server struggles
```

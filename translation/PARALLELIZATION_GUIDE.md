# Parallel calls in Python: quick guide

## What is it?

**Normal:** send 1 paragraph → wait for the answer → send the next. Slow.

**Parallel:** send **several paragraphs at the same time** (e.g. 8). The server works on them together, so it's about **8× faster**.

Same idea as `parallel_calls` in the professor's `bacchuss_lyaeus()`.

## How to do it

Python's `ThreadPoolExecutor` does it, with nothing to install:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def ask_llm(row_id, text):
    # send ONE paragraph to the uni API and return {"row_id": ..., "label": ...}
    ...

with ThreadPoolExecutor(max_workers=8) as pool:                  # 8 at the same time
    jobs = [pool.submit(ask_llm, r.row_id, r.text) for r in df.itertuples()]
    results = [job.result() for job in as_completed(jobs)]

df = df.merge(pd.DataFrame(results), on="row_id")                # put answers back
```

That's it: you write a function for **one** paragraph, and the pool runs it for all of them in parallel.

## 3 rules

1. **Keep a `row_id`.** Answers come back in random order, so merge them by `row_id`.
2. **Start with 4–8 workers.** The server is shared; too many gives `504` errors. Lower it if you get errors.
3. **Test on 20 paragraphs first**, then run everything.

Full working example: `translation/parallel_translate.py`

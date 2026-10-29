# Translation of the 5k sample

All 5,000 sampled paragraphs (`sample5k.ipynb`, `random_state=123`) were sent to the uni API
with the professor's translation prompt, using **one model: gemma4-26b**
(temperature 0, seed 123, JSON mode, 2 parallel calls).

## Result (29 Oct 2026)

| | rows |
|---|---|
| translated with gemma4-26b | 4,976 |
| not translated (server kept timing out, left out) | 24 |
| flagged for a manual check (placeholder or length) | 61 |

The output files hold data, so they are **not on GitHub** (see `.gitignore`):

- `sample_5k_translated.xlsx` / `.jsonl`: all 5,000 rows; `translation` is empty for the 24 missing ones
- `to_check_by_hand.xlsx`: sheet `not_translated` (the 24) and sheet `flagged` (the 61)

## Files

- `parallel_translate.py`: the script that did the translation (parallel calls, checkpoint/resume)
- `translate_5k.ipynb`: the same steps as a notebook, plus a test batch and a speed test
- `PARALLELIZATION_GUIDE.md`: short guide for the team
- `How_the_API_and_bacchuss_work.md`, `translation_test.ipynb`: first one-paragraph test

To translate the 24 missing rows later: `export UNI_API_KEY=...` and run `python parallel_translate.py --workers 2`.
It skips everything that is already done.

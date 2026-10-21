# How the API and bacchuss work: simple flow

## The idea in 3 lines

- The university has an **AI model** on its server (`gemma4-26b`).
- An **API** lets us send it a message and get an answer back.
- **bacchuss** (R) is just a helper that sends these messages for us. **Python can send the same message**, so we don't need R.

---

## The flow

**1. We prepare two things**
- **Prompt** = the instructions (e.g. the professor's translation prompt, or our warmth codebook)
- **Paragraph** = the news text, e.g. `Text: 'Duell zweier Eigengewächse…'`

⬇

**2. We send them to the uni server**
- Address: `maki.uni-mannheim.de`
- Model: `gemma4-26b`
- API key: the password from `Howto.rmd` (keep it private)

⬇

**3. The AI reads the prompt and the paragraph**

⬇

**4. The AI sends back an answer in JSON**
- Translation: `{"label": "Duel of two home-grown talents…"}`
- Warmth coding: `{"explanation": "…", "label": "…"}`

⬇

**5. We save the answer in a table (Excel)**

---

## bacchuss vs. Python

| | bacchuss (R) | Our notebook (Python) |
|---|---|---|
| Sends to | uni server | **same** uni server |
| Message | prompt + paragraph | **same** prompt + paragraph |
| Answer | JSON | **same** JSON |

**→ Same request, same result. We use Python.**

---

## In our project

The flow is always the same. **Only the prompt changes:**

1. **Translate**: professor's translation prompt → English text
2. **Code warmth**: our warmth prompt → warm or not
3. **Code cold**: our cold prompt → cold or not

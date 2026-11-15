"""
Compare two prompts (e.g. explicit vs implicit) on the same 5k paragraphs and
collect the paragraphs where they disagree, so the team can label them by hand.

Each input is an annotated Excel file with at least: row_id, label, explanation.
Warm and cold are compared separately; each needs two files (prompt A and B).

Run (from the disagreements/ folder):
    python compare_prompts.py --warm data/explicit.xlsx data/implicit.xlsx
    python compare_prompts.py --warm W_A.xlsx W_B.xlsx --cold C_A.xlsx C_B.xlsx
    python compare_prompts.py --warm W_A.xlsx W_B.xlsx --names explicit implicit

Output: prompt_disagreements.xlsx
    Summary            how often the two prompts agree, per dimension
    Warm disagreements one row per paragraph where the warm labels differ: both labels,
                       both explanations, text and group; every other input column is kept but hidden
    Cold disagreements the same for cold (only if cold files are given)
    All labels         every paragraph with every prompt's label, side by side
"""

import argparse

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

OUTPUT = "prompt_disagreements.xlsx"


def to_bool(x):
    """Labels come as True/False, 'TRUE'/'FALSE' or 1/0; anything else is missing."""
    s = str(x).strip().upper()
    return True if s in ("TRUE", "1", "1.0") else False if s in ("FALSE", "0", "0.0") else None


def load(path, dim, name):
    d = pd.read_excel(path)
    return d.drop_duplicates("row_id", keep="last")


def compare(dim, path_a, path_b, a, b):
    da, db = load(path_a, dim, a), load(path_b, dim, b)
    m = da.merge(db, on="row_id", how="outer", suffixes=(f" [{a}]", f" [{b}]"))
    # A column that is identical in both files (text, group, ...) is kept once; the rest keep one copy per prompt.
    for c in [c for c in da.columns if c not in ("row_id", "label", "explanation") and c in db.columns]:
        ca, cb = f"{c} [{a}]", f"{c} [{b}]"
        if m[ca].fillna("<NA>").astype(str).equals(m[cb].fillna("<NA>").astype(str)):
            m = m.drop(columns=cb).rename(columns={ca: c})
    la, lb = m[f"label [{a}]"].map(to_bool), m[f"label [{b}]"].map(to_bool)
    m[f"{a} label"], m[f"{b} label"] = la.map({True: "TRUE", False: "FALSE"}), lb.map({True: "TRUE", False: "FALSE"})
    both = la.notna() & lb.notna()
    agree = (la == lb).where(both)
    stats = {
        "Dimension": dim,
        f"Rows in {a}": int(la.notna().sum()),
        f"Rows in {b}": int(lb.notna().sum()),
        "Rows in both": int(both.sum()),
        f"TRUE by {a}": int((la == True).sum()),
        f"TRUE by {b}": int((lb == True).sum()),
        "Both TRUE": int(((la == True) & (lb == True)).sum()),
        "Both FALSE": int(((la == False) & (lb == False)).sum()),
        f"Only {a} TRUE": int(((la == True) & (lb == False)).sum()),
        f"Only {b} TRUE": int(((la == False) & (lb == True)).sum()),
        "Disagreements": int((agree == False).sum()),
        "Agreement %": round(100 * (agree == True).sum() / max(both.sum(), 1), 1),
    }
    m["Disagreement"] = la.map({True: f"{a} TRUE / {b} FALSE", False: f"{a} FALSE / {b} TRUE"}).where(agree == False)
    m[f"Why {a}"], m[f"Why {b}"] = m[f"explanation [{a}]"], m[f"explanation [{b}]"]
    shown = ["row_id", "group", f"{a} label", f"{b} label", "Disagreement", "translation", f"Why {a}", f"Why {b}"]
    coders = ["Hamid", "Omar", "Ara", "Arhan", "Final label (team)", "Edge case? (Y/N)", "Note"]
    dis = m[agree == False].copy()
    for c in coders:
        dis[c] = None
    rest = [c for c in m.columns if c not in shown and c not in (f"explanation [{a}]", f"explanation [{b}]")]
    dis = dis[shown + coders + rest].sort_values(["Disagreement", "row_id"])
    dis = dis.rename(columns={"translation": "Paragraph (English)"})
    alllab = m[["row_id", "group", f"{a} label", f"{b} label"]].assign(**{f"{dim}_agree": agree})
    alllab = alllab.rename(columns={f"{a} label": f"{dim} {a}", f"{b} label": f"{dim} {b}"})
    return alllab, dis, stats, len(shown) + len(coders)


def style(ws, n_rows, label_cols, n_visible):
    head = PatternFill("solid", fgColor="1F4E78")
    todo = PatternFill("solid", fgColor="FFF9DB")
    wrap = Alignment(wrap_text=True, vertical="top")
    widths = {"A": 7, "B": 8, "C": 10, "D": 10, "E": 24, "F": 70, "G": 45, "H": 45}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    for c in ws[1]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), head
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = wrap
    tf = DataValidation(type="list", formula1='"TRUE,FALSE"', allow_blank=True)
    yn = DataValidation(type="list", formula1='"Y,N"', allow_blank=True)
    ws.add_data_validation(tf)
    ws.add_data_validation(yn)
    for i, col in enumerate(label_cols):
        letter = ws.cell(1, n_visible - len(label_cols) + 1 + i).column_letter
        ws.column_dimensions[letter].width = 11 if i < 5 else 30
        for r in range(2, n_rows + 2):
            ws[f"{letter}{r}"].fill = todo
        (tf if i < 5 else yn if i == 5 else None) and (tf if i < 5 else yn).add(f"{letter}2:{letter}{n_rows + 1}")
    for j in range(n_visible + 1, ws.max_column + 1):  # all other columns: hidden, not removed
        ws.column_dimensions[ws.cell(1, j).column_letter].hidden = True
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--warm", nargs=2, metavar=("PROMPT_A", "PROMPT_B"))
    ap.add_argument("--cold", nargs=2, metavar=("PROMPT_A", "PROMPT_B"))
    ap.add_argument("--names", nargs=2, default=["explicit", "implicit"], help="names of prompt A and B")
    args = ap.parse_args()
    if not (args.warm or args.cold):
        raise SystemExit("Give at least --warm A B or --cold A B")
    a, b = args.names

    merged, sheets, summary, visible = None, {}, [], {}
    for dim, paths in (("warm", args.warm), ("cold", args.cold)):
        if not paths:
            continue
        m, dis, stats, n_visible = compare(dim, paths[0], paths[1], a, b)
        visible[dim] = n_visible
        sheets[f"{dim.capitalize()} disagreements"] = dis
        summary.append(stats)
        merged = m if merged is None else merged.merge(m.drop(columns="group"), on="row_id", how="outer")
        print(f"{dim}: {stats['Disagreements']} disagreements, agreement {stats['Agreement %']}%")

    with pd.ExcelWriter(OUTPUT, engine="openpyxl") as w:
        pd.DataFrame(summary).set_index("Dimension").T.to_excel(w, sheet_name="Summary")
        for name, d in sheets.items():
            d.to_excel(w, sheet_name=name, index=False)
            style(w.sheets[name], len(d), ["Hamid", "Omar", "Ara", "Arhan", "Final label (team)", "Edge case? (Y/N)", "Note"],
                  visible[name.split()[0].lower()])
        merged.sort_values("row_id").to_excel(w, sheet_name="All labels", index=False)
        w.sheets["Summary"].column_dimensions["A"].width = 24
    print(f"Saved {OUTPUT}")

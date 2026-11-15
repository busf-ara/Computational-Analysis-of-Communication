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
    Warm disagreements one row per paragraph where the warm labels differ
    Cold disagreements the same for cold (only if cold files are given)
    All labels         every paragraph with every prompt's label, side by side
"""

import argparse

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

TEXT_COLS = ["row_id", "article_id", "pub", "group", "translation", "text_block"]
OUTPUT = "prompt_disagreements.xlsx"


def to_bool(x):
    """Labels come as True/False, 'TRUE'/'FALSE' or 1/0; anything else is missing."""
    s = str(x).strip().upper()
    return True if s in ("TRUE", "1", "1.0") else False if s in ("FALSE", "0", "0.0") else None


def load(path, dim, name):
    d = pd.read_excel(path)
    d = d.drop_duplicates("row_id", keep="last")
    d[f"{dim}_{name}"] = d["label"].map(to_bool)
    d[f"{dim}_{name}_why"] = d["explanation"]
    return d


def compare(dim, path_a, path_b, a, b):
    da, db = load(path_a, dim, a), load(path_b, dim, b)
    keep = [c for c in TEXT_COLS if c in da.columns]
    m = da[keep + [f"{dim}_{a}", f"{dim}_{a}_why"]].merge(
        db[["row_id", f"{dim}_{b}", f"{dim}_{b}_why"]], on="row_id", how="outer")
    la, lb = m[f"{dim}_{a}"], m[f"{dim}_{b}"]
    both = la.notna() & lb.notna()
    m[f"{dim}_agree"] = (la == lb).where(both)
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
        "Disagreements": int((m[f"{dim}_agree"] == False).sum()),
        "Agreement %": round(100 * (m[f"{dim}_agree"] == True).sum() / max(both.sum(), 1), 1),
    }
    dis = m[m[f"{dim}_agree"] == False].copy()
    dis.insert(1, "Which prompt said TRUE", dis[f"{dim}_{a}"].map({True: f"only {a}", False: f"only {b}"}))
    dis = dis.sort_values(["Which prompt said TRUE", "row_id"])
    dis = dis[["row_id", "Which prompt said TRUE", "group", "pub", "translation",
               f"{dim}_{a}_why", f"{dim}_{b}_why", "text_block", "article_id"]]
    dis = dis.rename(columns={"translation": "Paragraph (English)", "text_block": "German original",
                              f"{dim}_{a}_why": f"Why {a} said {'TRUE/FALSE'}",
                              f"{dim}_{b}_why": f"Why {b} said {'TRUE/FALSE'}"})
    for c in ["Hamid", "Omar", "Ara", "Arhan", "Final label (team)", "Edge case? (Y/N)", "Note"]:
        dis[c] = None
    return m, dis, stats


def style(ws, n_rows, label_cols):
    head = PatternFill("solid", fgColor="1F4E78")
    todo = PatternFill("solid", fgColor="FFF9DB")
    wrap = Alignment(wrap_text=True, vertical="top")
    widths = {"A": 7, "B": 14, "C": 8, "D": 12, "E": 70, "F": 45, "G": 45, "H": 50, "I": 12}
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
        letter = ws.cell(1, ws.max_column - len(label_cols) + 1 + i).column_letter
        ws.column_dimensions[letter].width = 11 if i < 5 else 30
        for r in range(2, n_rows + 2):
            ws[f"{letter}{r}"].fill = todo
        (tf if i < 5 else yn if i == 5 else None) and (tf if i < 5 else yn).add(f"{letter}2:{letter}{n_rows + 1}")
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

    merged, sheets, summary = None, {}, []
    for dim, paths in (("warm", args.warm), ("cold", args.cold)):
        if not paths:
            continue
        m, dis, stats = compare(dim, paths[0], paths[1], a, b)
        sheets[f"{dim.capitalize()} disagreements"] = dis
        summary.append(stats)
        merged = m if merged is None else merged.merge(m.drop(columns=[c for c in TEXT_COLS if c != "row_id" and c in m]), on="row_id", how="outer")
        print(f"{dim}: {stats['Disagreements']} disagreements, agreement {stats['Agreement %']}%")

    with pd.ExcelWriter(OUTPUT, engine="openpyxl") as w:
        pd.DataFrame(summary).set_index("Dimension").T.to_excel(w, sheet_name="Summary")
        for name, d in sheets.items():
            d.to_excel(w, sheet_name=name, index=False)
            style(w.sheets[name], len(d), ["Hamid", "Omar", "Ara", "Arhan", "Final label (team)", "Edge case? (Y/N)", "Note"])
        merged.sort_values("row_id").to_excel(w, sheet_name="All labels", index=False)
        w.sheets["Summary"].column_dimensions["A"].width = 24
    print(f"Saved {OUTPUT}")

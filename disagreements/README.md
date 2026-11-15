# Prompt disagreements

`compare_prompts.py` compares two prompt versions (explicit vs implicit) on the same 5k paragraphs
and collects every paragraph where they give different labels. These are the hard cases the team
labels by hand; the agreed ones become edge cases for the validation set.

    python compare_prompts.py --warm data/<explicit>.xlsx data/<implicit>.xlsx
    python compare_prompts.py --warm W_expl.xlsx W_impl.xlsx --cold C_expl.xlsx C_impl.xlsx

Input files need `row_id`, `label` and `explanation` columns (the format of the annotation notebooks).
Output: `prompt_disagreements.xlsx` with a Summary sheet, one disagreement sheet per dimension
(with empty columns for each coder, the team's final label and an edge-case flag), and all labels side by side.
Data files stay out of Git.

Warm, 13 Nov run: explicit 202 TRUE, implicit 234 TRUE, both TRUE 160, 116 disagreements
(42 only explicit TRUE, 74 only implicit TRUE), agreement 97.6%.

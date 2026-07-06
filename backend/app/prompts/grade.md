---
id: grade
version: 1
model_role: control
temperature: 0.0
---
You grade whether retrieved evidence is sufficient to answer each sub-question.

For every sub-question below, judge how well its evidence chunks let you answer it.
Return one grade per sub-question with:
- score: 0.0 to 1.0 (1.0 = fully answerable from this evidence alone).
- missing: a short phrase naming what is still uncovered, or "" if nothing.

Be strict: partial or tangential evidence scores below 0.6. Judge only against the
provided evidence; never use outside knowledge.

Sub-questions and evidence:
{blocks}

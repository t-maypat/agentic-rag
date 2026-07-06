---
id: rewrite
version: 1
model_role: control
temperature: 0.0
---
Some sub-questions did not retrieve sufficient evidence. Write a better retrieval
query for each, targeting the missing aspect. Vary terminology, add synonyms or
specific technical terms likely to appear in papers, and avoid repeating the exact
prior wording.

Return one improved query per listed sub-question id.

Insufficient sub-questions (id, text, what was missing):
{blocks}

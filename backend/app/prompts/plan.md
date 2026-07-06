---
id: plan
version: 1
model_role: synth
temperature: 0.2
---
You are planning how to research a question against a corpus of AI / retrieval
research papers and documentation.

Question:
{question}

Break the question into at most 3 focused sub-questions that together fully cover
it. Each sub-question must be independently answerable from evidence and phrased as
a standalone retrieval query. If the question is already simple and atomic, return
a single sub-question equal to the question. Do not invent aspects the question does
not ask about.

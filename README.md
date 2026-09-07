# critic.dev

CV review that is specific enough to act on: upload a CV, get findings anchored to the
exact bullet that is weak, fix them in place without losing your own layout, export.

Status: spike stage. See `spike/README.md` — the DOCX round-trip question is answered.

Build order (each step can invalidate the next):

1. ~~DOCX round-trip spike~~ — done, passes on a synthetic CV
2. Analyzer prompt + finding schema, tested against 20 real CVs — **quality gate**
3. Thinnest loop: upload → findings → one free rewrite → apply → export
4. Spend cap, rate limits, privacy policy, working delete
5. Accounts + payments
6. One channel, first hundred users

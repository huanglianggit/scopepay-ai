# Submission drafting material

Status: preparation only. On October 29, 2026, real SiliconFlow model analysis and a USD 99 PayPal Sandbox capture were verified. The current copy-ready submission kit is in `output/submission-2026-10-29/`; see `docs/verification-2026-10-29.md` for verification scope. Public source publication, judging access and a public video remain unfinished. This file is not a submission receipt.

## Project name

ScopePay AI

## Elevator pitch

Turn client requests into source-backed change orders, clear approvals, and PayPal payments—so freelancers and clients agree on what comes next.

## Inspiration

A short client message can add a new deliverable, revision round or deadline. We wanted a focused workflow that connects that conversation to an explicit scope and fee both parties can review.

## What it does

ScopePay compares a client request with the agreed project scope and previously confirmed additions. It surfaces cited changes and clarification questions, prepares editable fee items, and gives the studio control over what becomes a quote. Publication freezes the version. A private client page records acceptance or a revision request and supports PayPal Sandbox checkout. A downloadable record connects the sources, clarification, accepted version and payment outcome.

## How it is built

React and TypeScript power the studio and client screens. FastAPI validates input and state transitions. SQLite persists projects, version snapshots, confirmations and activity. The model adapter accepts OpenAI-compatible endpoints or local Ollama. PayPal Sandbox orders and captures are reconciled with the server-side quote; signed webhooks can recover completed captures.

## Differentiation to demonstrate

Exact source citations, explicit ambiguity handling, version-bound client approval and payment, and a portable record. No claim of market-first invention, measured savings, model accuracy or user adoption has been established.

## Built with

React, TypeScript, Vite, Python, FastAPI, SQLite, PayPal Orders API, PayPal Webhooks, Lucide. Add the actual model/provider used in the verified submission. AI coding assistance was used during development.

## Final submission checklist

- [x] Verify a real model call with a new request, not only a rule example.
- [x] Verify PayPal Sandbox buyer approval and completed capture against the locked quote (USD 99).
- [ ] Optionally corroborate the capture in the seller dashboard; server-side order/capture matching is already verified.
- [ ] Verify cancellation, retries, version matching and access instructions in the actual hosted or reproducible build.
- [ ] Publish source, LICENSE, setup instructions and a secret-free configuration example.
- [ ] Supply working build access and test instructions to judges.
- [ ] Record an under-three-minute English/translated demo and upload publicly to YouTube.
- [ ] Fill the Devpost form, review updated official rules and submit before the deadline.

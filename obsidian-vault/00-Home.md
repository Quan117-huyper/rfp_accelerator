# AI Proposal Generation & Solution Architect Agent
This vault is the project map for the proposal-only version of the app.

## Start Here

- [[10-Scope]]
- [[15-Project-Structure]]
- [[20-System-Map]]
- [[30-Backend-Modules]]
- [[40-Frontend-Modules]]
- [[50-Provider-Options]]
- [[60-Runbook]]
- [[70-Backlog]]

## One-Line Summary

Turn a customer requirement document into extracted requirements, clarification questions, a draft solution proposal, and a PowerPoint deck.

## Current Build

- Proposal analysis lives in `backend/proposal_app.py`.
- Requirement extraction and proposal generation live in `backend/proposal_agent.py`.
- PPTX export lives in `backend/ppt_renderer.py`.
- The frontend is centered on `front-end/src/pages/SolutionArchitectProposalPage.js`.
- Gemini is optional, and the local fallback keeps the demo usable without an API key.

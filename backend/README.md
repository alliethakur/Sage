---
title: Sage Backend
emoji: 🌿
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# Sage backend

Flask API for [Sage](https://github.com/alliethakur/Sage), a document chatbot
(PDF / TXT / CSV) with hybrid retrieval, LangGraph routing and chunk-level citations.

This folder is deployed to Hugging Face Spaces as a Docker app. The Groq API key is
set as a Space secret (`GROQ_API_KEY`), never stored in the code.

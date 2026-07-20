# System Design Fundamentals

This starter document exists so the RAG pipeline has a real corpus to ingest and test.

## URL Shortener

A URL shortener needs:
- a write path to create a short code
- a read path to resolve the short code
- a cache to absorb repeated lookups
- a durable database to store mappings

At scale, the read path should be optimized for latency and the write path should avoid collisions.

## Notification System

A notification system usually needs:
- an API layer for incoming requests
- a queue for buffering spikes
- worker services for delivery
- retries and dead-letter handling

The system should be designed so transient downstream failures do not drop messages permanently.

## General Guidance

When building distributed systems, prefer:
- stateless services where possible
- explicit data ownership
- observability
- graceful degradation
- idempotent processing for retries

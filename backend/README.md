# LLM Scraper

A full-stack web scraper built for LLM ingestion pipelines with:

- Domain crawling (Scrapy + Playwright)
- Content extraction & cleaning
- Keyword generation
- Vector embedding (FAISS)
- Full-text metadata (PostgreSQL)
- Ontology graph creation
- React UI dashboard

## Features

- Crawl any domain
- Extract text, metadata, links
- Chunk for LLMs
- Store vectors in FAISS
- Save metadata in PostgreSQL
- Semantic keyword extraction
- Diff-based change monitoring (coming soon)
- Ontology graph building
- Configurable output formats
- Export destinations (currently PostgreSQL)

## Setup

```bash
docker-compose up --build

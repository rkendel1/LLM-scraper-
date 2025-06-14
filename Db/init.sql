CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE,
    title TEXT,
    description TEXT,
    text TEXT NOT NULL,
    keywords TEXT[],
    embedding VECTOR(384),
    pdf_paths TEXT[],
    source_type TEXT NOT NULL DEFAULT 'web',
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_embedding ON documents USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
CREATE INDEX idx_source_type ON documents(source_type);
CREATE INDEX idx_keywords ON documents USING GIN(keywords);
CREATE INDEX idx_url ON documents(url);

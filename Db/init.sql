CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    description TEXT,
    text TEXT,
    keywords TEXT[],
    embedding VECTOR(384),  -- Dimension matches all-MiniLM-L6-v2
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_url ON documents(url);
CREATE INDEX idx_keywords ON documents USING GIN(keywords);
CREATE INDEX idx_embedding ON documents USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);

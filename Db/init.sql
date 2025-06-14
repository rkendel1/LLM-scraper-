-- Main document storage
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,        -- 'web', 'pdf', 'manual', 'api'
    source_id TEXT,                   -- URL, file path, or user ID
    title TEXT,
    description TEXT,
    text TEXT NOT NULL,
    keywords TEXT[],
    embedding VECTOR(384),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Store associated files like PDFs
CREATE TABLE document_files (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,          -- 'original_pdf', 'filled_pdf', 'txt', etc.
    uploaded_at TIMESTAMP DEFAULT NOW()
);

-- For graph relationships
CREATE TABLE document_relations (
    id SERIAL PRIMARY KEY,
    from_doc_id INTEGER REFERENCES documents(id),
    to_doc_id INTEGER REFERENCES documents(id),
    relation_type TEXT DEFAULT 'linked',
    weight FLOAT DEFAULT 1.0
);

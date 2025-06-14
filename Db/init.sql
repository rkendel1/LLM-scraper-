-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Main documents table
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE,
    title TEXT,
    description TEXT,
    text TEXT NOT NULL,
    keywords TEXT[],
    embedding VECTOR(384),
    pdf_paths TEXT[],
    source_type TEXT DEFAULT 'web',
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for documents
CREATE INDEX idx_url ON documents(url);
CREATE INDEX idx_keywords ON documents USING GIN(keywords);
CREATE INDEX idx_embedding ON documents USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);

-- Users table with profile storage
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    profile JSONB DEFAULT '{}'::JSONB,
    role TEXT DEFAULT 'anonymous', -- anonymous, registered, verified
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for user lookup
CREATE INDEX idx_user_email ON users(email);

-- User query history
CREATE TABLE user_queries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT,
    sources JSONB,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Optional: For storing chat sessions or threads
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    session_id TEXT NOT NULL,
    messages JSONB,
    title TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for session retrieval
CREATE INDEX idx_session_id ON user_sessions(session_id);

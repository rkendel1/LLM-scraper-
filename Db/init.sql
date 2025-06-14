-- Existing tables
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

-- New tables for user profiles
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE,
    password_hash TEXT,
    profile JSONB DEFAULT '{}',
    role TEXT DEFAULT 'anonymous',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_queries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    response TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
);

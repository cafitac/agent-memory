PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    adapter TEXT,
    external_ref TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    content TEXT NOT NULL,
    checksum TEXT NOT NULL UNIQUE,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_ref TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_ref_or_value TEXT NOT NULL,
    evidence_ids_json TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.5,
    valid_from TEXT,
    valid_to TEXT,
    scope TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('candidate', 'approved', 'disputed', 'deprecated')) DEFAULT 'candidate',
    searchable_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at TEXT,
    last_accessed_at TEXT,
    retrieval_count INTEGER NOT NULL DEFAULT 0,
    reinforcement_count REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS procedures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    trigger_context TEXT NOT NULL,
    preconditions_json TEXT NOT NULL,
    steps_json TEXT NOT NULL,
    evidence_ids_json TEXT NOT NULL,
    success_rate REAL NOT NULL DEFAULT 0.0,
    scope TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('candidate', 'approved', 'disputed', 'deprecated')) DEFAULT 'candidate',
    searchable_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at TEXT,
    last_accessed_at TEXT,
    retrieval_count INTEGER NOT NULL DEFAULT 0,
    reinforcement_count REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    started_at TEXT,
    ended_at TEXT,
    source_ids_json TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    importance_score REAL NOT NULL DEFAULT 0.0,
    scope TEXT NOT NULL DEFAULT 'global',
    status TEXT NOT NULL CHECK (status IN ('candidate', 'approved', 'disputed', 'deprecated')) DEFAULT 'candidate',
    searchable_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at TEXT,
    last_accessed_at TEXT,
    retrieval_count INTEGER NOT NULL DEFAULT 0,
    reinforcement_count REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_ref TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    to_ref TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    evidence_ids_json TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.5,
    valid_from TEXT,
    valid_to TEXT
);

CREATE TABLE IF NOT EXISTS memory_status_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_type TEXT NOT NULL CHECK (memory_type IN ('fact', 'procedure', 'episode')),
    memory_id INTEGER NOT NULL,
    from_status TEXT NOT NULL CHECK (from_status IN ('candidate', 'approved', 'disputed', 'deprecated')),
    to_status TEXT NOT NULL CHECK (to_status IN ('candidate', 'approved', 'disputed', 'deprecated')),
    reason TEXT,
    actor TEXT,
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS retrieval_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    surface TEXT NOT NULL,
    query_sha256 TEXT NOT NULL,
    query_preview TEXT,
    preferred_scope TEXT,
    limit_value INTEGER NOT NULL,
    statuses_json TEXT NOT NULL DEFAULT '["approved"]',
    retrieved_memory_refs_json TEXT NOT NULL DEFAULT '[]',
    top_memory_ref TEXT,
    response_mode TEXT CHECK (response_mode IN ('direct', 'cautious', 'verify_first')),
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS experience_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    surface TEXT NOT NULL,
    event_kind TEXT NOT NULL,
    scope TEXT,
    session_ref TEXT,
    content_sha256 TEXT NOT NULL,
    summary TEXT,
    salience REAL NOT NULL DEFAULT 0.0,
    user_emphasis REAL NOT NULL DEFAULT 0.0,
    related_memory_refs_json TEXT NOT NULL DEFAULT '[]',
    related_observation_ids_json TEXT NOT NULL DEFAULT '[]',
    retention_policy TEXT NOT NULL CHECK (retention_policy IN ('ephemeral', 'short', 'review', 'archive')) DEFAULT 'ephemeral',
    expires_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_memory_status_transitions_memory ON memory_status_transitions(memory_type, memory_id, id);
CREATE INDEX IF NOT EXISTS idx_retrieval_observations_created_at ON retrieval_observations(created_at, id);
CREATE INDEX IF NOT EXISTS idx_retrieval_observations_surface ON retrieval_observations(surface, created_at);
CREATE INDEX IF NOT EXISTS idx_experience_traces_created_at ON experience_traces(created_at, id);
CREATE INDEX IF NOT EXISTS idx_experience_traces_surface_kind ON experience_traces(surface, event_kind, created_at);

CREATE INDEX IF NOT EXISTS idx_facts_status_scope ON facts(status, scope);
CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject_ref);
CREATE INDEX IF NOT EXISTS idx_procedures_status_scope ON procedures(status, scope);
CREATE INDEX IF NOT EXISTS idx_procedures_name ON procedures(name);
CREATE INDEX IF NOT EXISTS idx_episodes_status_scope_importance ON episodes(status, scope, importance_score);
CREATE INDEX IF NOT EXISTS idx_episodes_title ON episodes(title);
CREATE INDEX IF NOT EXISTS idx_relations_from_to ON relations(from_ref, to_ref);
CREATE INDEX IF NOT EXISTS idx_relations_to_ref ON relations(to_ref);
CREATE INDEX IF NOT EXISTS idx_relations_type_refs ON relations(relation_type, from_ref, to_ref);

CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    searchable_text,
    content='facts',
    content_rowid='id'
);

CREATE VIRTUAL TABLE IF NOT EXISTS procedures_fts USING fts5(
    searchable_text,
    content='procedures',
    content_rowid='id'
);

CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
    searchable_text,
    content='episodes',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, searchable_text)
    VALUES (new.id, new.searchable_text);
END;

CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, searchable_text)
    VALUES('delete', old.id, old.searchable_text);
END;

CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, searchable_text)
    VALUES('delete', old.id, old.searchable_text);
    INSERT INTO facts_fts(rowid, searchable_text)
    VALUES (new.id, new.searchable_text);
END;

CREATE TRIGGER IF NOT EXISTS procedures_ai AFTER INSERT ON procedures BEGIN
    INSERT INTO procedures_fts(rowid, searchable_text)
    VALUES (new.id, new.searchable_text);
END;

CREATE TRIGGER IF NOT EXISTS procedures_ad AFTER DELETE ON procedures BEGIN
    INSERT INTO procedures_fts(procedures_fts, rowid, searchable_text)
    VALUES('delete', old.id, old.searchable_text);
END;

CREATE TRIGGER IF NOT EXISTS procedures_au AFTER UPDATE ON procedures BEGIN
    INSERT INTO procedures_fts(procedures_fts, rowid, searchable_text)
    VALUES('delete', old.id, old.searchable_text);
    INSERT INTO procedures_fts(rowid, searchable_text)
    VALUES (new.id, new.searchable_text);
END;

CREATE TRIGGER IF NOT EXISTS episodes_ai AFTER INSERT ON episodes BEGIN
    INSERT INTO episodes_fts(rowid, searchable_text)
    VALUES (new.id, new.searchable_text);
END;

CREATE TRIGGER IF NOT EXISTS episodes_ad AFTER DELETE ON episodes BEGIN
    INSERT INTO episodes_fts(episodes_fts, rowid, searchable_text)
    VALUES('delete', old.id, old.searchable_text);
END;

CREATE TRIGGER IF NOT EXISTS episodes_au AFTER UPDATE ON episodes BEGIN
    INSERT INTO episodes_fts(episodes_fts, rowid, searchable_text)
    VALUES('delete', old.id, old.searchable_text);
    INSERT INTO episodes_fts(rowid, searchable_text)
    VALUES (new.id, new.searchable_text);
END;

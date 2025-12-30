-- Migration to add hierarchical chunking support
-- Run this to update an existing database to the new schema

ALTER TABLE documentchunk ADD COLUMN IF NOT EXISTS parent_id INTEGER REFERENCES documentchunk(id) ON DELETE CASCADE;
ALTER TABLE documentchunk ADD COLUMN IF NOT EXISTS is_summary BOOLEAN DEFAULT FALSE;

-- Index for performance (optional but recommended)
CREATE INDEX IF NOT EXISTS idx_documentchunk_parent_id ON documentchunk(parent_id);

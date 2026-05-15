-- PostgreSQL DDL for ${table_name}
CREATE TABLE IF NOT EXISTS ${table_name} (
    id BIGSERIAL PRIMARY KEY,
    -- TODO: 添加业务字段
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT FALSE
);

COMMENT ON TABLE ${table_name} IS '${table_comment}';

CREATE INDEX IF NOT EXISTS idx_${table_name}_created_at ON ${table_name}(created_at);
CREATE INDEX IF NOT EXISTS idx_${table_name}_deleted ON ${table_name}(deleted);

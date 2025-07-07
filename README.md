# 1bath-ngao

CREATE TABLE assets (
    id SERIAL PRIMARY KEY,
    asset_id TEXT,
    sub_number INTEGER,
    inventory_code TEXT,
    description TEXT,
    product_code TEXT,
    capitalized_date DATE,
    acquisition_value NUMERIC,
    accumulated_depreciation NUMERIC,
    book_value NUMERIC,
    asset_status TEXT,
    cost_center TEXT,
    image TEXT,
    disposal_status TEXT
);


CREATE TABLE disposal_status_log (
    id SERIAL PRIMARY KEY,
    asset_id TEXT,
    status_code TEXT,
    status_description TEXT,
    ref_document TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by TEXT
);


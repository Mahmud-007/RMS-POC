-- RMS SQLite schema. See PLANNING.md §5 for column rationale.

CREATE TABLE IF NOT EXISTS observations (
    ts        TEXT    NOT NULL,
    channel   TEXT    NOT NULL CHECK (channel IN ('dine_in','delivery','takeaway')),
    covers    REAL    NOT NULL,
    PRIMARY KEY (ts, channel)
);

CREATE TABLE IF NOT EXISTS weather (
    date      TEXT    NOT NULL,
    hour      INTEGER NOT NULL,
    temp      REAL,
    rain_mm   REAL,
    condition TEXT,
    PRIMARY KEY (date, hour)
);

CREATE TABLE IF NOT EXISTS events (
    date      TEXT    NOT NULL,
    type      TEXT    NOT NULL,
    severity  REAL    NOT NULL,
    PRIMARY KEY (date, type)
);

CREATE TABLE IF NOT EXISTS predictions (
    ts             TEXT    NOT NULL,
    channel        TEXT    NOT NULL,
    base_pred      REAL    NOT NULL,
    residual_pred  REAL    NOT NULL,
    final_pred     REAL    NOT NULL,
    model_version  TEXT    NOT NULL,
    created_at     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts, channel)
);

CREATE TABLE IF NOT EXISTS corrections (
    ts            TEXT    NOT NULL,
    channel       TEXT    NOT NULL,
    predicted     REAL    NOT NULL,
    actual        REAL    NOT NULL,
    reason_tag    TEXT    NOT NULL,
    weather_flag  TEXT,
    event_flag    TEXT,
    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts, channel)
);

CREATE TABLE IF NOT EXISTS ingredients (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL UNIQUE,
    unit            TEXT    NOT NULL,
    shelf_life_days INTEGER NOT NULL,
    lead_time_days  INTEGER NOT NULL,
    stock           REAL    NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS recipes (
    item_id          INTEGER NOT NULL,
    ingredient_id    INTEGER NOT NULL,
    qty_per_cover    REAL    NOT NULL,
    PRIMARY KEY (item_id, ingredient_id),
    FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
);

CREATE TABLE IF NOT EXISTS mix_history (
    date     TEXT    NOT NULL,
    item_id  INTEGER NOT NULL,
    share    REAL    NOT NULL,
    PRIMARY KEY (date, item_id)
);

CREATE TABLE IF NOT EXISTS staff_throughput (
    role               TEXT    PRIMARY KEY,
    covers_per_hour    REAL    NOT NULL,
    floor_min          INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS model_registry (
    version      TEXT    PRIMARY KEY,
    type         TEXT    NOT NULL,
    trained_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    mae          REAL,
    r2           REAL,
    path         TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS sgd_state (
    version          TEXT    PRIMARY KEY,
    coef_blob        BLOB    NOT NULL,
    intercept        REAL    NOT NULL,
    n_updates        INTEGER NOT NULL DEFAULT 0,
    last_reset_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_observations_ts ON observations(ts);
CREATE INDEX IF NOT EXISTS idx_predictions_ts ON predictions(ts);
CREATE INDEX IF NOT EXISTS idx_corrections_ts ON corrections(ts);

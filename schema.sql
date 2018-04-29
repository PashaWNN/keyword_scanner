-- Initialize the database.
-- Drop any existing data and create empty tables.

DROP TABLE IF EXISTS tasks;

CREATE TABLE tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT NOT NULL,
  list TEXT NOT NULL,
  progress INTEGER NOT NULL,
  log TEXT NOT NULL,
  result TEXT NOT NULL,
  state INTEGER NOT NULL
);

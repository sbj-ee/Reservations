DROP TABLE IF EXISTS reservation;
DROP TABLE IF EXISTS widget;
DROP TABLE IF EXISTS user;

CREATE TABLE user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE widget (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  created_by INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (created_by) REFERENCES user (id)
);

CREATE TABLE reservation (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  widget_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (widget_id) REFERENCES widget (id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES user (id)
);

CREATE INDEX idx_reservation_widget ON reservation (widget_id, start_time, end_time);
CREATE INDEX idx_reservation_user ON reservation (user_id);

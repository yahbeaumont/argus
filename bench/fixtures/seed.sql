-- Base de fixtures do benchmark: resultados de uma avaliação anterior de RAG/agentes.
-- Deliberadamente pequena e estável: as tarefas de "data" têm resposta única.
DROP TABLE IF EXISTS runs;
DROP TABLE IF EXISTS categories;

CREATE TABLE runs (
  id INTEGER PRIMARY KEY,
  model TEXT NOT NULL,
  accuracy REAL NOT NULL,
  cost_per_task REAL NOT NULL,
  tasks INTEGER NOT NULL,
  p95_latency_s REAL NOT NULL
);

INSERT INTO runs (model, accuracy, cost_per_task, tasks, p95_latency_s) VALUES
  ('baseline-vector', 0.610, 0.0041, 40, 3.1),
  ('hybrid-rerank',   0.890, 0.0098, 40, 8.4),
  ('agent-guarded',   0.825, 0.0580, 40, 61.2),
  ('agent-unguarded', 0.600, 0.0610, 40, 118.9);

CREATE TABLE categories (
  run_id INTEGER NOT NULL REFERENCES runs(id),
  category TEXT NOT NULL,
  passed INTEGER NOT NULL,
  total INTEGER NOT NULL,
  PRIMARY KEY (run_id, category)
);

INSERT INTO categories (run_id, category, passed, total) VALUES
  (3, 'synthesis', 10, 10),
  (3, 'compute',    9, 10),
  (3, 'data',      10, 10),
  (3, 'adversarial', 4, 10),
  (4, 'synthesis',  7, 10),
  (4, 'compute',    9, 10),
  (4, 'data',       6, 10),
  (4, 'adversarial', 2, 10);

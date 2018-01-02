--
-- File generated with SQLiteStudio v3.1.1 on sab dic 23 17:13:49 2017
--
-- Text encoding used: UTF-8
--
PRAGMA foreign_keys = off;
BEGIN TRANSACTION;

	-- Table: authors

	CREATE TABLE IF NOT EXISTS authors (common_name STRING PRIMARY KEY, birth DATE, death DATE, nationality STRING);

	-- Table: features

	CREATE TABLE IF NOT EXISTS features (id PRIMARY KEY REFERENCES works (id), metric STRING NOT NULL, tonality STRING NOT NULL, incipit_type STRING NOT NULL, has_triplets BOOLEAN NOT NULL, features_path STRING NOT NULL);

	-- Table: works

	CREATE TABLE IF NOT EXISTS works (id INTEGER PRIMARY KEY, title STRING, first_performance_date DATE, language STRING, path_lyrics STRING NOT NULL, path_leadsheet STRING NOT NULL);

	-- Table: work_author

	CREATE TABLE IF NOT EXISTS work_author (
		id     INTEGER REFERENCES works (id),
		author STRING  REFERENCES authors (common_name),
		PRIMARY KEY(id, author)
	);

	-- Table: work_genres

	CREATE TABLE IF NOT EXISTS work_genres (id INTEGER REFERENCES works (id) NOT NULL, genre STRING NOT NULL, occurrences INTEGER, PRIMARY KEY (id, genre));

	-- Table: work_style

	CREATE TABLE IF NOT EXISTS work_style (
		id                  REFERENCES works (id),
		style       STRING  NOT NULL,
		occurrences INTEGER,
		PRIMARY KEY(id, style)
	);

	COMMIT TRANSACTION;
	PRAGMA foreign_keys = on;

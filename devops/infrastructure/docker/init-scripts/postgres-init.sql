-- HumanEye PostgreSQL initialization
-- Creates the mlflow database alongside main humaneye DB

CREATE DATABASE mlflow;
GRANT ALL PRIVILEGES ON DATABASE mlflow TO humaneye;

-- Extensions
\c humaneye
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- BRONZE: land source extracts as-is (all text), stamped with lineage columns.
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE OR REPLACE TABLE bronze.shipments AS
SELECT *, current_timestamp AS _ingested_at, 'tms_export' AS _source
FROM read_csv('{raw_dir}/shipments.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE bronze.customers AS
SELECT *, current_timestamp AS _ingested_at, 'crm_export' AS _source
FROM read_csv('{raw_dir}/customers.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE bronze.carriers AS
SELECT *, current_timestamp AS _ingested_at, 'carrier_master' AS _source
FROM read_csv('{raw_dir}/carriers.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE bronze.facilities AS
SELECT *, current_timestamp AS _ingested_at, 'network_master' AS _source
FROM read_csv('{raw_dir}/facilities.csv', header = true, all_varchar = true);

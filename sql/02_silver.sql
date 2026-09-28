-- SILVER: typed, deduplicated, conformed. Rows that break hard rules are
-- quarantined with a reason instead of silently dropped.
CREATE SCHEMA IF NOT EXISTS silver;

CREATE OR REPLACE TABLE silver.customers AS
SELECT customer_id, customer_name, industry, segment, lower(contact_email) AS contact_email,
       TRY_CAST(onboarded_date AS DATE) AS onboarded_date
FROM bronze.customers;

CREATE OR REPLACE TABLE silver.carriers AS
SELECT carrier_id, carrier_name, mode AS primary_mode FROM bronze.carriers;

CREATE OR REPLACE TABLE silver.facilities AS
SELECT facility_id, city, state, region, TRY_CAST(lat AS DOUBLE) AS lat, TRY_CAST(lon AS DOUBLE) AS lon
FROM bronze.facilities;

CREATE OR REPLACE TEMP TABLE shipments_typed AS
SELECT
    shipment_id,
    NULLIF(customer_id, '') AS customer_id,
    carrier_id, origin_id, dest_id, mode, status,
    TRY_CAST(pickup_date AS DATE) AS pickup_date,
    TRY_CAST(promised_date AS DATE) AS promised_date,
    TRY_CAST(actual_delivery_date AS DATE) AS actual_delivery_date,
    TRY_CAST(miles AS INTEGER) AS miles,
    TRY_CAST(weight_lbs AS INTEGER) AS weight_lbs,
    TRY_CAST(pallets AS INTEGER) AS pallets,
    TRY_CAST(linehaul_revenue AS DECIMAL(12, 2)) AS linehaul_revenue,
    TRY_CAST(fuel_revenue AS DECIMAL(12, 2)) AS fuel_revenue,
    TRY_CAST(accessorial_revenue AS DECIMAL(12, 2)) AS accessorial_revenue,
    TRY_CAST(carrier_cost AS DECIMAL(12, 2)) AS carrier_cost,
    TRY_CAST(fuel_cost AS DECIMAL(12, 2)) AS fuel_cost,
    TRY_CAST(accessorial_cost AS DECIMAL(12, 2)) AS accessorial_cost,
    TRY_CAST(delivered_in_full AS BOOLEAN) AS delivered_in_full,
    TRY_CAST(claim_amount_usd AS DECIMAL(12, 2)) AS claim_amount_usd,
    TRY_CAST(source_updated_at AS TIMESTAMP) AS source_updated_at
FROM bronze.shipments
QUALIFY row_number() OVER (PARTITION BY shipment_id ORDER BY source_updated_at DESC) = 1;

CREATE OR REPLACE TEMP TABLE shipments_checked AS
SELECT *,
    CASE
        WHEN customer_id IS NULL THEN 'missing_customer'
        WHEN customer_id NOT IN (SELECT customer_id FROM silver.customers) THEN 'unknown_customer'
        WHEN carrier_id NOT IN (SELECT carrier_id FROM silver.carriers) THEN 'unknown_carrier'
        WHEN weight_lbs IS NULL OR weight_lbs <= 0 THEN 'non_positive_weight'
        WHEN actual_delivery_date < pickup_date THEN 'delivery_before_pickup'
        WHEN pickup_date IS NULL OR promised_date IS NULL THEN 'missing_dates'
    END AS reject_reason
FROM shipments_typed;

CREATE OR REPLACE TABLE silver.shipment_rejects AS
SELECT * FROM shipments_checked WHERE reject_reason IS NOT NULL;

CREATE OR REPLACE TABLE silver.shipments AS
SELECT * EXCLUDE (reject_reason) FROM shipments_checked WHERE reject_reason IS NULL;

CREATE TABLE IF NOT EXISTS silver.load_audit (
    loaded_at TIMESTAMP, bronze_rows BIGINT, duplicates_removed BIGINT,
    rejected_rows BIGINT, silver_rows BIGINT
);
INSERT INTO silver.load_audit
SELECT current_timestamp,
       (SELECT count(*) FROM bronze.shipments),
       (SELECT count(*) FROM bronze.shipments) - (SELECT count(*) FROM shipments_typed),
       (SELECT count(*) FROM silver.shipment_rejects),
       (SELECT count(*) FROM silver.shipments);

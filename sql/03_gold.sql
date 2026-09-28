-- GOLD: Kimball star schema that every dashboard and model reads from.
CREATE SCHEMA IF NOT EXISTS gold;

CREATE OR REPLACE TABLE gold.dim_date AS
SELECT
    CAST(strftime(d, '%Y%m%d') AS INTEGER) AS date_key,
    CAST(d AS DATE) AS date,
    year(d) AS year,
    quarter(d) AS quarter,
    year(d) || '-Q' || quarter(d) AS year_quarter,
    month(d) AS month,
    strftime(d, '%Y-%m') AS year_month,
    dayofweek(d) AS day_of_week,
    strftime(d, '%a') AS day_name,
    dayofweek(d) IN (0, 6) AS is_weekend
FROM generate_series(TIMESTAMP '2024-01-01', TIMESTAMP '2026-12-31', INTERVAL 1 DAY) AS t(d);

-- PII policy: contact email is masked in gold; only silver (restricted) holds it in clear.
CREATE OR REPLACE TABLE gold.dim_customer AS
SELECT customer_id, customer_name, industry, segment, onboarded_date,
       regexp_replace(contact_email, '^(.)[^@]*@', '\1***@') AS contact_email_masked
FROM silver.customers;

CREATE OR REPLACE TABLE gold.dim_carrier AS
SELECT carrier_id, carrier_name, primary_mode FROM silver.carriers;

CREATE OR REPLACE TABLE gold.dim_facility AS
SELECT * FROM silver.facilities;

CREATE OR REPLACE TABLE gold.dim_lane AS
SELECT
    o.facility_id || '-' || d.facility_id AS lane_id,
    o.facility_id AS origin_id, o.city AS origin_city, o.state AS origin_state, o.region AS origin_region,
    o.lat AS origin_lat, o.lon AS origin_lon,
    d.facility_id AS dest_id, d.city AS dest_city, d.state AS dest_state, d.region AS dest_region,
    d.lat AS dest_lat, d.lon AS dest_lon,
    o.region || ' → ' || d.region AS corridor
FROM silver.facilities o
CROSS JOIN silver.facilities d
WHERE o.facility_id <> d.facility_id;

CREATE OR REPLACE TABLE gold.fact_shipment AS
SELECT
    s.shipment_id,
    CAST(strftime(s.pickup_date, '%Y%m%d') AS INTEGER) AS pickup_date_key,
    s.customer_id, s.carrier_id,
    s.origin_id || '-' || s.dest_id AS lane_id,
    s.mode, s.status,
    s.pickup_date, s.promised_date, s.actual_delivery_date,
    s.miles, s.weight_lbs, s.pallets,
    s.linehaul_revenue + s.fuel_revenue + s.accessorial_revenue AS revenue_usd,
    s.carrier_cost + s.fuel_cost + s.accessorial_cost AS total_cost_usd,
    (s.linehaul_revenue + s.fuel_revenue + s.accessorial_revenue)
        - (s.carrier_cost + s.fuel_cost + s.accessorial_cost) AS gross_margin_usd,
    CASE WHEN s.status = 'Delivered' THEN s.actual_delivery_date <= s.promised_date END AS is_on_time,
    CASE WHEN s.status = 'Delivered' THEN s.delivered_in_full END AS is_in_full,
    CASE WHEN s.status = 'Delivered'
         THEN s.actual_delivery_date <= s.promised_date AND s.delivered_in_full END AS is_otif,
    CASE WHEN s.status = 'Delivered'
         THEN greatest(date_diff('day', s.promised_date, s.actual_delivery_date), 0) END AS days_late,
    s.claim_amount_usd,
    s.claim_amount_usd > 0 AS has_claim
FROM silver.shipments s
WHERE s.status <> 'Cancelled';

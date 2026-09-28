"""Generate synthetic source-system extracts for a freight carrier / 3PL.

Stands in for the TMS, CRM, and carrier-master exports an enterprise
warehouse would ingest. The data has realistic signal (carrier reliability,
winter weather, distance, peak season) and deliberately injected defects
(duplicates, orphans, bad values) so the quality layer has something to catch.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .config import AS_OF, START

# id, city, state, region, lat, lon, relative volume
FACILITIES = [
    ("ATL", "Atlanta", "GA", "Southeast", 33.749, -84.388, 1.4),
    ("CHI", "Chicago", "IL", "Midwest", 41.878, -87.630, 1.6),
    ("DAL", "Dallas", "TX", "South Central", 32.777, -96.797, 1.4),
    ("LAX", "Los Angeles", "CA", "West", 34.052, -118.244, 1.6),
    ("EWR", "Newark", "NJ", "Northeast", 40.736, -74.172, 1.3),
    ("MEM", "Memphis", "TN", "Southeast", 35.149, -90.049, 1.1),
    ("IND", "Indianapolis", "IN", "Midwest", 39.768, -86.158, 1.0),
    ("CMH", "Columbus", "OH", "Midwest", 39.961, -82.999, 1.0),
    ("HOU", "Houston", "TX", "South Central", 29.760, -95.370, 1.2),
    ("PHX", "Phoenix", "AZ", "West", 33.448, -112.074, 0.8),
    ("SEA", "Seattle", "WA", "Northwest", 47.606, -122.332, 0.8),
    ("DEN", "Denver", "CO", "Mountain", 39.739, -104.990, 0.8),
    ("MKC", "Kansas City", "MO", "Midwest", 39.100, -94.579, 0.9),
    ("CLT", "Charlotte", "NC", "Southeast", 35.227, -80.843, 0.9),
    ("JAX", "Jacksonville", "FL", "Southeast", 30.332, -81.656, 0.8),
    ("PHL", "Philadelphia", "PA", "Northeast", 39.953, -75.165, 1.0),
    ("MSP", "Minneapolis", "MN", "Midwest", 44.978, -93.265, 0.7),
    ("SLC", "Salt Lake City", "UT", "Mountain", 40.761, -111.891, 0.6),
    ("OAK", "Oakland", "CA", "West", 37.804, -122.271, 0.9),
    ("RIC", "Richmond", "VA", "Southeast", 37.541, -77.436, 0.6),
]
SNOW_REGIONS = {"Midwest", "Northeast", "Mountain", "Northwest"}

# id, name, mode, reliability (logit offset; higher = later), cost index, claim rate
CARRIERS = [
    ("C01", "Summit Freight", "TL", -0.55, 1.04, 0.006),
    ("C02", "Blue Ridge Transport", "TL", -0.20, 0.98, 0.008),
    ("C03", "Prairie Line Logistics", "TL", 0.35, 0.91, 0.012),
    ("C04", "Lone Star Trucking", "TL", 0.10, 0.95, 0.010),
    ("C05", "Evergreen Linehaul", "TL", -0.35, 1.01, 0.007),
    ("C06", "Atlas Road Partners", "TL", 0.65, 0.87, 0.016),
    ("C07", "Keystone LTL", "LTL", -0.30, 1.03, 0.014),
    ("C08", "Great Lakes Haulers", "LTL", 0.25, 0.96, 0.020),
    ("C09", "Redwood Express", "LTL", -0.10, 0.99, 0.015),
    ("C10", "Pioneer Transport", "LTL", 0.55, 0.90, 0.026),
    ("C11", "Northstar Freight", "LTL", 0.00, 0.97, 0.017),
    ("C12", "Ironhorse Intermodal", "Intermodal", -0.05, 0.93, 0.009),
    ("C13", "Harbor Rail Link", "Intermodal", 0.40, 0.88, 0.012),
    ("C14", "Coastal Carriers", "TL", 0.05, 0.96, 0.009),
]

INDUSTRIES = ["Retail", "Food & Beverage", "Industrial", "Automotive", "Healthcare", "E-commerce", "Building Materials"]
NAME_A = ["Apex", "Bright", "Cedar", "Delta", "Echo", "Frontier", "Granite", "Harbor", "Iris", "Juniper",
          "Keystone", "Lumen", "Maple", "Nova", "Orchard", "Pinnacle", "Quarry", "Ridge", "Sterling", "Tidewater"]
NAME_B = ["Foods", "Supply", "Brands", "Manufacturing", "Goods", "Distribution", "Health", "Outfitters", "Materials", "Home"]


def _haversine_miles(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 3958.8 * 2 * np.arcsin(np.sqrt(a))


def _customers(rng: np.random.Generator, n: int) -> pd.DataFrame:
    names = sorted({f"{a} {b}" for a in NAME_A for b in NAME_B})
    picked = rng.choice(names, n, replace=False)
    segment = rng.choice(["Enterprise", "Mid-Market", "SMB"], n, p=[0.15, 0.35, 0.50])
    ids = [f"CU{i:04d}" for i in range(1, n + 1)]
    return pd.DataFrame({
        "customer_id": ids,
        "customer_name": picked,
        "industry": rng.choice(INDUSTRIES, n),
        "segment": segment,
        "contact_email": [f"{nm.split()[0].lower()}.ops{i}@{nm.split()[1].lower()}.example.com" for i, nm in enumerate(picked)],
        "onboarded_date": [START - timedelta(days=int(d)) for d in rng.integers(0, 2000, n)],
    })


def _pickup_dates(rng: np.random.Generator, n: int) -> np.ndarray:
    days = pd.date_range(START, AS_OF, freq="D")
    t = np.arange(len(days)) / len(days)
    dow = days.dayofweek.to_numpy()
    dow_w = np.where(dow >= 5, 0.15, 1.0)
    peak = np.where(days.month.isin([10, 11, 12]), 1.15, 1.0)
    w = (1 + 0.25 * t) * dow_w * peak
    return rng.choice(days.to_numpy(), n, p=w / w.sum())


def generate(out_dir: Path, n_shipments: int = 60_000, seed: int = 42) -> dict[str, int]:
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    fac = pd.DataFrame(FACILITIES, columns=["facility_id", "city", "state", "region", "lat", "lon", "size"])
    car = pd.DataFrame(CARRIERS, columns=["carrier_id", "carrier_name", "mode", "reliability", "cost_index", "claim_rate"])
    cust = _customers(rng, 180)

    n = n_shipments
    w = fac["size"].to_numpy() / fac["size"].sum()
    o = rng.choice(len(fac), n, p=w)
    d = rng.choice(len(fac), n, p=w)
    while (same := o == d).any():
        d[same] = rng.choice(len(fac), same.sum(), p=w)

    miles = _haversine_miles(fac.lat.values[o], fac.lon.values[o], fac.lat.values[d], fac.lon.values[d]) * 1.18
    miles = np.round(miles + rng.normal(0, 8, n)).clip(40)

    # Mode: intermodal only makes sense on long hauls.
    u = rng.random(n)
    im_share = np.where(miles > 800, 0.22, 0.0)
    mode = np.where(u < im_share, "Intermodal", np.where(u < im_share + 0.36, "LTL", "TL"))

    carrier_idx = np.empty(n, dtype=int)
    for m in ("TL", "LTL", "Intermodal"):
        pool = np.flatnonzero(car["mode"].values == m)
        mask = mode == m
        cw = rng.dirichlet(np.ones(len(pool)) * 4)
        carrier_idx[mask] = rng.choice(pool, mask.sum(), p=cw)
    cr = car.iloc[carrier_idx].reset_index(drop=True)

    cust_w = np.where(cust.segment == "Enterprise", 6.0, np.where(cust.segment == "Mid-Market", 2.0, 0.6))
    cust_idx = rng.choice(len(cust), n, p=cust_w / cust_w.sum())
    segment = cust.segment.values[cust_idx]

    pickup = pd.to_datetime(_pickup_dates(rng, n))
    std_days = np.select(
        [mode == "TL", mode == "LTL"],
        [np.ceil(miles / 550), np.ceil(miles / 400) + 1],
        np.ceil(miles / 350) + 2,
    ).astype(int).clip(1)
    promised = pickup + pd.to_timedelta(std_days, unit="D")

    # On-time drivers: carrier, distance, winter weather, mode, Friday pickups, peak season.
    o_reg, d_reg = fac.region.values[o], fac.region.values[d]
    winter = np.asarray(pickup.month.isin([12, 1, 2]))
    snowy = np.isin(o_reg, list(SNOW_REGIONS)) | np.isin(d_reg, list(SNOW_REGIONS))
    logit = (
        -2.9 + 1.3 * cr.reliability.values + 0.00035 * miles
        + 0.75 * (winter & snowy) + 0.2 * winter
        + np.select([mode == "LTL", mode == "Intermodal"], [0.35, 0.25], 0.0)
        + 0.25 * (pickup.dayofweek.to_numpy() == 4)
        + 0.3 * np.asarray(pickup.month.isin([11, 12]))
        + rng.normal(0, 0.2, n)
    )
    late = rng.random(n) < 1 / (1 + np.exp(-logit))
    days_late = np.where(late, 1 + rng.poisson(0.55, n), np.where(rng.random(n) < 0.08, -1, 0))
    actual = promised + pd.to_timedelta(days_late, unit="D")

    status = np.where(actual > pd.Timestamp(AS_OF), "In Transit", "Delivered")
    status = np.where(rng.random(n) < 0.01, "Cancelled", status)

    weight = np.select(
        [mode == "TL", mode == "LTL"],
        [rng.uniform(18_000, 44_000, n), np.exp(rng.normal(7.8, 0.7, n)).clip(150, 12_000)],
        rng.uniform(25_000, 42_000, n),
    ).round()
    pallets = np.ceil(weight / 1400).clip(1, 26).astype(int)

    # Pricing: market rate drifts with season; lanes carry a headhaul/backhaul imbalance.
    month_idx = (pickup.year - START.year) * 12 + pickup.month
    market = 1 + 0.05 * np.sin(2 * np.pi * month_idx / 12) + 0.0015 * (month_idx - month_idx.min())
    seg_adj = np.select([segment == "Enterprise", segment == "SMB"], [0.94, 1.05], 1.0)
    linehaul_rev = np.select(
        [mode == "TL", mode == "LTL"],
        [miles * 2.55, np.maximum(150, weight / 100 * (12 + miles * 0.03))],
        miles * 1.95,
    ) * market * seg_adj * rng.normal(1, 0.06, n)
    fuel_per_mile = 0.58 + 0.06 * np.sin(2 * np.pi * (month_idx + 3) / 12)
    fuel_rev = np.where(mode == "LTL", linehaul_rev * 0.24, miles * fuel_per_mile)
    detention = np.where(days_late > 0, 85 * days_late, 0) + np.where(rng.random(n) < 0.06, rng.uniform(50, 300, n), 0)
    accessorial_rev = detention * 1.25

    lane_key = o * 100 + d
    lane_shock = {k: v for k, v in zip(np.unique(lane_key), rng.normal(0, 0.07, len(np.unique(lane_key))))}
    imbalance = np.vectorize(lane_shock.get)(lane_key)
    carrier_cost = linehaul_rev * 0.84 * cr.cost_index.values * (1 + imbalance) * rng.normal(1, 0.04, n)
    fuel_cost = fuel_rev * 0.96
    accessorial_cost = detention

    claim_p = cr.claim_rate.values * np.where(mode == "LTL", 1.4, 1.0)
    claim = np.where(rng.random(n) < claim_p, np.exp(rng.normal(7.3, 0.8, n)), 0.0)
    in_full = rng.random(n) > np.where(mode == "LTL", 0.04, 0.02)

    delivered = status == "Delivered"
    ship = pd.DataFrame({
        "shipment_id": [f"SH{i:07d}" for i in range(1, n + 1)],
        "customer_id": cust.customer_id.values[cust_idx],
        "carrier_id": cr.carrier_id.values,
        "origin_id": fac.facility_id.values[o],
        "dest_id": fac.facility_id.values[d],
        "mode": mode,
        "status": status,
        "pickup_date": pickup.date,
        "promised_date": promised.date,
        "actual_delivery_date": np.where(delivered, actual.date, None),
        "miles": miles.astype(int),
        "weight_lbs": weight.astype(int),
        "pallets": pallets,
        "linehaul_revenue": linehaul_rev.round(2),
        "fuel_revenue": fuel_rev.round(2),
        "accessorial_revenue": accessorial_rev.round(2),
        "carrier_cost": carrier_cost.round(2),
        "fuel_cost": fuel_cost.round(2),
        "accessorial_cost": accessorial_cost.round(2),
        "delivered_in_full": np.where(delivered, in_full, None),
        "claim_amount_usd": np.where(delivered, claim, 0).round(2),
        "source_updated_at": pickup + pd.to_timedelta(rng.integers(1, 20, n), unit="h"),
    })
    ship = _inject_defects(ship, rng)

    ship.to_csv(out_dir / "shipments.csv", index=False)
    cust.to_csv(out_dir / "customers.csv", index=False)
    car.drop(columns=["reliability", "cost_index", "claim_rate"]).to_csv(out_dir / "carriers.csv", index=False)
    fac.drop(columns=["size"]).to_csv(out_dir / "facilities.csv", index=False)
    return {"shipments": len(ship), "customers": len(cust), "carriers": len(car), "facilities": len(fac)}


def _inject_defects(ship: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Simulate what real source systems send: re-sent records and bad keys/values."""
    n = len(ship)

    def pick(rate):
        return rng.choice(n, max(1, int(n * rate)), replace=False)

    ship.loc[pick(0.0025), "customer_id"] = None
    neg = pick(0.0015)
    ship.loc[neg, "weight_lbs"] = -ship.loc[neg, "weight_lbs"]
    ship.loc[pick(0.001), "carrier_id"] = "C99"
    bad = pick(0.001)
    ship.loc[bad, "actual_delivery_date"] = (pd.to_datetime(ship.loc[bad, "pickup_date"]) - pd.Timedelta(days=2)).dt.date
    ship.loc[pick(0.0002), "linehaul_revenue"] *= 100  # fat-finger rate entry

    # Re-sent records: same shipment, later timestamp. Silver keeps the latest version.
    dup = ship.iloc[pick(0.006)].copy()
    dup["source_updated_at"] = dup["source_updated_at"] + pd.Timedelta(hours=30)
    return pd.concat([ship, dup], ignore_index=True)

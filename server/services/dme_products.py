"""DME Product Catalog — sleep medicine equipment and supplies.

Sourced from the practice's prescription form (HCPCS-based) with
size variants for masks. V1 supports browsing and selection; ordering
links out to VGM/PPM portals.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from server.db import db_execute, db_fetch_all, db_fetch_one

logger = logging.getLogger(__name__)


# ── Seed data from the practice prescription form ────────────────────

PRODUCT_CATALOG = [
    # ── EQUIPMENT (machines) ─────────────────────────────────────────
    {
        "id": "equip-cpap",
        "hcpcs_code": "E0601",
        "name": "CPAP Device",
        "category": "Equipment",
        "subcategory": "PAP Machines",
        "description": "Continuous Airway Pressure (CPAP) Device",
        "is_machine": True,
        "device_types": ["CPAP", "Auto-CPAP"],
        "sort_order": 1,
    },
    {
        "id": "equip-bipap",
        "hcpcs_code": "E0470",
        "name": "Bi-Level PAP (w/o Backup Rate)",
        "category": "Equipment",
        "subcategory": "PAP Machines",
        "description": "Bi-Level Pressure Capability, without Backup Rate",
        "is_machine": True,
        "device_types": ["Bi-Level PAP", "Auto Bi-Level PAP"],
        "sort_order": 2,
    },
    {
        "id": "equip-bipap-backup",
        "hcpcs_code": "E0471",
        "name": "Bi-Level PAP (w/ Backup Rate)",
        "category": "Equipment",
        "subcategory": "PAP Machines",
        "description": "Bi-Level Pressure Capability, with Back-Up Rate",
        "is_machine": True,
        "device_types": ["Bi-Level PAP", "Auto Bi-Level PAP", "Adaptive Servo Ventilation"],
        "sort_order": 3,
    },
    {
        "id": "equip-humidifier-nonheated",
        "hcpcs_code": "E0561",
        "name": "Humidifier, Non-Heated",
        "category": "Equipment",
        "subcategory": "Humidifiers",
        "description": "Humidifier, Non-Heated, used with PAP device",
        "is_machine": False,
        "device_types": ["CPAP", "Auto-CPAP", "Bi-Level PAP", "Auto Bi-Level PAP", "Adaptive Servo Ventilation"],
        "sort_order": 4,
    },
    {
        "id": "equip-humidifier-heated",
        "hcpcs_code": "E0562",
        "name": "Humidifier, Heated",
        "category": "Equipment",
        "subcategory": "Humidifiers",
        "description": "Humidifier, Heated, used with PAP device",
        "is_machine": False,
        "device_types": ["CPAP", "Auto-CPAP", "Bi-Level PAP", "Auto Bi-Level PAP", "Adaptive Servo Ventilation"],
        "sort_order": 5,
    },

    # ── MASKS (with size variants) ───────────────────────────────────
    {
        "id": "mask-full-face",
        "hcpcs_code": "A7030",
        "name": "Full Face Mask",
        "category": "Masks",
        "subcategory": "Full Face",
        "description": "Full Face Mask, complete assembly",
        "resupply_months": 3,
        "has_sizes": True,
        "available_sizes": ["XS", "S", "S/M", "M", "M/L", "L", "XL"],
        "is_accessory": True,
        "sort_order": 10,
    },
    {
        "id": "mask-nasal",
        "hcpcs_code": "A7034",
        "name": "Nasal Mask (or Cannula)",
        "category": "Masks",
        "subcategory": "Nasal",
        "description": "Nasal Interface (Mask or Cannula), complete assembly",
        "resupply_months": 3,
        "has_sizes": True,
        "available_sizes": ["XS", "S", "S/M", "M", "M/L", "L"],
        "is_accessory": True,
        "sort_order": 11,
    },
    {
        "id": "mask-nasal-pillow",
        "hcpcs_code": "A7033",
        "name": "Nasal Pillow",
        "category": "Masks",
        "subcategory": "Nasal Pillow",
        "description": "Replacement Nasal Pillow",
        "resupply_months": 1,
        "has_sizes": True,
        "available_sizes": ["XS", "S", "S/M", "M", "L"],
        "is_accessory": True,
        "sort_order": 12,
    },
    {
        "id": "mask-oral-nasal-combo",
        "hcpcs_code": "A7027",
        "name": "Combination Oral/Nasal Mask",
        "category": "Masks",
        "subcategory": "Oral/Nasal",
        "description": "Combination Oral/Nasal Mask, complete assembly",
        "has_sizes": True,
        "available_sizes": ["S", "M", "L"],
        "is_accessory": True,
        "sort_order": 13,
    },
    {
        "id": "mask-oral",
        "hcpcs_code": "A7044",
        "name": "Oral Interface",
        "category": "Masks",
        "subcategory": "Oral",
        "description": "Oral Interface device",
        "has_sizes": True,
        "available_sizes": ["S", "M", "L"],
        "is_accessory": True,
        "sort_order": 14,
    },

    # ── REPLACEMENT CUSHIONS / PILLOWS ───────────────────────────────
    {
        "id": "cushion-full-face",
        "hcpcs_code": "A7031",
        "name": "Replacement Cushion — Full Face",
        "category": "Replacement Parts",
        "subcategory": "Cushions",
        "description": "Replacement Cushion for Full Face Mask",
        "resupply_months": 1,
        "has_sizes": True,
        "available_sizes": ["XS", "S", "S/M", "M", "M/L", "L", "XL"],
        "is_accessory": True,
        "sort_order": 20,
    },
    {
        "id": "cushion-nasal",
        "hcpcs_code": "A7032",
        "name": "Replacement Cushion — Nasal Mask",
        "category": "Replacement Parts",
        "subcategory": "Cushions",
        "description": "Replacement Cushion for Nasal Mask",
        "resupply_months": 1,
        "has_sizes": True,
        "available_sizes": ["XS", "S", "S/M", "M", "M/L", "L"],
        "is_accessory": True,
        "sort_order": 21,
    },
    {
        "id": "cushion-oral-nasal",
        "hcpcs_code": "A7028",
        "name": "Replacement Cushion — Oral/Nasal Combo",
        "category": "Replacement Parts",
        "subcategory": "Cushions",
        "description": "Replacement Oral Cushion for Combo Oral/Nasal Mask",
        "has_sizes": True,
        "available_sizes": ["S", "M", "L"],
        "is_accessory": True,
        "sort_order": 22,
    },
    {
        "id": "pillows-oral-nasal",
        "hcpcs_code": "A7029",
        "name": "Replacement Nasal Pillows — Oral/Nasal Combo",
        "category": "Replacement Parts",
        "subcategory": "Pillows",
        "description": "Replacement Nasal Pillows for Combo Oral/Nasal Mask",
        "has_sizes": True,
        "available_sizes": ["XS", "S", "M", "L"],
        "is_accessory": True,
        "sort_order": 23,
    },

    # ── TUBING ───────────────────────────────────────────────────────
    {
        "id": "tubing-heated",
        "hcpcs_code": "A4604",
        "name": "Heated Tubing",
        "category": "Accessories",
        "subcategory": "Tubing",
        "description": "Tubing with Integrated Heating Element",
        "resupply_months": 3,
        "is_accessory": True,
        "sort_order": 30,
    },
    {
        "id": "tubing-standard",
        "hcpcs_code": "A7037",
        "name": "Standard Tubing (Non-Heated)",
        "category": "Accessories",
        "subcategory": "Tubing",
        "description": "Tubing — Non-Heated",
        "resupply_months": 2,
        "is_accessory": True,
        "sort_order": 31,
    },

    # ── HEADGEAR / CHINSTRAP ─────────────────────────────────────────
    {
        "id": "headgear",
        "hcpcs_code": "A7035",
        "name": "Headgear",
        "category": "Accessories",
        "subcategory": "Headgear",
        "description": "Headgear for PAP mask",
        "resupply_months": 6,
        "has_sizes": True,
        "available_sizes": ["S", "M", "L"],
        "is_accessory": True,
        "sort_order": 32,
    },
    {
        "id": "chinstrap",
        "hcpcs_code": "A7036",
        "name": "Chinstrap",
        "category": "Accessories",
        "subcategory": "Headgear",
        "description": "Chinstrap for PAP therapy",
        "resupply_months": 6,
        "is_accessory": True,
        "sort_order": 33,
    },

    # ── FILTERS ──────────────────────────────────────────────────────
    {
        "id": "filter-disposable",
        "hcpcs_code": "A7038",
        "name": "Filter — Disposable",
        "category": "Accessories",
        "subcategory": "Filters",
        "description": "Disposable filter for PAP device",
        "resupply_months": 1,
        "resupply_qty": 2,
        "is_accessory": True,
        "sort_order": 34,
    },
    {
        "id": "filter-nondisposable",
        "hcpcs_code": "A7039",
        "name": "Filter — Non-Disposable (Reusable)",
        "category": "Accessories",
        "subcategory": "Filters",
        "description": "Non-disposable (reusable) filter for PAP device",
        "resupply_months": 6,
        "is_accessory": True,
        "sort_order": 35,
    },

    # ── HUMIDIFIER CHAMBER ───────────────────────────────────────────
    {
        "id": "humidifier-chamber",
        "hcpcs_code": "A7046",
        "name": "Humidifier Chamber",
        "category": "Accessories",
        "subcategory": "Humidifier",
        "description": "Replacement Humidifier Chamber",
        "resupply_months": 3,
        "is_accessory": True,
        "sort_order": 36,
    },

    # ── OTHER ────────────────────────────────────────────────────────
    {
        "id": "exhalation-port",
        "hcpcs_code": "A7045",
        "name": "Exhalation Port / Swivel",
        "category": "Accessories",
        "subcategory": "Other",
        "description": "Replacement Exhalation Port with or without Swivel",
        "is_accessory": True,
        "sort_order": 40,
    },
    {
        "id": "modem",
        "hcpcs_code": "A9279",
        "name": "Modem (Wireless Transmitter)",
        "category": "Accessories",
        "subcategory": "Other",
        "description": "Monitoring feature/device, standalone or integrated",
        "is_accessory": True,
        "sort_order": 41,
    },
]

# Vendor ordering portals (V1: link out, V2+: direct integration)
VENDOR_PORTALS = {
    "VGM": {
        "name": "VGM & Associates",
        "order_url": "https://www.vgm.com/login/?returnURL=%2fportal%2f",
        "notes": "Group purchasing organization — order via VGM portal",
    },
    "PPM": {
        "name": "PPM Fulfillment",
        "order_url": "https://dev.ppmfulfillment.com/Login.aspx",
        "notes": "Direct DME fulfillment — order via PPM portal",
    },
    "In-House": {
        "name": "In-House Stock",
        "order_url": "",
        "notes": "Stocked on-site — managed via inventory UI",
    },
}


# ── Database operations ──────────────────────────────────────────────

async def seed_products():
    """Populate dme_products table from PRODUCT_CATALOG. Idempotent."""
    existing = await db_fetch_all("SELECT id FROM dme_products")
    existing_ids = {row["id"] for row in existing}

    inserted = 0
    for p in PRODUCT_CATALOG:
        if p["id"] in existing_ids:
            continue
        await db_execute(
            """INSERT INTO dme_products
               (id, hcpcs_code, name, category, subcategory, description,
                resupply_months, resupply_qty, has_sizes, available_sizes,
                vendors, device_types, is_machine, is_accessory, active, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                p["id"],
                p["hcpcs_code"],
                p["name"],
                p["category"],
                p.get("subcategory", ""),
                p.get("description", ""),
                p.get("resupply_months"),
                p.get("resupply_qty", 1),
                1 if p.get("has_sizes") else 0,
                json.dumps(p.get("available_sizes", [])),
                json.dumps(p.get("vendors", ["In-House", "PPM", "VGM"])),
                json.dumps(p.get("device_types", [])),
                1 if p.get("is_machine") else 0,
                1 if p.get("is_accessory") else 0,
                p.get("sort_order", 100),
            ),
        )
        inserted += 1

    if inserted:
        logger.info(f"Seeded {inserted} DME products")
    return inserted


async def get_all_products(active_only: bool = True) -> list[dict]:
    """Return all products, optionally filtered to active only."""
    sql = "SELECT * FROM dme_products"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY sort_order, name"
    rows = await db_fetch_all(sql)
    return [_deserialize_product(r) for r in rows]


async def get_products_by_category(category: str) -> list[dict]:
    """Return products filtered by category (Equipment, Masks, etc.)."""
    rows = await db_fetch_all(
        "SELECT * FROM dme_products WHERE category = ? AND active = 1 ORDER BY sort_order, name",
        (category,),
    )
    return [_deserialize_product(r) for r in rows]


async def get_product(product_id: str) -> Optional[dict]:
    """Return a single product by ID."""
    row = await db_fetch_one(
        "SELECT * FROM dme_products WHERE id = ?", (product_id,)
    )
    return _deserialize_product(row) if row else None


async def get_products_by_hcpcs(hcpcs_code: str) -> list[dict]:
    """Return products matching a HCPCS code."""
    rows = await db_fetch_all(
        "SELECT * FROM dme_products WHERE hcpcs_code = ? AND active = 1 ORDER BY sort_order",
        (hcpcs_code,),
    )
    return [_deserialize_product(r) for r in rows]


async def get_product_categories() -> list[str]:
    """Return distinct active product categories."""
    rows = await db_fetch_all(
        "SELECT DISTINCT category FROM dme_products WHERE active = 1 ORDER BY "
        "CASE category "
        "  WHEN 'Equipment' THEN 1 "
        "  WHEN 'Masks' THEN 2 "
        "  WHEN 'Replacement Parts' THEN 3 "
        "  WHEN 'Accessories' THEN 4 "
        "  ELSE 5 END"
    )
    return [r["category"] for r in rows]


def get_vendor_info(vendor: str) -> Optional[dict]:
    """Return vendor portal info."""
    return VENDOR_PORTALS.get(vendor)


def get_all_vendors() -> list[dict]:
    """Return all vendor options with portal info."""
    return [
        {"key": k, **v}
        for k, v in VENDOR_PORTALS.items()
    ]


def _deserialize_product(row: dict) -> dict:
    """Parse JSON fields from a database row."""
    row = dict(row)
    for field in ("available_sizes", "vendors", "device_types"):
        if isinstance(row.get(field), str):
            try:
                row[field] = json.loads(row[field])
            except (json.JSONDecodeError, TypeError):
                row[field] = []
    row["has_sizes"] = bool(row.get("has_sizes"))
    row["is_machine"] = bool(row.get("is_machine"))
    row["is_accessory"] = bool(row.get("is_accessory"))
    row["active"] = bool(row.get("active"))
    return row


# ── In-House Inventory ───────────────────────────────────────────────

async def seed_inventory():
    """Create inventory rows for all active products. Idempotent.
    Products with sizes get one row per size; others get one row with size=''."""
    products = await get_all_products()
    existing = await db_fetch_all("SELECT product_id, size FROM dme_inventory")
    existing_keys = {(r["product_id"], r["size"]) for r in existing}

    inserted = 0
    now = datetime.now().isoformat()
    for p in products:
        if p["has_sizes"] and p["available_sizes"]:
            for size in p["available_sizes"]:
                if (p["id"], size) not in existing_keys:
                    inv_id = f"inv-{p['id']}-{size.lower().replace('/', '')}"
                    await db_execute(
                        """INSERT INTO dme_inventory (id, product_id, size, quantity, reorder_point, updated_at)
                           VALUES (?, ?, ?, 0, 2, ?)""",
                        (inv_id, p["id"], size, now),
                    )
                    inserted += 1
        else:
            if (p["id"], "") not in existing_keys:
                inv_id = f"inv-{p['id']}"
                await db_execute(
                    """INSERT INTO dme_inventory (id, product_id, size, quantity, reorder_point, updated_at)
                       VALUES (?, ?, '', 0, 2, ?)""",
                    (inv_id, p["id"], now),
                )
                inserted += 1

    if inserted:
        logger.info(f"Seeded {inserted} inventory rows")
    return inserted


async def get_inventory() -> list[dict]:
    """Return full inventory with product details, sorted by product."""
    rows = await db_fetch_all("""
        SELECT i.id, i.product_id, i.size, i.quantity, i.reorder_point,
               i.last_restocked, i.updated_at,
               p.name as product_name, p.hcpcs_code, p.category
        FROM dme_inventory i
        JOIN dme_products p ON p.id = i.product_id
        WHERE p.active = 1
        ORDER BY p.sort_order, p.name, i.size
    """)
    result = []
    for r in rows:
        row = dict(r)
        row["low_stock"] = row["quantity"] <= row["reorder_point"]
        result.append(row)
    return result


async def get_inventory_for_product(product_id: str) -> list[dict]:
    """Return inventory rows for a specific product."""
    rows = await db_fetch_all(
        """SELECT * FROM dme_inventory WHERE product_id = ? ORDER BY size""",
        (product_id,),
    )
    result = []
    for r in rows:
        row = dict(r)
        row["low_stock"] = row["quantity"] <= row["reorder_point"]
        result.append(row)
    return result


async def update_inventory(
    inventory_id: str, quantity: int, reorder_point: Optional[int] = None
) -> Optional[dict]:
    """Update quantity (and optionally reorder point) for an inventory row."""
    now = datetime.now().isoformat()
    if reorder_point is not None:
        await db_execute(
            "UPDATE dme_inventory SET quantity = ?, reorder_point = ?, updated_at = ? WHERE id = ?",
            (quantity, reorder_point, now, inventory_id),
        )
    else:
        await db_execute(
            "UPDATE dme_inventory SET quantity = ?, updated_at = ? WHERE id = ?",
            (quantity, now, inventory_id),
        )
    return await db_fetch_one("SELECT * FROM dme_inventory WHERE id = ?", (inventory_id,))


async def adjust_inventory(inventory_id: str, delta: int) -> Optional[dict]:
    """Increment/decrement inventory by delta. Prevents going below 0."""
    now = datetime.now().isoformat()
    await db_execute(
        "UPDATE dme_inventory SET quantity = MAX(0, quantity + ?), updated_at = ? WHERE id = ?",
        (delta, now, inventory_id),
    )
    return await db_fetch_one("SELECT * FROM dme_inventory WHERE id = ?", (inventory_id,))


async def restock_inventory(inventory_id: str, quantity: int) -> Optional[dict]:
    """Add stock and record restock timestamp."""
    now = datetime.now().isoformat()
    await db_execute(
        "UPDATE dme_inventory SET quantity = quantity + ?, last_restocked = ?, updated_at = ? WHERE id = ?",
        (quantity, now, now, inventory_id),
    )
    return await db_fetch_one("SELECT * FROM dme_inventory WHERE id = ?", (inventory_id,))


async def get_low_stock_items() -> list[dict]:
    """Return items at or below reorder point."""
    rows = await db_fetch_all("""
        SELECT i.id, i.product_id, i.size, i.quantity, i.reorder_point,
               i.last_restocked, i.updated_at,
               p.name as product_name, p.hcpcs_code, p.category
        FROM dme_inventory i
        JOIN dme_products p ON p.id = i.product_id
        WHERE p.active = 1 AND i.quantity <= i.reorder_point
        ORDER BY i.quantity ASC, p.name
    """)
    return [dict(r) for r in rows]


async def get_inventory_summary() -> dict:
    """Dashboard summary: total items, low stock count, out of stock count."""
    total = await db_fetch_one(
        "SELECT COUNT(*) as count FROM dme_inventory i JOIN dme_products p ON p.id = i.product_id WHERE p.active = 1"
    )
    low = await db_fetch_one(
        "SELECT COUNT(*) as count FROM dme_inventory i JOIN dme_products p ON p.id = i.product_id "
        "WHERE p.active = 1 AND i.quantity <= i.reorder_point AND i.quantity > 0"
    )
    out = await db_fetch_one(
        "SELECT COUNT(*) as count FROM dme_inventory i JOIN dme_products p ON p.id = i.product_id "
        "WHERE p.active = 1 AND i.quantity = 0"
    )
    return {
        "total_skus": total["count"] if total else 0,
        "low_stock": low["count"] if low else 0,
        "out_of_stock": out["count"] if out else 0,
    }

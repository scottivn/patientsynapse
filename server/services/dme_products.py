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
    # ══════════════════════════════════════════════════════════════════
    # EQUIPMENT — PAP Machines
    # ══════════════════════════════════════════════════════════════════

    # ── ResMed ────────────────────────────────────────────────────────
    {
        "id": "equip-resmed-airsense11",
        "hcpcs_code": "E0601",
        "name": "ResMed AirSense 11 AutoSet",
        "category": "Equipment",
        "subcategory": "PAP Machines",
        "description": "Auto-CPAP with integrated humidifier, Bluetooth",
        "is_machine": True,
        "device_types": ["CPAP", "Auto-CPAP"],
        "vendors": ["PPM", "ResMed"],
        "sort_order": 1,
    },
    {
        "id": "equip-resmed-aircurve10",
        "hcpcs_code": "E0470",
        "name": "ResMed AirCurve 10 VAuto",
        "category": "Equipment",
        "subcategory": "PAP Machines",
        "description": "Bi-Level PAP without backup rate",
        "is_machine": True,
        "device_types": ["Bi-Level PAP", "Auto Bi-Level PAP"],
        "vendors": ["PPM", "ResMed"],
        "sort_order": 2,
    },
    {
        "id": "equip-resmed-aircurve10-asv",
        "hcpcs_code": "E0471",
        "name": "ResMed AirCurve 10 ASV",
        "category": "Equipment",
        "subcategory": "PAP Machines",
        "description": "Adaptive Servo Ventilation with backup rate",
        "is_machine": True,
        "device_types": ["Adaptive Servo Ventilation"],
        "vendors": ["PPM", "ResMed"],
        "sort_order": 3,
    },
    # ── 3B Medical ────────────────────────────────────────────────────
    {
        "id": "equip-3b-luna-g3-apap",
        "hcpcs_code": "E0601",
        "name": "3B Luna G3 Auto-CPAP",
        "category": "Equipment",
        "subcategory": "PAP Machines",
        "description": "Luna G3 APAP with integrated heated humidifier",
        "is_machine": True,
        "device_types": ["CPAP", "Auto-CPAP"],
        "vendors": ["3B Medical", "PPM"],
        "manufacturer_sku": "LG3600",
        "sort_order": 4,
    },
    {
        "id": "equip-3b-luna-g3-bpap25",
        "hcpcs_code": "E0470",
        "name": "3B Luna G3 BPAP 25A",
        "category": "Equipment",
        "subcategory": "PAP Machines",
        "description": "Luna G3 Bi-Level 25A without backup rate",
        "is_machine": True,
        "device_types": ["Bi-Level PAP"],
        "vendors": ["3B Medical", "PPM"],
        "manufacturer_sku": "LG3700",
        "sort_order": 5,
    },
    {
        "id": "equip-3b-luna-g3-bpap30",
        "hcpcs_code": "E0471",
        "name": "3B Luna G3 BPAP BiLevel 30",
        "category": "Equipment",
        "subcategory": "PAP Machines",
        "description": "Luna G3 Bi-Level 30 with backup rate",
        "is_machine": True,
        "device_types": ["Bi-Level PAP", "Auto Bi-Level PAP"],
        "vendors": ["3B Medical"],
        "manufacturer_sku": "LG3800",
        "sort_order": 6,
    },
    # ── Philips ───────────────────────────────────────────────────────
    {
        "id": "equip-philips-ds2",
        "hcpcs_code": "E0601",
        "name": "Philips DreamStation 2 Auto",
        "category": "Equipment",
        "subcategory": "PAP Machines",
        "description": "DreamStation 2 Auto-CPAP with humidifier",
        "is_machine": True,
        "device_types": ["CPAP", "Auto-CPAP"],
        "vendors": ["PPM", "Philips"],
        "sort_order": 7,
    },
    # ── 3B Travel ─────────────────────────────────────────────────────
    {
        "id": "equip-3b-travelpap",
        "hcpcs_code": "E0601",
        "name": "3B Luna TravelPAP Auto",
        "category": "Equipment",
        "subcategory": "PAP Machines",
        "description": "Portable travel auto-CPAP",
        "is_machine": True,
        "device_types": ["CPAP", "Auto-CPAP"],
        "vendors": ["3B Medical"],
        "manufacturer_sku": "LTP100",
        "sort_order": 8,
    },

    # ══════════════════════════════════════════════════════════════════
    # EQUIPMENT — Humidifiers
    # ══════════════════════════════════════════════════════════════════
    {
        "id": "equip-humidifier-heated",
        "hcpcs_code": "E0562",
        "name": "Heated Humidifier (Integrated)",
        "category": "Equipment",
        "subcategory": "Humidifiers",
        "description": "Heated humidifier, integrated with or attached to PAP device",
        "is_machine": False,
        "device_types": ["CPAP", "Auto-CPAP", "Bi-Level PAP", "Adaptive Servo Ventilation"],
        "sort_order": 9,
    },
    {
        "id": "equip-fp-sleepstyle",
        "hcpcs_code": "E0562",
        "name": "F&P SleepStyle Auto CPAP",
        "category": "Equipment",
        "subcategory": "Humidifiers",
        "description": "Fisher & Paykel SleepStyle with built-in heated humidifier",
        "is_machine": True,
        "device_types": ["CPAP", "Auto-CPAP"],
        "vendors": ["Fisher & Paykel"],
        "manufacturer_sku": "ICON+AUTO",
        "sort_order": 10,
    },

    # ══════════════════════════════════════════════════════════════════
    # MASKS — Full Face (A7030)
    # ══════════════════════════════════════════════════════════════════
    {
        "id": "mask-resmed-f20",
        "hcpcs_code": "A7030",
        "name": "ResMed AirFit F20",
        "category": "Masks",
        "subcategory": "Full Face",
        "description": "Full face mask, complete assembly",
        "resupply_months": 3,
        "has_sizes": True,
        "available_sizes": ["S", "M", "L"],
        "is_accessory": True,
        "vendors": ["PPM", "ResMed"],
        "sort_order": 20,
    },
    {
        "id": "mask-resmed-f30i",
        "hcpcs_code": "A7030",
        "name": "ResMed AirFit F30i",
        "category": "Masks",
        "subcategory": "Full Face",
        "description": "Full face mask with top-of-head tube connection",
        "resupply_months": 3,
        "has_sizes": True,
        "available_sizes": ["S", "M", "STD"],
        "is_accessory": True,
        "vendors": ["PPM", "ResMed"],
        "sort_order": 21,
    },
    {
        "id": "mask-3b-siesta-ff",
        "hcpcs_code": "A7030",
        "name": "3B Siesta Full Face",
        "category": "Masks",
        "subcategory": "Full Face",
        "description": "Siesta full face mask, complete assembly",
        "resupply_months": 3,
        "has_sizes": True,
        "available_sizes": ["S", "M", "L"],
        "is_accessory": True,
        "vendors": ["3B Medical", "PPM"],
        "manufacturer_sku": "SFF1002",
        "sort_order": 22,
    },
    {
        "id": "mask-fp-vitera",
        "hcpcs_code": "A7030",
        "name": "F&P Vitera Full Face",
        "category": "Masks",
        "subcategory": "Full Face",
        "description": "Fisher & Paykel Vitera full face mask",
        "resupply_months": 3,
        "has_sizes": True,
        "available_sizes": ["S", "M", "L"],
        "is_accessory": True,
        "vendors": ["Fisher & Paykel"],
        "sort_order": 23,
    },
    {
        "id": "mask-fp-evora-ff",
        "hcpcs_code": "A7030",
        "name": "F&P Evora Full Face",
        "category": "Masks",
        "subcategory": "Full Face",
        "description": "Fisher & Paykel Evora full face mask, compact design",
        "resupply_months": 3,
        "has_sizes": True,
        "available_sizes": ["XS/S", "S/M", "M/L"],
        "is_accessory": True,
        "vendors": ["Fisher & Paykel"],
        "sort_order": 24,
    },
    {
        "id": "mask-philips-dw-ff",
        "hcpcs_code": "A7030",
        "name": "Philips DreamWear Full Face",
        "category": "Masks",
        "subcategory": "Full Face",
        "description": "DreamWear full face mask, under-nose design",
        "resupply_months": 3,
        "has_sizes": True,
        "available_sizes": ["S", "M", "MW", "L"],
        "is_accessory": True,
        "vendors": ["PPM", "Philips"],
        "sort_order": 25,
    },

    # ══════════════════════════════════════════════════════════════════
    # MASKS — Nasal (A7034)
    # ══════════════════════════════════════════════════════════════════
    {
        "id": "mask-3b-siesta-nasal",
        "hcpcs_code": "A7034",
        "name": "3B Siesta Nasal",
        "category": "Masks",
        "subcategory": "Nasal",
        "description": "Siesta nasal mask, complete assembly",
        "resupply_months": 3,
        "has_sizes": True,
        "available_sizes": ["S", "M", "L"],
        "is_accessory": True,
        "vendors": ["3B Medical", "PPM"],
        "manufacturer_sku": "SNA1002",
        "sort_order": 30,
    },
    {
        "id": "mask-fp-eson2",
        "hcpcs_code": "A7034",
        "name": "F&P Eson 2 Nasal",
        "category": "Masks",
        "subcategory": "Nasal",
        "description": "Fisher & Paykel Eson 2 nasal mask",
        "resupply_months": 3,
        "has_sizes": True,
        "available_sizes": ["S", "M", "L"],
        "is_accessory": True,
        "vendors": ["Fisher & Paykel"],
        "sort_order": 31,
    },
    {
        "id": "mask-fp-evora-nasal",
        "hcpcs_code": "A7034",
        "name": "F&P Evora Nasal",
        "category": "Masks",
        "subcategory": "Nasal",
        "description": "Fisher & Paykel Evora compact nasal mask",
        "resupply_months": 3,
        "has_sizes": True,
        "available_sizes": ["XS/S", "S/M", "M/L"],
        "is_accessory": True,
        "vendors": ["Fisher & Paykel"],
        "sort_order": 32,
    },
    {
        "id": "mask-fp-solo-nasal",
        "hcpcs_code": "A7034",
        "name": "F&P Solo Nasal",
        "category": "Masks",
        "subcategory": "Nasal",
        "description": "Fisher & Paykel Solo nasal mask",
        "resupply_months": 3,
        "has_sizes": True,
        "available_sizes": ["S", "M", "L"],
        "is_accessory": True,
        "vendors": ["Fisher & Paykel"],
        "sort_order": 33,
    },

    # ══════════════════════════════════════════════════════════════════
    # MASKS — Nasal Pillow (A7033)
    # ══════════════════════════════════════════════════════════════════
    {
        "id": "mask-resmed-p10",
        "hcpcs_code": "A7033",
        "name": "ResMed AirFit P10",
        "category": "Masks",
        "subcategory": "Nasal Pillow",
        "description": "Nasal pillow mask, ultra-quiet",
        "resupply_months": 1,
        "has_sizes": True,
        "available_sizes": ["XS", "S", "M"],
        "is_accessory": True,
        "vendors": ["PPM", "ResMed"],
        "sort_order": 40,
    },
    {
        "id": "mask-resmed-p30i",
        "hcpcs_code": "A7033",
        "name": "ResMed AirFit P30i",
        "category": "Masks",
        "subcategory": "Nasal Pillow",
        "description": "Nasal pillow mask with top-of-head tube connection",
        "resupply_months": 1,
        "has_sizes": True,
        "available_sizes": ["S", "STD"],
        "is_accessory": True,
        "vendors": ["PPM", "ResMed"],
        "sort_order": 41,
    },
    {
        "id": "mask-3b-rio2",
        "hcpcs_code": "A7033",
        "name": "3B RIO II Nasal Pillow",
        "category": "Masks",
        "subcategory": "Nasal Pillow",
        "description": "RIO II nasal pillow mask, complete assembly",
        "resupply_months": 1,
        "has_sizes": True,
        "available_sizes": ["S", "M", "L"],
        "is_accessory": True,
        "vendors": ["3B Medical", "PPM"],
        "manufacturer_sku": "RII1002",
        "sort_order": 42,
    },
    {
        "id": "mask-fp-brevida",
        "hcpcs_code": "A7033",
        "name": "F&P Brevida Nasal Pillow",
        "category": "Masks",
        "subcategory": "Nasal Pillow",
        "description": "Fisher & Paykel Brevida nasal pillow mask",
        "resupply_months": 1,
        "has_sizes": True,
        "available_sizes": ["XS/S", "M/L"],
        "is_accessory": True,
        "vendors": ["Fisher & Paykel"],
        "sort_order": 43,
    },
    {
        "id": "mask-fp-nova-micro",
        "hcpcs_code": "A7033",
        "name": "F&P Nova Micro Nasal Pillow",
        "category": "Masks",
        "subcategory": "Nasal Pillow",
        "description": "Fisher & Paykel Nova Micro nasal pillow mask",
        "resupply_months": 1,
        "has_sizes": True,
        "available_sizes": ["XS/S", "M/L"],
        "is_accessory": True,
        "vendors": ["Fisher & Paykel"],
        "sort_order": 44,
    },
    {
        "id": "mask-fp-solo-pillows",
        "hcpcs_code": "A7033",
        "name": "F&P Solo Nasal Pillow",
        "category": "Masks",
        "subcategory": "Nasal Pillow",
        "description": "Fisher & Paykel Solo nasal pillow mask",
        "resupply_months": 1,
        "has_sizes": True,
        "available_sizes": ["S", "M", "L"],
        "is_accessory": True,
        "vendors": ["Fisher & Paykel"],
        "sort_order": 45,
    },

    # ══════════════════════════════════════════════════════════════════
    # REPLACEMENT CUSHIONS / PILLOWS
    # ══════════════════════════════════════════════════════════════════
    {
        "id": "cushion-full-face",
        "hcpcs_code": "A7031",
        "name": "Replacement Cushion — Full Face",
        "category": "Replacement Parts",
        "subcategory": "Cushions",
        "description": "Replacement cushion for full face mask (all manufacturers)",
        "resupply_months": 1,
        "has_sizes": True,
        "available_sizes": ["XS", "S", "S/M", "M", "M/L", "L", "XL"],
        "is_accessory": True,
        "sort_order": 50,
    },
    {
        "id": "cushion-nasal",
        "hcpcs_code": "A7032",
        "name": "Replacement Cushion — Nasal",
        "category": "Replacement Parts",
        "subcategory": "Cushions",
        "description": "Replacement cushion for nasal mask (all manufacturers)",
        "resupply_months": 1,
        "has_sizes": True,
        "available_sizes": ["XS", "S", "S/M", "M", "M/L", "L"],
        "is_accessory": True,
        "sort_order": 51,
    },
    {
        "id": "cushion-nasal-pillow",
        "hcpcs_code": "A7033",
        "name": "Replacement Nasal Pillow Cushion",
        "category": "Replacement Parts",
        "subcategory": "Pillows",
        "description": "Replacement pillow insert for nasal pillow masks",
        "resupply_months": 1,
        "has_sizes": True,
        "available_sizes": ["XS", "S", "M", "L"],
        "is_accessory": True,
        "sort_order": 52,
    },

    # ══════════════════════════════════════════════════════════════════
    # ACCESSORIES — Tubing
    # ══════════════════════════════════════════════════════════════════
    {
        "id": "tubing-heated-resmed",
        "hcpcs_code": "A4604",
        "name": "ResMed ClimateLine Air Heated Tube",
        "category": "Accessories",
        "subcategory": "Tubing",
        "description": "Heated tubing for AirSense 10/11",
        "resupply_months": 3,
        "is_accessory": True,
        "vendors": ["PPM", "ResMed"],
        "sort_order": 60,
    },
    {
        "id": "tubing-heated-3b",
        "hcpcs_code": "A4604",
        "name": "3B Luna G3 Heated Tubing",
        "category": "Accessories",
        "subcategory": "Tubing",
        "description": "Integrated heated tubing for Luna G3",
        "resupply_months": 3,
        "is_accessory": True,
        "vendors": ["3B Medical", "PPM"],
        "manufacturer_sku": "LG3HT",
        "sort_order": 61,
    },
    {
        "id": "tubing-heated-philips",
        "hcpcs_code": "A4604",
        "name": "Philips 15mm Heated Tube",
        "category": "Accessories",
        "subcategory": "Tubing",
        "description": "15mm heated tube for DreamStation",
        "resupply_months": 3,
        "is_accessory": True,
        "vendors": ["PPM", "Philips"],
        "sort_order": 62,
    },
    {
        "id": "tubing-standard",
        "hcpcs_code": "A7037",
        "name": "Standard Tubing (Non-Heated)",
        "category": "Accessories",
        "subcategory": "Tubing",
        "description": "Standard 6ft tubing, non-heated",
        "resupply_months": 2,
        "is_accessory": True,
        "sort_order": 63,
    },

    # ══════════════════════════════════════════════════════════════════
    # ACCESSORIES — Headgear / Chinstrap
    # ══════════════════════════════════════════════════════════════════
    {
        "id": "headgear",
        "hcpcs_code": "A7035",
        "name": "Headgear",
        "category": "Accessories",
        "subcategory": "Headgear",
        "description": "Replacement headgear for PAP mask (all manufacturers)",
        "resupply_months": 6,
        "has_sizes": True,
        "available_sizes": ["S", "M", "L"],
        "is_accessory": True,
        "sort_order": 70,
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
        "sort_order": 71,
    },

    # ══════════════════════════════════════════════════════════════════
    # ACCESSORIES — Filters
    # ══════════════════════════════════════════════════════════════════
    {
        "id": "filter-disposable",
        "hcpcs_code": "A7038",
        "name": "Filter — Disposable",
        "category": "Accessories",
        "subcategory": "Filters",
        "description": "Disposable ultra-fine filter for PAP device",
        "resupply_months": 1,
        "resupply_qty": 2,
        "is_accessory": True,
        "sort_order": 80,
    },
    {
        "id": "filter-nondisposable",
        "hcpcs_code": "A7039",
        "name": "Filter — Reusable (Pollen)",
        "category": "Accessories",
        "subcategory": "Filters",
        "description": "Reusable pollen filter for PAP device",
        "resupply_months": 6,
        "is_accessory": True,
        "sort_order": 81,
    },

    # ══════════════════════════════════════════════════════════════════
    # ACCESSORIES — Humidifier Chambers
    # ══════════════════════════════════════════════════════════════════
    {
        "id": "chamber-resmed",
        "hcpcs_code": "A7046",
        "name": "ResMed HumidAir Standard Tub",
        "category": "Accessories",
        "subcategory": "Humidifier",
        "description": "Replacement water chamber for AirSense 10/11",
        "resupply_months": 3,
        "is_accessory": True,
        "vendors": ["PPM", "ResMed"],
        "sort_order": 90,
    },
    {
        "id": "chamber-3b",
        "hcpcs_code": "A7046",
        "name": "3B Luna G3 Water Chamber",
        "category": "Accessories",
        "subcategory": "Humidifier",
        "description": "Replacement water chamber for Luna G3",
        "resupply_months": 3,
        "is_accessory": True,
        "vendors": ["3B Medical", "PPM"],
        "manufacturer_sku": "LG34510",
        "sort_order": 91,
    },
    {
        "id": "chamber-philips",
        "hcpcs_code": "A7046",
        "name": "Philips DreamStation 2 Humidifier Tank",
        "category": "Accessories",
        "subcategory": "Humidifier",
        "description": "Replacement humidifier water tank for DreamStation 2",
        "resupply_months": 3,
        "is_accessory": True,
        "vendors": ["PPM", "Philips"],
        "sort_order": 92,
    },

    # ══════════════════════════════════════════════════════════════════
    # ACCESSORIES — Other
    # ══════════════════════════════════════════════════════════════════
    {
        "id": "exhalation-port",
        "hcpcs_code": "A7045",
        "name": "Exhalation Port / Swivel",
        "category": "Accessories",
        "subcategory": "Other",
        "description": "Replacement exhalation port with or without swivel",
        "is_accessory": True,
        "sort_order": 100,
    },
    {
        "id": "modem-3b-wifi",
        "hcpcs_code": "A9279",
        "name": "3B WiFi Module",
        "category": "Accessories",
        "subcategory": "Connectivity",
        "description": "WiFi data module for Luna G3",
        "is_accessory": True,
        "vendors": ["3B Medical"],
        "manufacturer_sku": "LG21010",
        "sort_order": 101,
    },
    {
        "id": "modem-3b-cellular",
        "hcpcs_code": "A9279",
        "name": "3B Cellular Modem",
        "category": "Accessories",
        "subcategory": "Connectivity",
        "description": "Cellular data modem for Luna G3",
        "is_accessory": True,
        "vendors": ["3B Medical"],
        "manufacturer_sku": "LG21020",
        "sort_order": 102,
    },
    {
        "id": "cleaner-lumin",
        "hcpcs_code": "",
        "name": "Lumin UVC CPAP Cleaner",
        "category": "Accessories",
        "subcategory": "Cleaning",
        "description": "3B Lumin UV-C sanitizing device for masks and accessories",
        "is_accessory": True,
        "vendors": ["3B Medical"],
        "manufacturer_sku": "LM3000",
        "sort_order": 103,
    },
]

# Vendor ordering portals (V1: link out, V2+: direct integration)
VENDOR_PORTALS = {
    "In-House": {
        "name": "In-House Stock",
        "order_url": "",
        "notes": "Stocked on-site — managed via inventory UI",
    },
    "PPM": {
        "name": "PPM Fulfillment",
        "order_url": "https://dev.ppmfulfillment.com/Login.aspx",
        "notes": "Direct DME fulfillment — ships ResMed, Philips, 3B Medical products",
    },
    "VGM": {
        "name": "VGM & Associates",
        "order_url": "https://www.vgm.com/login/?returnURL=%2fportal%2f",
        "notes": "Group purchasing organization — order via VGM portal",
    },
    "Fisher & Paykel": {
        "name": "Fisher & Paykel Healthcare",
        "order_url": "",
        "notes": "Direct vendor — STRC account #0000110728. Masks, humidifiers, respiratory therapy.",
    },
    "3B Medical": {
        "name": "3B Medical / React Health",
        "order_url": "",
        "notes": "Luna G3 devices, RIO II/Siesta masks, Lumin cleaners. Price list PS.SL.0264 REV H.",
    },
    "ResMed": {
        "name": "ResMed",
        "order_url": "",
        "notes": "AirSense/AirCurve devices, AirFit/AirTouch masks. Ordered through PPM or direct.",
    },
    "Philips": {
        "name": "Philips Respironics",
        "order_url": "",
        "notes": "DreamStation devices, DreamWear/DreamWisp masks. Ordered through PPM.",
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
                vendors, device_types, is_machine, is_accessory, active, sort_order,
                manufacturer_sku)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
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
                p.get("manufacturer_sku", ""),
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

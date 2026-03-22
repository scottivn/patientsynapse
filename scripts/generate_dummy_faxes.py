#!/usr/bin/env python3
"""
Generate 100 dummy scanned-fax files for testing the PatientSynapse OCR pipeline.

Produces image-based PDFs, TIFFs, PNGs, and JPEGs that replicate
the look and content of real faxes received by a sleep medicine practice.
"""

import os
import uuid
import random
import textwrap
from datetime import date, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DPI = 200
PAGE_W, PAGE_H = int(8.5 * DPI), int(11 * DPI)  # 1700 x 2200
MARGIN_L = int(0.75 * DPI)
MARGIN_R = PAGE_W - int(0.75 * DPI)
MARGIN_T = int(0.9 * DPI)   # leave room for fax header
CONTENT_W = MARGIN_R - MARGIN_L
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IncomingFaxes")

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
_FONT_PATH = "/System/Library/Fonts/Helvetica.ttc"

def _font(size, bold=False):
    try:
        return ImageFont.truetype(_FONT_PATH, size, index=1 if bold else 0)
    except Exception:
        return ImageFont.load_default()

F_HDR    = _font(11)
F_SMALL  = _font(13)
F_NORM   = _font(16)
F_MED    = _font(18)
F_MEDB   = _font(18, bold=True)
F_LG     = _font(22, bold=True)
F_XL     = _font(28, bold=True)
F_HUGE   = _font(42, bold=True)
F_FAX    = _font(60, bold=True)

# ---------------------------------------------------------------------------
# Dummy-data pools
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    "Maria","Jose","Carlos","Rosa","Miguel","Ana","Juan","Elena","Luis","Sofia",
    "Roberto","Carmen","David","Patricia","Ricardo","Linda","Fernando","Jessica",
    "Daniel","Sandra","Antonio","Rachel","James","Cynthia","Michael","Veronica",
    "William","Gabriela","Robert","Monica","Thomas","Isabel","Richard","Teresa",
    "John","Laura","Joseph","Alicia","Edward","Catherine","Albert","Donna",
    "George","Helen","Frank","Margaret","Henry","Sarah","Mark","Lisa",
]
LAST_NAMES = [
    "Garcia","Martinez","Rodriguez","Hernandez","Lopez","Gonzalez","Perez",
    "Sanchez","Ramirez","Torres","Flores","Rivera","Gomez","Diaz","Cruz",
    "Morales","Reyes","Ortiz","Gutierrez","Chavez","Ramos","Vargas","Castillo",
    "Mendoza","Ruiz","Jimenez","Alvarez","Romero","Serna","Smith","Johnson",
    "Williams","Brown","Jones","Davis","Miller","Wilson","Moore","Taylor",
]
STREETS = [
    "Medical Dr","Babcock Rd","Bandera Rd","Culebra Rd","Fredericksburg Rd",
    "Huebner Rd","Potranco Rd","Marbach Rd","Military Dr","Presa St",
    "Commerce St","Broadway","Nacogdoches Rd","Wurzbach Rd","Blanco Rd",
    "West Ave","Pleasanton Rd","Goliad Rd","Rigsby Ave","New Braunfels Ave",
    "Callaghan Rd","Ingram Rd","Evers Rd","Vance Jackson Rd","Loop 410",
    "Goldfinch Way","Bank St","Oak Valley","Pecan Grove","Cedar Elm",
]
CITIES_TX = [
    ("San Antonio", "TX", "78229"), ("San Antonio", "TX", "78240"),
    ("San Antonio", "TX", "78201"), ("San Antonio", "TX", "78204"),
    ("San Antonio", "TX", "78214"), ("San Antonio", "TX", "78245"),
    ("San Antonio", "TX", "78253"), ("San Antonio", "TX", "78216"),
    ("San Antonio", "TX", "78230"), ("San Antonio", "TX", "78249"),
    ("San Antonio", "TX", "78209"), ("San Antonio", "TX", "78223"),
    ("New Braunfels", "TX", "78130"), ("Schertz", "TX", "78154"),
    ("Boerne", "TX", "78006"), ("Seguin", "TX", "78155"),
]
REFERRING_PRACTICES = [
    ("Gonzaba Medical Group", "720 Pleasanton Rd", "San Antonio", "TX", "78214", "(210) 921-3800", "(210) 334-2862"),
    ("SATX MedFirst - Medical Center", "5979 Babcock Rd", "San Antonio", "TX", "78240", "(210) 690-5700", "(210) 558-0428"),
    ("South Texas Primary Care", "4242 Medical Dr Ste 200", "San Antonio", "TX", "78229", "(210) 616-0700", "(210) 616-0704"),
    ("Alamo Family Practice", "1303 McCullough Ave", "San Antonio", "TX", "78212", "(210) 223-6161", "(210) 223-6165"),
    ("WellMed at Ingram Park", "6101 NW Loop 410", "San Antonio", "TX", "78238", "(210) 521-8880", "(210) 521-8890"),
    ("CommuniCare Health Centers", "1100 W Villaret Blvd", "San Antonio", "TX", "78224", "(210) 233-7070", "(210) 233-7075"),
    ("Oak Hills Family Medicine", "7272 Wurzbach Rd Ste 801", "San Antonio", "TX", "78240", "(210) 614-5500", "(210) 614-5505"),
    ("Westover Hills Primary Care", "10530 Culebra Rd Ste 100", "San Antonio", "TX", "78251", "(210) 647-2200", "(210) 647-2210"),
    ("San Antonio Pulmonary Associates", "4647 Medical Dr Ste 200", "San Antonio", "TX", "78229", "(210) 614-8800", "(210) 614-8805"),
    ("Bexar County Family Medicine", "8300 Floyd Curl Dr", "San Antonio", "TX", "78229", "(210) 450-9000", "(210) 450-9010"),
    ("HealthTexas Medical Group", "5282 Medical Dr Ste 500", "San Antonio", "TX", "78229", "(210) 731-2800", "(210) 731-2810"),
    ("Northeast Family Medicine", "4400 Centergate St Ste 101", "San Antonio", "TX", "78217", "(210) 653-1500", "(210) 653-1510"),
]
REFERRING_DOCTORS = [
    "Manuel Martinez MD", "Ramani Rao FNP", "Sarah Chen MD", "David Gutierrez DO",
    "Maria Sandoval MD", "Robert Kim MD", "Patricia Flores MD", "James Wilson MD",
    "Carlos Mendoza MD", "Lisa Thompson MD", "Antonio Reyes MD", "Jennifer Lopez MD",
    "Michael Ortiz DO", "Rachel Davis FNP", "Thomas Nguyen MD", "Amanda Garcia PA-C",
    "Richard Perez MD", "Cynthia Cruz MD", "Daniel Hernandez MD", "Laura Castillo MD",
]
INSURANCE_COMPANIES = [
    ("UHC (MC) Complete Care WELM2", "hmo"), ("Blue Cross Blue Shield TX", "ppo"),
    ("Aetna Better Health", "hmo"), ("Cigna HealthSpring", "hmo"),
    ("Humana Gold Plus", "hmo"), ("TRICARE Prime-Active Duty Sponsors", "hmo"),
    ("Superior HealthPlan (Medicaid)", "hmo"), ("Molina Healthcare", "hmo"),
    ("Ambetter from Superior", "hmo"), ("Community First Health Plans", "hmo"),
    ("Medicare Part B", "ppo"), ("UnitedHealthcare Choice Plus", "ppo"),
    ("Curative - First Health", "ppo"), ("Aetna Open Access", "ppo"),
    ("BCBS Federal Employee", "ppo"), ("Cigna Open Access Plus", "ppo"),
]
SLEEP_DX_CODES = [
    ("G47.33", "Obstructive Sleep Apnea"),
    ("G47.30", "Sleep Apnea, unspecified"),
    ("R06.83", "Snoring"),
    ("G47.00", "Insomnia, unspecified"),
    ("G47.01", "Insomnia due to medical condition"),
    ("G47.09", "Other insomnia"),
    ("R40.0", "Somnolence / Daytime Sleepiness"),
    ("G47.411", "Narcolepsy with cataplexy"),
    ("G47.419", "Narcolepsy without cataplexy"),
    ("G25.81", "Restless Legs Syndrome"),
    ("G47.61", "Periodic Limb Movement Disorder"),
    ("E66.01", "Morbid Obesity due to excess calories"),
    ("R06.00", "Dyspnea, unspecified"),
    ("J98.8", "Other specified respiratory disorder"),
    ("G47.10", "Hypersomnia, unspecified"),
    ("G47.20", "Circadian rhythm sleep disorder, unspecified"),
]
SLEEP_CPT_CODES = [
    ("95810", "Polysomnography (PSG)"),
    ("95811", "PSG with CPAP/BiPAP titration"),
    ("95800", "Home Sleep Apnea Test (HSAT)"),
    ("95801", "Portable Sleep Study"),
    ("99202", "Office visit - new patient (15-29 min)"),
    ("99203", "Office visit - new patient (30-44 min)"),
    ("99213", "Office visit - established (20-29 min)"),
    ("99214", "Office visit - established (30-39 min)"),
]
SLEEP_STUDY_TYPES = [
    "Diagnostic Polysomnography (In-Lab PSG)",
    "Split-Night Polysomnography",
    "CPAP Titration Study",
    "BiPAP Titration Study",
    "Home Sleep Apnea Test (HSAT)",
    "Multiple Sleep Latency Test (MSLT)",
    "Maintenance of Wakefulness Test (MWT)",
]
SLEEP_REASONS = [
    "excessive daytime sleepiness, loud snoring, witnessed apneas by spouse",
    "snoring with fatigue, gasping for air at night upon sleeping",
    "daytime somnolence, snoring, breathing pauses r/o OSA",
    "chronic insomnia, difficulty maintaining sleep, non-restorative sleep",
    "suspected narcolepsy, excessive sleepiness, sleep attacks",
    "restless legs, difficulty falling asleep, periodic leg movements",
    "loud snoring, morning headaches, unrefreshing sleep, BMI > 35",
    "witnessed apneas, choking at night, nocturia x3, daytime fatigue",
    "CPAP non-compliance, needs retitration, AHI elevated on current settings",
    "sleep maintenance insomnia, early morning awakening, fatigue",
    "suspected upper airway resistance syndrome, snoring, EDS",
    "obesity hypoventilation evaluation, BMI 42, hypercapnia",
]
MEDICATIONS_SLEEP = [
    "CPAP machine at 12 cmH2O", "BiPAP 15/10 cmH2O", "Modafinil 200mg daily",
    "Trazodone 50mg at bedtime", "Melatonin 5mg at bedtime",
    "Gabapentin 300mg at bedtime for RLS", "Ropinirole 0.5mg at bedtime",
    "Suvorexant 10mg at bedtime", "Zolpidem 10mg at bedtime",
]
COMORBIDITIES = [
    "Type 2 Diabetes Mellitus", "Essential Hypertension", "Obesity (BMI > 30)",
    "Morbid Obesity (BMI > 40)", "GERD", "Atrial Fibrillation",
    "CHF (Congestive Heart Failure)", "COPD", "Asthma", "Depression",
    "Anxiety", "Hypothyroidism", "Hyperlipidemia", "Chronic Pain",
    "Coronary Artery Disease", "Stroke History", "Seizure Disorder",
]
STRC_PROVIDERS = [
    "Sarah Andry DO", "Autum Simmons MD", "Robert Clarke MD",
]
STRC_PHONE = "(210) 614-6000"
STRC_FAX = "(210) 614-7728"
STRC_ADDR = "5290 Medical Dr"
STRC_CITY = "San Antonio, TX 78229"
STRC_NAME = "Sleep Therapy & Research Center"
STRC_NPI = "1386689917"

# ---------------------------------------------------------------------------
# Helper: random data generators
# ---------------------------------------------------------------------------

def rand_name():
    return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)

def rand_full_name():
    f, l = rand_name()
    return f"{f} {l}"

def rand_dob(min_age=18, max_age=85):
    age = random.randint(min_age, max_age)
    d = date.today() - timedelta(days=age * 365 + random.randint(0, 364))
    return d.strftime("%m/%d/%Y"), age

def rand_addr():
    num = random.randint(100, 19999)
    st = random.choice(STREETS)
    city, state, zipcode = random.choice(CITIES_TX)
    return f"{num} {st}", f"{city}, {state} {zipcode}"

def rand_phone():
    return f"(210) {random.randint(200,999)}-{random.randint(1000,9999)}"

def rand_fax():
    return f"(210) {random.randint(200,999)}-{random.randint(1000,9999)}"

def rand_ssn_masked():
    return f"XXX-XX-{random.randint(1000,9999)}"

def rand_member_id():
    return f"{random.randint(100000000,999999999)}"

def rand_group_num():
    return str(random.randint(10000, 99999))

def rand_npi():
    return f"1{random.randint(100000000,999999999)}"

def rand_referral_num():
    prefix = random.choice(["OP","RF","REF","AUTH","RN"])
    return f"{prefix}{random.randint(1000000000,9999999999)}"

def rand_auth_num():
    return f"{random.randint(1000000,9999999)}-{random.randint(10,99)}"

def rand_date_recent(days_back=90):
    d = date.today() - timedelta(days=random.randint(0, days_back))
    return d.strftime("%m/%d/%Y")

def rand_date_future(days_ahead=365):
    d = date.today() + timedelta(days=random.randint(30, days_ahead))
    return d.strftime("%m/%d/%Y")

def rand_insurance():
    name, ins_type = random.choice(INSURANCE_COMPANIES)
    return {
        "company": name, "type": ins_type.upper(),
        "member_id": rand_member_id(), "group": rand_group_num(),
    }

def rand_practice():
    p = random.choice(REFERRING_PRACTICES)
    return {
        "name": p[0], "addr": p[1], "city": f"{p[2]}, {p[3]} {p[4]}",
        "phone": p[5], "fax": p[6],
    }

def rand_dx(n=None):
    n = n or random.randint(1, 3)
    return random.sample(SLEEP_DX_CODES, min(n, len(SLEEP_DX_CODES)))

def rand_vitals():
    ht_in = random.randint(60, 76)
    wt = random.randint(140, 380)
    bmi = round(wt / (ht_in ** 2) * 703, 1)
    bp_s = random.randint(110, 165)
    bp_d = random.randint(60, 95)
    hr = random.randint(58, 100)
    rr = random.randint(14, 22)
    o2 = random.randint(88, 99)
    temp = round(random.uniform(97.0, 99.0), 1)
    return {
        "height": f"{ht_in // 12} ft {ht_in % 12} in",
        "weight": f"{wt} lbs", "bmi": str(bmi),
        "bp": f"{bp_s}/{bp_d}", "hr": str(hr), "rr": str(rr),
        "o2": f"{o2}%", "temp": f"{temp} F",
    }

# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def new_page():
    """Create a new blank page with slight gray background (scanned look)."""
    bg = random.randint(238, 248)
    img = Image.new("L", (PAGE_W, PAGE_H), bg)
    return img, ImageDraw.Draw(img)

def add_fax_header(draw, sender_name, page_num, total_pages, fax_date=None):
    """Draw fax transmission header strip at top of page."""
    fax_date = fax_date or rand_date_recent(30)
    hour = random.randint(6, 22)
    minute = random.randint(0, 59)
    time_str = f"{hour:02d}:{minute:02d}:{random.randint(0,59):02d}"
    left = f"  {fax_date}  {time_str}  Fax Server"
    right = f"pg {page_num} of {total_pages}"
    mid = f"->    {STRC_FAX.replace('(','').replace(') ','')}  {sender_name[:30]}"
    draw.text((20, 8), left, fill=40, font=F_HDR)
    draw.text((PAGE_W // 3, 8), mid, fill=40, font=F_HDR)
    draw.text((PAGE_W - 200, 8), right, fill=40, font=F_HDR)

def draw_line(draw, y, x1=None, x2=None, width=2):
    x1 = x1 or MARGIN_L
    x2 = x2 or MARGIN_R
    draw.line([(x1, y), (x2, y)], fill=30, width=width)

def draw_text_wrapped(draw, text, x, y, font, max_w=None, fill=20, line_spacing=4):
    """Draw wrapped text, return y after last line."""
    max_w = max_w or (MARGIN_R - x)
    # Estimate chars per line from font size
    avg_char_w = font.size * 0.55
    chars = max(20, int(max_w / avg_char_w))
    lines = []
    for paragraph in text.split("\n"):
        if paragraph.strip():
            lines.extend(textwrap.wrap(paragraph, width=chars))
        else:
            lines.append("")
    for line in lines:
        draw.text((x, y), line, fill=fill, font=font)
        y += font.size + line_spacing
    return y

def draw_field(draw, label, value, x, y, label_font=None, val_font=None, gap=160):
    """Draw a label: value pair."""
    label_font = label_font or F_MEDB
    val_font = val_font or F_NORM
    draw.text((x, y), label, fill=15, font=label_font)
    draw.text((x + gap, y), str(value), fill=30, font=val_font)
    return y + val_font.size + 6

def draw_box(draw, x1, y1, x2, y2, fill_color=252):
    draw.rectangle([(x1, y1), (x2, y2)], outline=40, fill=fill_color, width=2)

def add_scan_noise(img):
    """Add subtle noise to simulate scanner artifacts."""
    import numpy as np
    arr = np.array(img, dtype=np.int16)
    noise = np.random.normal(0, 2, arr.shape).astype(np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

# ---------------------------------------------------------------------------
# Document generators — each returns a list of PIL Images (pages)
# ---------------------------------------------------------------------------

def gen_fax_cover(practice, sender, fax_date=None, comment="", total_pages=1):
    """Generate a fax cover sheet page."""
    img, draw = new_page()
    fax_date = fax_date or rand_date_recent(30)
    y = MARGIN_T + 20

    draw.text((PAGE_W // 2 - 180, y), "FACSIMILE COVER LETTER", fill=10, font=F_LG)
    y += 60

    # FAX logo + table
    draw.text((MARGIN_L + 40, y + 30), "F A X", fill=20, font=F_FAX)

    tbl_x = PAGE_W // 2 - 60
    tbl_w = MARGIN_R - tbl_x
    fields = [
        ("Date & Time:", f"{fax_date} {random.randint(6,10)}:{random.randint(10,59):02d} {'AM' if random.random() > 0.5 else 'PM'}"),
        ("Deliver To:", "Bulk" if random.random() > 0.3 else STRC_NAME),
        ("Fax Number:", STRC_FAX.replace("(","").replace(") ","")),
        ("From:", sender),
        ("Phone:", practice["phone"]),
        ("Regarding:", comment[:40] if comment else ""),
    ]
    for i, (lbl, val) in enumerate(fields):
        fy = y + i * 30
        draw_box(draw, tbl_x, fy, MARGIN_R, fy + 30, fill_color=255)
        draw.text((tbl_x + 5, fy + 5), lbl, fill=20, font=F_MED)
        draw.text((tbl_x + 140, fy + 5), val, fill=35, font=F_NORM)
    y += len(fields) * 30 + 50

    # Comment section
    if comment:
        draw_box(draw, MARGIN_L, y, MARGIN_R, y + 30, fill_color=245)
        draw.text((MARGIN_L + 8, y + 5), "Comments:", fill=10, font=F_MEDB)
        y += 40
        y = draw_text_wrapped(draw, comment, MARGIN_L + 20, y, F_NORM, fill=30)
        y += 30

    # HIPAA disclaimer at bottom
    disclaimer = (
        "IMPORTANT: This facsimile transmission contains confidential information, "
        "some or all of which may be protected health information as defined by the "
        "federal Health Insurance Portability & Accountability Act (HIPAA) Privacy Rule. "
        "This transmission is intended for the exclusive use of the individual or entity "
        "to whom it is addressed and may contain information that is proprietary, privileged, "
        "confidential and/or exempt from disclosure under applicable law."
    )
    draw_text_wrapped(draw, disclaimer, MARGIN_L, PAGE_H - 260, F_SMALL, fill=60)

    # Page count
    draw.text((MARGIN_L, PAGE_H - 80), f"Number of pages including this cover sheet: {total_pages}", fill=20, font=F_MEDB)

    add_fax_header(draw, practice["name"][:25], 1, total_pages, fax_date)
    return img


def gen_patient_info_page(patient, insurance, practice, page_num, total_pages, fax_date=None):
    """Generate a patient demographics / registration page."""
    img, draw = new_page()
    add_fax_header(draw, practice["name"][:25], page_num, total_pages, fax_date)
    y = MARGIN_T

    draw.text((MARGIN_L, y), "PATIENT INFORMATION", fill=10, font=F_LG)
    draw_line(draw, y + 30)
    y += 45

    # Left column
    lx = MARGIN_L
    y = draw_field(draw, "Name:", patient["name"], lx, y)
    y = draw_field(draw, "Preferred:", patient["first"], lx, y)
    y = draw_field(draw, "Address:", patient["addr1"], lx, y)
    y = draw_field(draw, "City,State:", patient["addr2"], lx, y)
    y = draw_field(draw, "Phone:", patient["phone"], lx, y)

    # Right column (restart y)
    rx = PAGE_W // 2 + 20
    ry = MARGIN_T + 45
    ry = draw_field(draw, "Patient ID #:", patient["pid"], rx, ry)
    ry = draw_field(draw, "Date of Birth:", patient["dob"], rx, ry)
    ry = draw_field(draw, "Sex:", patient["sex"], rx, ry)
    ry = draw_field(draw, "SSN:", patient["ssn"], rx, ry)
    ry = draw_field(draw, "Referring MD:", patient["ref_doc"], rx, ry)

    y = max(y, ry) + 20
    draw.text((MARGIN_L, y), "PRIMARY INSURANCE", fill=10, font=F_LG)
    draw_line(draw, y + 28)
    y += 40

    y = draw_field(draw, "Company:", insurance["company"], lx, y, gap=140)
    y = draw_field(draw, "Insured ID:", insurance["member_id"], lx, y, gap=140)
    y = draw_field(draw, "Group:", insurance["group"], lx, y, gap=140)
    y = draw_field(draw, "Type:", insurance["type"], lx, y, gap=140)
    y = draw_field(draw, "Insured Party:", patient["name"], lx, y, gap=140)

    y += 30
    draw.text((MARGIN_L, y), "PATIENT EMPLOYMENT", fill=10, font=F_LG)
    draw_line(draw, y + 28)
    y += 40

    emp_status = random.choice(["[X]Employed  [ ]Retired  [ ]Unemployed",
                                 "[ ]Employed  [X]Retired  [ ]Unemployed",
                                 "[ ]Employed  [ ]Retired  [ ]Unemployed  [X]Disabled"])
    draw.text((MARGIN_L, y), emp_status, fill=30, font=F_NORM)
    y += 30

    if "Employed" in emp_status and emp_status.startswith("[X]"):
        employer = random.choice(["USAA","Valero Energy","HEB","SAISD","City of San Antonio",
                                   "Methodist Healthcare","Baptist Health","Rackspace","CPS Energy","USPS"])
        y = draw_field(draw, "Employer:", employer, lx, y, gap=140)

    # Date at bottom
    draw.text((MARGIN_L, PAGE_H - 80), rand_date_recent(30), fill=40, font=F_NORM)
    return img


def gen_referral_form(patient, insurance, practice, doctor, dx_list, page_num, total_pages, fax_date=None):
    """Generate a referral order form (PCP -> sleep center)."""
    img, draw = new_page()
    add_fax_header(draw, practice["name"][:25], page_num, total_pages, fax_date)
    y = MARGIN_T

    # Practice header
    draw.text((MARGIN_L, y), practice["name"], fill=10, font=F_MED)
    draw.text((MARGIN_L, y + 22), f"{practice['addr']}, {practice['city']}", fill=40, font=F_SMALL)
    draw.text((MARGIN_L, y + 38), f"{practice['phone']}  Fax: {practice['fax']}", fill=40, font=F_SMALL)

    # Date
    ref_date = fax_date or rand_date_recent(30)
    draw.text((MARGIN_R - 200, y + 5), ref_date, fill=30, font=F_NORM)
    y += 70

    # Title
    draw.text((PAGE_W // 2 - 100, y), "Referral Form", fill=10, font=F_XL)
    y += 50

    # Provider info box
    draw_box(draw, MARGIN_L, y, PAGE_W // 2 - 20, y + 110)
    draw.text((MARGIN_L + 8, y + 5), "Authorizing Provider:", fill=20, font=F_MEDB)
    draw.text((MARGIN_L + 200, y + 5), doctor, fill=30, font=F_NORM)
    draw.text((MARGIN_L + 8, y + 28), "Phone:", fill=20, font=F_MEDB)
    draw.text((MARGIN_L + 200, y + 28), practice["phone"], fill=30, font=F_NORM)
    draw.text((MARGIN_L + 8, y + 51), "Fax:", fill=20, font=F_MEDB)
    draw.text((MARGIN_L + 200, y + 51), practice["fax"], fill=30, font=F_NORM)

    # Service provider box
    sp_x = PAGE_W // 2 + 10
    draw_box(draw, sp_x, y, MARGIN_R, y + 110)
    draw.text((sp_x + 8, y + 5), "Service Provider:", fill=20, font=F_MEDB)
    draw.text((sp_x + 170, y + 5), STRC_NAME, fill=30, font=F_NORM)
    draw.text((sp_x + 8, y + 28), "Phone:", fill=20, font=F_MEDB)
    draw.text((sp_x + 170, y + 28), STRC_PHONE, fill=30, font=F_NORM)
    draw.text((sp_x + 8, y + 51), "Fax:", fill=20, font=F_MEDB)
    draw.text((sp_x + 170, y + 51), STRC_FAX, fill=30, font=F_NORM)
    y += 125

    # Patient info box
    draw_box(draw, MARGIN_L, y, MARGIN_R, y + 60)
    draw.text((MARGIN_L + 8, y + 5), "Patient Name:", fill=20, font=F_MEDB)
    draw.text((MARGIN_L + 150, y + 5), patient["name"], fill=30, font=F_NORM)
    draw.text((MARGIN_L + 8, y + 28), "Home Phone:", fill=20, font=F_MEDB)
    draw.text((MARGIN_L + 150, y + 28), patient["phone"], fill=30, font=F_NORM)
    draw.text((sp_x + 8, y + 5), "DOB:", fill=20, font=F_MEDB)
    draw.text((sp_x + 60, y + 5), patient["dob"], fill=30, font=F_NORM)
    draw.text((sp_x + 200, y + 5), f"Age: {patient['age']}", fill=30, font=F_NORM)
    draw.text((sp_x + 8, y + 28), "Sex:", fill=20, font=F_MEDB)
    draw.text((sp_x + 60, y + 28), patient["sex"], fill=30, font=F_NORM)
    y += 75

    # Insurance box
    draw_box(draw, MARGIN_L, y, PAGE_W // 2 - 20, y + 80)
    draw.text((MARGIN_L + 8, y + 5), "Primary Ins:", fill=20, font=F_MEDB)
    draw.text((MARGIN_L + 120, y + 5), insurance["company"][:28], fill=30, font=F_NORM)
    draw.text((MARGIN_L + 8, y + 28), "Group:", fill=20, font=F_MEDB)
    draw.text((MARGIN_L + 120, y + 28), insurance["group"], fill=30, font=F_NORM)
    draw.text((MARGIN_L + 8, y + 51), "Insured ID:", fill=20, font=F_MEDB)
    draw.text((MARGIN_L + 120, y + 51), insurance["member_id"], fill=30, font=F_NORM)
    y += 95

    # Diagnosis & order
    draw_box(draw, MARGIN_L, y, MARGIN_R, y + 30, fill_color=235)
    draw.text((MARGIN_L + 8, y + 5), "Code", fill=10, font=F_MEDB)
    draw.text((MARGIN_L + 150, y + 5), "Description", fill=10, font=F_MEDB)
    draw.text((sp_x, y + 5), "Diagnoses", fill=10, font=F_MEDB)
    y += 35

    # CPT and diagnoses
    cpt = random.choice(SLEEP_CPT_CODES[:4])
    dx_text = "  ".join([f"{c} - {d}" for c, d in dx_list])
    draw.text((MARGIN_L + 8, y), cpt[0], fill=30, font=F_NORM)
    draw.text((MARGIN_L + 150, y), f"*{cpt[1]}", fill=30, font=F_NORM)
    draw_text_wrapped(draw, dx_text, sp_x, y, F_SMALL, max_w=MARGIN_R - sp_x - 10, fill=30)
    y += 30

    # Order details
    start = rand_date_recent(14)
    end = rand_date_future(365)
    visits = random.choice([1, 2, 3, 5, 6, 10, 12, 24])
    y += 15
    y = draw_field(draw, "Order Number:", rand_auth_num(), MARGIN_L + 150, y, gap=150)
    y = draw_field(draw, "Auth#:", rand_referral_num(), MARGIN_L + 150, y, gap=150)
    y = draw_field(draw, "Maximum Visits:", str(visits), MARGIN_L + 150, y, gap=150)
    y = draw_field(draw, "Start Date:", start, MARGIN_L + 150, y, gap=150)
    draw.text((sp_x, y - 24), f"End Date:    {end}", fill=30, font=F_NORM)
    y = draw_field(draw, "Duration:", f"{random.choice([90,180,365])} Days", MARGIN_L + 150, y, gap=150)
    y = draw_field(draw, "Signed By:", doctor, MARGIN_L + 150, y, gap=150)
    y = draw_field(draw, "NPI:", rand_npi(), MARGIN_L + 150, y, gap=150)
    y = draw_field(draw, "Reason:", random.choice(SLEEP_REASONS)[:60], MARGIN_L + 150, y, gap=150)

    # Signature line
    y += 40
    draw.text((PAGE_W // 2 - 150, y + 35), f"Electronically Signed by: {doctor}", fill=30, font=F_NORM)

    return img


def gen_progress_note(patient, practice, doctor, page_num, total_pages, fax_date=None):
    """Generate a PCP progress note / office visit page."""
    img, draw = new_page()
    add_fax_header(draw, practice["name"][:25], page_num, total_pages, fax_date)
    y = MARGIN_T

    # Header
    draw.text((MARGIN_L, y), practice["name"], fill=10, font=F_MED)
    draw.text((MARGIN_L, y + 22), f"{practice['addr']}, {practice['city']}", fill=40, font=F_SMALL)
    draw.text((MARGIN_L, y + 38), f"{practice['phone']}  Fax: {practice['fax']}", fill=40, font=F_SMALL)
    draw.text((MARGIN_R - 120, y), "Office Visit", fill=30, font=F_MED)
    y += 65

    draw.text((MARGIN_L, y), f"{patient['name']}", fill=10, font=F_LG)
    draw.text((MARGIN_L, y + 28), f"{patient['sex']}  DOB: {patient['dob']}", fill=30, font=F_NORM)
    draw.text((PAGE_W // 2, y + 28), f"Ins: {patient['insurance']['company'][:30]}", fill=30, font=F_NORM)
    y += 60
    draw_line(draw, y)
    y += 15

    visit_date = fax_date or rand_date_recent(60)
    draw.text((MARGIN_L, y), f"{visit_date} - Office Visit", fill=10, font=F_MEDB)
    y = draw_field(draw, "Provider:", doctor, MARGIN_L, y + 25, gap=100)
    y = draw_field(draw, "Location:", practice["name"], MARGIN_L, y, gap=100)
    y += 15

    # CC and HPI
    draw.text((MARGIN_L, y), "PCP:", fill=20, font=F_MEDB)
    draw.text((MARGIN_L + 50, y), doctor, fill=30, font=F_NORM)
    y += 30

    cc = random.choice([
        "Sleep apnea evaluation", "Snoring and daytime sleepiness",
        "Referral to sleep medicine", "Follow up chronic conditions + sleep complaints",
        "Annual wellness visit - sleep concerns noted", "Fatigue evaluation",
    ])
    draw.text((MARGIN_L, y), "CC:", fill=20, font=F_MEDB)
    draw.text((MARGIN_L + 40, y), cc, fill=30, font=F_NORM)
    y += 35

    draw.text((MARGIN_L, y), "History of Present Illness:", fill=10, font=F_MEDB)
    y += 25
    hpi_templates = [
        f"Patient presents for evaluation of {random.choice(['chronic snoring','excessive daytime sleepiness','witnessed apneas','fatigue and poor sleep'])}. "
        f"Symptoms have been present for {random.choice(['several months','over a year','the past 6 months','approximately 2 years'])}. "
        f"Spouse reports {random.choice(['loud snoring with occasional pauses in breathing','gasping and choking at night','restless sleep with frequent awakenings'])}. "
        f"Patient endorses {random.choice(['morning headaches','unrefreshing sleep','difficulty concentrating','nocturia x2-3 per night'])}. "
        f"BMI is {random.choice(['elevated at 32','significantly elevated at 38','in the obese range at 35','41 indicating morbid obesity'])}.",

        f"Patient is a {patient['age']}-year-old {patient['sex'].lower()} who presents with complaints of "
        f"{random.choice(['poor sleep quality','chronic insomnia','excessive sleepiness during the day','difficulty staying asleep'])}. "
        f"Reports {random.choice(['falling asleep while driving','nodding off at work','difficulty with daily tasks due to fatigue','sleeping 10+ hours and still feeling tired'])}. "
        f"Epworth Sleepiness Scale score: {random.randint(8,21)}/24. "
        f"Recommend referral to sleep specialist for further evaluation.",
    ]
    y = draw_text_wrapped(draw, random.choice(hpi_templates), MARGIN_L, y, F_NORM, fill=30)
    y += 20

    # Vitals
    vitals = rand_vitals()
    draw.text((MARGIN_L, y), "Vital Signs", fill=10, font=F_MEDB)
    y += 25
    y = draw_field(draw, "Height:", vitals["height"], MARGIN_L, y, gap=100)
    y = draw_field(draw, "Weight:", vitals["weight"], MARGIN_L, y, gap=100)
    draw.text((PAGE_W // 2, y - 50), f"BMI: {vitals['bmi']}", fill=30, font=F_NORM)
    draw.text((PAGE_W // 2, y - 25), f"BP: {vitals['bp']}", fill=30, font=F_NORM)
    y = draw_field(draw, "Temp:", vitals["temp"], MARGIN_L, y, gap=100)
    y = draw_field(draw, "Pulse:", vitals["hr"], MARGIN_L, y, gap=100)
    y = draw_field(draw, "O2 Sat:", vitals["o2"], MARGIN_L, y, gap=100)
    y += 15

    # Assessment
    draw.text((MARGIN_L, y), "Assessment & Plan:", fill=10, font=F_MEDB)
    y += 25
    dx = rand_dx(2)
    for code, desc in dx:
        draw.text((MARGIN_L, y), f"• {desc} ({code})", fill=30, font=F_NORM)
        y += 22
    y += 10
    plan = random.choice([
        f"Refer to {STRC_NAME} for sleep study evaluation. Fax referral with records.",
        f"Order: Polysomnography. Referral to {STRC_NAME} for sleep medicine consult.",
        f"HSAT ordered. If positive for OSA, will refer to {STRC_NAME} for CPAP titration.",
        f"Refer to sleep medicine ({STRC_NAME}) for evaluation of suspected OSA. Patient counseled on sleep hygiene.",
    ])
    y = draw_text_wrapped(draw, plan, MARGIN_L, y, F_NORM, fill=30)

    return img


def gen_tricare_auth(patient, page_num, total_pages, fax_date=None):
    """Generate a TRICARE/TriWest authorization letter."""
    img, draw = new_page()
    fax_date = fax_date or rand_date_recent(14)
    add_fax_header(draw, "DOMA Technologies", page_num, total_pages, fax_date)
    y = MARGIN_T

    # TRICARE logo placeholder
    draw.text((MARGIN_L, y), "TRICARE", fill=20, font=F_LG)
    draw.text((MARGIN_L, y + 28), "PO Box 2399 | Virginia Beach, VA 23450", fill=50, font=F_SMALL)
    draw.text((MARGIN_R - 80, y), "UM4000", fill=50, font=F_SMALL)
    y += 60

    draw.text((MARGIN_R - 200, y), fax_date, fill=30, font=F_NORM)
    y += 40

    # Addressee
    draw.text((MARGIN_L, y), STRC_NAME.upper(), fill=20, font=F_MED)
    y += 22
    draw.text((MARGIN_L, y), STRC_ADDR, fill=30, font=F_NORM)
    y += 20
    draw.text((MARGIN_L, y), STRC_CITY.upper(), fill=30, font=F_NORM)
    y += 40

    # Sponsor info (right side)
    rx = PAGE_W // 2 + 40
    ry = y - 80
    dod_id = str(random.randint(1000000000, 9999999999))
    sponsor = random.choice(["SELF","SPOUSE","CHILD"])
    plan_type = random.choice(["TRICARE Prime-Active Duty Sponsors","TRICARE Select","TRICARE Prime Remote"])
    ry = draw_field(draw, "Sponsor Name:", sponsor, rx, ry, gap=170)
    ry = draw_field(draw, "Sponsor SSN:", rand_ssn_masked(), rx, ry, gap=170)
    ry = draw_field(draw, "Beneficiary:", patient["name"].upper(), rx, ry, gap=170)
    ry = draw_field(draw, "DOD ID:", dod_id, rx, ry, gap=170)
    ry = draw_field(draw, "DOB:", patient["dob"], rx, ry, gap=170)
    ry = draw_field(draw, "Phone:", patient["phone"], rx, ry, gap=170)
    ry = draw_field(draw, "Plan Type:", plan_type, rx, ry, gap=170)

    y = max(y, ry) + 15
    ref_num = f"00{random.randint(10000000,99999999)}"
    start = rand_date_recent(14)
    end = rand_date_future(365)
    strc_prov = random.choice(STRC_PROVIDERS)

    draw.text((MARGIN_L, y), f"RE: TriWest Reference Number: {ref_num}", fill=20, font=F_MED)
    y += 22
    draw.text((MARGIN_L + 30, y), f"Valid Date Range: {start} - {end}", fill=30, font=F_NORM)
    y += 22

    # Requesting provider
    draw.text((rx, y - 44), f"Requesting Provider:", fill=20, font=F_MEDB)
    draw.text((rx, y - 22), strc_prov.upper(), fill=30, font=F_NORM)
    draw.text((rx, y), f"NPI: {rand_npi()}", fill=30, font=F_NORM)
    y += 30

    draw.text((MARGIN_L, y), f"Dear {STRC_NAME.upper()}:", fill=20, font=F_MED)
    y += 30
    draw.text((MARGIN_L, y), "TriWest Healthcare Alliance has received a request for the following service(s).", fill=30, font=F_NORM)
    y += 40

    draw.text((MARGIN_L, y), "Provider Orders", fill=10, font=F_MEDB)
    draw_line(draw, y + 22)
    y += 35

    dx = random.choice(SLEEP_DX_CODES)
    draw.text((MARGIN_L + 20, y), f"VISIT TYPE:  EVALUATE AND TREAT", fill=30, font=F_NORM)
    y += 22
    draw.text((MARGIN_L + 20, y), f"DX CODE:  {dx[0]} - {dx[1]}", fill=30, font=F_NORM)
    y += 22
    draw.text((MARGIN_L + 20, y), f"MESSAGE:", fill=20, font=F_MEDB)
    y += 22
    y = draw_text_wrapped(draw, random.choice(SLEEP_REASONS), MARGIN_L + 20, y, F_NORM, fill=30)
    y += 25

    # Service table
    draw.text((MARGIN_L, y), "Service", fill=10, font=F_MEDB)
    draw_line(draw, y + 20)
    y += 30
    visits = random.choice([1, 2, 5, 6])
    draw.text((MARGIN_L, y), f"BEGIN DATE   END DATE     LOCATION   STATUS      QTY   TYPE", fill=20, font=F_MEDB)
    y += 22
    draw.text((MARGIN_L, y), f"{start}   {end}   Office     Approved    {visits}     Visit{'s' if visits > 1 else ''}", fill=30, font=F_NORM)
    y += 30

    cpt = random.choice(SLEEP_CPT_CODES[:4])
    draw.text((MARGIN_L, y), f"CPT: {cpt[0]}: {cpt[1]}", fill=30, font=F_NORM)

    # Footer
    draw.text((MARGIN_L, PAGE_H - 80), "TRICARE is administered by TriWest Healthcare Alliance in the West Region.", fill=60, font=F_SMALL)
    draw.text((MARGIN_L, PAGE_H - 60), f"DOD ID: {dod_id}", fill=60, font=F_SMALL)

    return img


def gen_prior_auth_letter(patient, insurance, approved=True, page_num=1, total_pages=1, fax_date=None):
    """Generate an insurance prior authorization approval or denial letter."""
    img, draw = new_page()
    fax_date = fax_date or rand_date_recent(14)
    add_fax_header(draw, insurance["company"][:25], page_num, total_pages, fax_date)
    y = MARGIN_T

    draw.text((MARGIN_L, y), insurance["company"], fill=10, font=F_LG)
    y += 35
    draw.text((MARGIN_L, y), "Prior Authorization Department", fill=30, font=F_MED)
    y += 25
    draw.text((MARGIN_L, y), f"Date: {fax_date}", fill=30, font=F_NORM)
    y += 40

    draw.text((MARGIN_L, y), f"RE: Prior Authorization {'APPROVAL' if approved else 'DENIAL'}", fill=10, font=F_LG)
    y += 35
    draw_line(draw, y)
    y += 20

    auth_num = rand_referral_num()
    y = draw_field(draw, "Auth Number:", auth_num, MARGIN_L, y, gap=180)
    y = draw_field(draw, "Patient:", patient["name"], MARGIN_L, y, gap=180)
    y = draw_field(draw, "DOB:", patient["dob"], MARGIN_L, y, gap=180)
    y = draw_field(draw, "Member ID:", insurance["member_id"], MARGIN_L, y, gap=180)
    y = draw_field(draw, "Group:", insurance["group"], MARGIN_L, y, gap=180)
    y += 10
    y = draw_field(draw, "Provider:", random.choice(STRC_PROVIDERS), MARGIN_L, y, gap=180)
    y = draw_field(draw, "Facility:", STRC_NAME, MARGIN_L, y, gap=180)
    y = draw_field(draw, "NPI:", STRC_NPI, MARGIN_L, y, gap=180)
    y += 10

    dx = rand_dx(2)
    cpt = random.choice(SLEEP_CPT_CODES[:4])
    y = draw_field(draw, "Requested:", cpt[1], MARGIN_L, y, gap=180)
    y = draw_field(draw, "CPT Code:", cpt[0], MARGIN_L, y, gap=180)
    for code, desc in dx:
        y = draw_field(draw, "Diagnosis:", f"{code} - {desc}", MARGIN_L, y, gap=180)
    y += 10

    start = rand_date_recent(7)
    end = rand_date_future(180)
    visits = random.choice([1, 2, 3, 5])
    y = draw_field(draw, "Effective:", f"{start} through {end}", MARGIN_L, y, gap=180)
    y = draw_field(draw, "Visits:", str(visits), MARGIN_L, y, gap=180)
    y += 20

    if approved:
        draw.text((MARGIN_L, y), "DETERMINATION: APPROVED", fill=10, font=F_LG)
        y += 35
        text = (
            f"This letter confirms that the above-referenced service has been authorized. "
            f"This authorization is valid for {visits} visit(s) from {start} through {end}. "
            f"Please note that this authorization does not guarantee payment. Payment is subject to "
            f"member eligibility and benefit verification at the time of service."
        )
    else:
        draw.text((MARGIN_L, y), "DETERMINATION: DENIED", fill=10, font=F_LG)
        y += 35
        denial_reason = random.choice([
            "The requested service does not meet medical necessity criteria per clinical guidelines.",
            "Insufficient clinical documentation to support medical necessity. Please submit additional records.",
            "The member's plan requires completion of a home sleep test (HSAT) prior to in-lab polysomnography.",
            "Prior conservative treatment measures have not been documented. Please provide evidence of attempted interventions.",
        ])
        text = (
            f"The request for the above-referenced service has been denied for the following reason:\n\n"
            f"{denial_reason}\n\n"
            f"You may appeal this decision within 60 days by submitting additional documentation to the address above."
        )

    y = draw_text_wrapped(draw, text, MARGIN_L, y, F_NORM, fill=30)

    return img


def gen_sleep_study_report(patient, page_num, total_pages, fax_date=None):
    """Generate a sleep study results summary page."""
    img, draw = new_page()
    fax_date = fax_date or rand_date_recent(60)
    facility = random.choice([
        "South Texas Sleep Diagnostics", "Alamo Sleep Center",
        "Baptist Sleep Lab", "Methodist Sleep Center",
        STRC_NAME,
    ])
    add_fax_header(draw, facility[:25], page_num, total_pages, fax_date)
    y = MARGIN_T

    draw.text((MARGIN_L, y), facility, fill=10, font=F_LG)
    y += 35
    draw.text((MARGIN_L, y), "POLYSOMNOGRAPHY REPORT", fill=10, font=F_XL)
    y += 45
    draw_line(draw, y)
    y += 15

    study_date = rand_date_recent(90)
    study_type = random.choice(["Diagnostic PSG", "Split-Night PSG", "CPAP Titration", "BiPAP Titration"])
    interp_doc = random.choice(STRC_PROVIDERS + REFERRING_DOCTORS[:5])

    y = draw_field(draw, "Patient:", patient["name"], MARGIN_L, y, gap=180)
    y = draw_field(draw, "DOB:", patient["dob"], MARGIN_L, y, gap=180)
    y = draw_field(draw, "Study Date:", study_date, MARGIN_L, y, gap=180)
    y = draw_field(draw, "Study Type:", study_type, MARGIN_L, y, gap=180)
    y = draw_field(draw, "Interpreting:", interp_doc, MARGIN_L, y, gap=180)
    y += 15

    draw.text((MARGIN_L, y), "SLEEP ARCHITECTURE", fill=10, font=F_MEDB)
    draw_line(draw, y + 22)
    y += 30

    tst = random.randint(240, 420)
    sleep_eff = round(random.uniform(60, 95), 1)
    sleep_lat = random.randint(3, 45)
    rem_lat = random.randint(60, 180)
    n1 = round(random.uniform(3, 15), 1)
    n2 = round(random.uniform(40, 60), 1)
    n3 = round(random.uniform(5, 25), 1)
    rem = round(100 - n1 - n2 - n3, 1)

    y = draw_field(draw, "Total Sleep Time:", f"{tst} min ({tst//60}h {tst%60}m)", MARGIN_L, y, gap=220)
    y = draw_field(draw, "Sleep Efficiency:", f"{sleep_eff}%", MARGIN_L, y, gap=220)
    y = draw_field(draw, "Sleep Latency:", f"{sleep_lat} min", MARGIN_L, y, gap=220)
    y = draw_field(draw, "REM Latency:", f"{rem_lat} min", MARGIN_L, y, gap=220)
    y = draw_field(draw, "Stage N1:", f"{n1}%", MARGIN_L, y, gap=220)
    y = draw_field(draw, "Stage N2:", f"{n2}%", MARGIN_L, y, gap=220)
    y = draw_field(draw, "Stage N3:", f"{n3}%", MARGIN_L, y, gap=220)
    y = draw_field(draw, "Stage REM:", f"{rem}%", MARGIN_L, y, gap=220)
    y += 15

    draw.text((MARGIN_L, y), "RESPIRATORY EVENTS", fill=10, font=F_MEDB)
    draw_line(draw, y + 22)
    y += 30

    severity = random.choice(["none", "mild", "moderate", "severe"])
    if severity == "none":
        ahi = round(random.uniform(0, 4.9), 1)
    elif severity == "mild":
        ahi = round(random.uniform(5, 14.9), 1)
    elif severity == "moderate":
        ahi = round(random.uniform(15, 29.9), 1)
    else:
        ahi = round(random.uniform(30, 90), 1)

    obstructive = random.randint(int(ahi * 2), int(ahi * 5))
    central = random.randint(0, max(1, int(ahi * 0.5)))
    mixed = random.randint(0, max(1, int(ahi * 0.3)))
    hypopneas = random.randint(int(ahi * 1), int(ahi * 4))
    low_o2 = random.randint(70 if severity == "severe" else 80, 94)

    y = draw_field(draw, "AHI (overall):", f"{ahi} events/hr", MARGIN_L, y, gap=220)
    y = draw_field(draw, "Obstructive Apneas:", str(obstructive), MARGIN_L, y, gap=220)
    y = draw_field(draw, "Central Apneas:", str(central), MARGIN_L, y, gap=220)
    y = draw_field(draw, "Mixed Apneas:", str(mixed), MARGIN_L, y, gap=220)
    y = draw_field(draw, "Hypopneas:", str(hypopneas), MARGIN_L, y, gap=220)
    y = draw_field(draw, "Lowest SpO2:", f"{low_o2}%", MARGIN_L, y, gap=220)
    y += 15

    if "Titration" in study_type:
        draw.text((MARGIN_L, y), "TITRATION RESULTS", fill=10, font=F_MEDB)
        draw_line(draw, y + 22)
        y += 30
        mode = "CPAP" if "CPAP" in study_type else "BiPAP"
        if mode == "CPAP":
            pressure = random.randint(6, 16)
            y = draw_field(draw, "Optimal Pressure:", f"{pressure} cmH2O", MARGIN_L, y, gap=220)
        else:
            ipap = random.randint(12, 20)
            epap = ipap - random.randint(2, 6)
            y = draw_field(draw, "IPAP:", f"{ipap} cmH2O", MARGIN_L, y, gap=220)
            y = draw_field(draw, "EPAP:", f"{epap} cmH2O", MARGIN_L, y, gap=220)
        res_ahi = round(random.uniform(0, 4.9), 1)
        y = draw_field(draw, "Residual AHI:", f"{res_ahi} events/hr", MARGIN_L, y, gap=220)
        y += 15

    # Impression
    draw.text((MARGIN_L, y), "IMPRESSION", fill=10, font=F_MEDB)
    draw_line(draw, y + 22)
    y += 30

    if ahi >= 5:
        impression = (
            f"{'Severe' if severity == 'severe' else 'Moderate' if severity == 'moderate' else 'Mild'} "
            f"Obstructive Sleep Apnea with AHI of {ahi} events/hour. "
            f"Lowest oxygen desaturation to {low_o2}%."
        )
        if "Titration" in study_type:
            impression += f" {'CPAP' if 'CPAP' in study_type else 'BiPAP'} titration successful with residual AHI of {res_ahi}."
        else:
            impression += f" Recommend {'CPAP' if ahi < 30 else 'BiPAP'} titration study."
    else:
        impression = (
            f"No significant obstructive sleep apnea identified. AHI {ahi} events/hour (normal < 5). "
            f"Consider alternative diagnoses for presenting symptoms."
        )
    y = draw_text_wrapped(draw, impression, MARGIN_L, y, F_NORM, fill=30)

    y += 40
    draw.text((MARGIN_L, y), f"Interpreted by: {interp_doc}", fill=30, font=F_MED)

    return img


def gen_cpap_prescription(patient, page_num=1, total_pages=1, fax_date=None):
    """Generate a CPAP/BiPAP prescription page."""
    img, draw = new_page()
    fax_date = fax_date or rand_date_recent(30)
    add_fax_header(draw, STRC_NAME[:25], page_num, total_pages, fax_date)
    y = MARGIN_T

    draw.text((MARGIN_L, y), STRC_NAME, fill=10, font=F_LG)
    y += 28
    draw.text((MARGIN_L, y), f"{STRC_ADDR}, {STRC_CITY}", fill=40, font=F_NORM)
    y += 22
    draw.text((MARGIN_L, y), f"Phone: {STRC_PHONE}   Fax: {STRC_FAX}   NPI: {STRC_NPI}", fill=40, font=F_NORM)
    y += 40

    draw.text((PAGE_W // 2 - 120, y), "PRESCRIPTION / ORDER", fill=10, font=F_XL)
    y += 50
    draw_line(draw, y)
    y += 20

    y = draw_field(draw, "Patient:", patient["name"], MARGIN_L, y, gap=160)
    y = draw_field(draw, "DOB:", patient["dob"], MARGIN_L, y, gap=160)
    y = draw_field(draw, "Phone:", patient["phone"], MARGIN_L, y, gap=160)
    y = draw_field(draw, "Address:", f"{patient['addr1']}, {patient['addr2']}", MARGIN_L, y, gap=160)
    y += 15
    draw_line(draw, y)
    y += 20

    dx = random.choice(SLEEP_DX_CODES[:3])
    device = random.choice(["CPAP", "APAP (Auto-CPAP)", "BiPAP", "BiPAP ST"])
    ahi = round(random.uniform(5, 80), 1)

    y = draw_field(draw, "Diagnosis:", f"{dx[0]} - {dx[1]}", MARGIN_L, y, gap=160)
    y = draw_field(draw, "AHI:", f"{ahi} events/hr", MARGIN_L, y, gap=160)
    y += 15

    draw.text((MARGIN_L, y), "ORDER:", fill=10, font=F_LG)
    y += 30

    if "BiPAP" in device:
        ipap = random.randint(12, 20)
        epap = ipap - random.randint(2, 6)
        y = draw_field(draw, "Device:", device, MARGIN_L, y, gap=200)
        y = draw_field(draw, "IPAP:", f"{ipap} cmH2O", MARGIN_L, y, gap=200)
        y = draw_field(draw, "EPAP:", f"{epap} cmH2O", MARGIN_L, y, gap=200)
    elif "APAP" in device:
        min_p = random.randint(4, 8)
        max_p = random.randint(12, 20)
        y = draw_field(draw, "Device:", device, MARGIN_L, y, gap=200)
        y = draw_field(draw, "Min Pressure:", f"{min_p} cmH2O", MARGIN_L, y, gap=200)
        y = draw_field(draw, "Max Pressure:", f"{max_p} cmH2O", MARGIN_L, y, gap=200)
    else:
        pressure = random.randint(6, 16)
        y = draw_field(draw, "Device:", device, MARGIN_L, y, gap=200)
        y = draw_field(draw, "Pressure:", f"{pressure} cmH2O", MARGIN_L, y, gap=200)

    mask = random.choice(["Full Face Mask", "Nasal Mask", "Nasal Pillows", "Provider's Discretion"])
    y = draw_field(draw, "Interface:", mask, MARGIN_L, y, gap=200)
    y = draw_field(draw, "Humidifier:", random.choice(["Yes - Heated","Yes","Heated humidification"]), MARGIN_L, y, gap=200)
    y += 10
    y = draw_field(draw, "Duration:", "99 months / Lifetime (chronic condition)", MARGIN_L, y, gap=200)

    # Supplies
    y += 20
    draw.text((MARGIN_L, y), "SUPPLIES (replacement schedule):", fill=10, font=F_MEDB)
    y += 25
    supplies = [
        "Mask cushion/pillows - every 1-3 months",
        "Full mask frame - every 3 months",
        "Headgear - every 6 months",
        "Tubing - every 3 months",
        "Filters (disposable) - 2x per month",
        "Filters (reusable) - every 6 months",
        "Humidifier chamber - every 6 months",
        "Chinstrap (if needed) - every 6 months",
    ]
    for s in supplies:
        draw.text((MARGIN_L + 20, y), f"• {s}", fill=30, font=F_NORM)
        y += 20

    # Signature
    y += 30
    prescriber = random.choice(STRC_PROVIDERS)
    draw_line(draw, y + 20, x1=MARGIN_L, x2=MARGIN_L + 350)
    draw.text((MARGIN_L, y + 25), f"{prescriber}    NPI: {rand_npi()}", fill=30, font=F_NORM)
    draw.text((MARGIN_L, y + 48), f"Date: {fax_date}", fill=30, font=F_NORM)

    return img


def gen_lab_results(patient, practice, page_num=1, total_pages=1, fax_date=None):
    """Generate a lab results page (blood work relevant to sleep medicine)."""
    img, draw = new_page()
    fax_date = fax_date or rand_date_recent(30)
    lab_name = random.choice(["Quest Diagnostics", "LabCorp", "South Texas Blood & Tissue", practice["name"]])
    add_fax_header(draw, lab_name[:25], page_num, total_pages, fax_date)
    y = MARGIN_T

    draw.text((MARGIN_L, y), lab_name, fill=10, font=F_LG)
    y += 35
    draw.text((MARGIN_L, y), "LABORATORY RESULTS", fill=10, font=F_XL)
    y += 45
    draw_line(draw, y)
    y += 15

    y = draw_field(draw, "Patient:", patient["name"], MARGIN_L, y, gap=160)
    y = draw_field(draw, "DOB:", patient["dob"], MARGIN_L, y, gap=160)
    y = draw_field(draw, "Ordering MD:", random.choice(REFERRING_DOCTORS), MARGIN_L, y, gap=160)
    y = draw_field(draw, "Collected:", rand_date_recent(7), MARGIN_L, y, gap=160)
    y += 10
    draw_line(draw, y)
    y += 10

    # Table header
    draw_box(draw, MARGIN_L, y, MARGIN_R, y + 25, fill_color=235)
    draw.text((MARGIN_L + 5, y + 3), "Test", fill=10, font=F_MEDB)
    draw.text((MARGIN_L + 350, y + 3), "Result", fill=10, font=F_MEDB)
    draw.text((MARGIN_L + 500, y + 3), "Units", fill=10, font=F_MEDB)
    draw.text((MARGIN_L + 650, y + 3), "Reference", fill=10, font=F_MEDB)
    y += 30

    panel = random.choice(["thyroid", "metabolic", "cbc"])
    if panel == "thyroid":
        labs = [
            ("TSH", f"{round(random.uniform(0.3, 8.5), 2)}", "mIU/L", "0.40 - 4.50"),
            ("Free T4", f"{round(random.uniform(0.6, 2.2), 2)}", "ng/dL", "0.80 - 1.80"),
            ("Free T3", f"{round(random.uniform(1.5, 5.0), 2)}", "pg/mL", "2.30 - 4.20"),
        ]
    elif panel == "metabolic":
        labs = [
            ("Glucose", str(random.randint(70, 250)), "mg/dL", "70 - 105"),
            ("BUN", str(random.randint(7, 35)), "mg/dL", "7 - 25"),
            ("Creatinine", f"{round(random.uniform(0.5, 2.0), 2)}", "mg/dL", "0.60 - 1.30"),
            ("Sodium", str(random.randint(133, 148)), "mEq/L", "135 - 145"),
            ("Potassium", f"{round(random.uniform(3.0, 5.5), 1)}", "mEq/L", "3.5 - 5.0"),
            ("CO2", str(random.randint(20, 34)), "mEq/L", "22 - 30"),
            ("HbA1c", f"{round(random.uniform(4.5, 11.0), 1)}", "%", "4.0 - 5.6"),
        ]
    else:
        labs = [
            ("WBC", f"{round(random.uniform(3.5, 14.0), 1)}", "K/uL", "4.0 - 11.0"),
            ("RBC", f"{round(random.uniform(3.5, 6.0), 2)}", "M/uL", "4.20 - 5.80"),
            ("Hemoglobin", f"{round(random.uniform(10, 18), 1)}", "g/dL", "12.0 - 17.0"),
            ("Hematocrit", f"{round(random.uniform(32, 52), 1)}", "%", "36.0 - 50.0"),
            ("Platelets", str(random.randint(120, 450)), "K/uL", "150 - 400"),
        ]

    for test_name, result, units, ref in labs:
        draw.text((MARGIN_L + 5, y), test_name, fill=30, font=F_NORM)
        draw.text((MARGIN_L + 350, y), result, fill=30, font=F_NORM)
        draw.text((MARGIN_L + 500, y), units, fill=50, font=F_SMALL)
        draw.text((MARGIN_L + 650, y), ref, fill=50, font=F_SMALL)
        y += 25
        draw_line(draw, y, width=1)
        y += 5

    return img


def gen_insurance_verification(patient, insurance, page_num=1, total_pages=1, fax_date=None):
    """Generate an insurance eligibility verification response."""
    img, draw = new_page()
    fax_date = fax_date or rand_date_recent(14)
    add_fax_header(draw, insurance["company"][:25], page_num, total_pages, fax_date)
    y = MARGIN_T

    draw.text((MARGIN_L, y), insurance["company"], fill=10, font=F_LG)
    y += 35
    draw.text((MARGIN_L, y), "ELIGIBILITY VERIFICATION RESPONSE", fill=10, font=F_XL)
    y += 50
    draw_line(draw, y)
    y += 20

    y = draw_field(draw, "Date:", fax_date, MARGIN_L, y, gap=180)
    y = draw_field(draw, "To:", f"{STRC_NAME} / Fax: {STRC_FAX}", MARGIN_L, y, gap=180)
    y += 15
    y = draw_field(draw, "Member:", patient["name"], MARGIN_L, y, gap=180)
    y = draw_field(draw, "DOB:", patient["dob"], MARGIN_L, y, gap=180)
    y = draw_field(draw, "Member ID:", insurance["member_id"], MARGIN_L, y, gap=180)
    y = draw_field(draw, "Group #:", insurance["group"], MARGIN_L, y, gap=180)
    y = draw_field(draw, "Plan Type:", insurance["type"], MARGIN_L, y, gap=180)
    y += 15

    eligible = random.random() > 0.15
    draw.text((MARGIN_L, y), f"STATUS: {'ACTIVE / ELIGIBLE' if eligible else 'INACTIVE / NOT ELIGIBLE'}", fill=10, font=F_LG)
    y += 35

    if eligible:
        eff_date = f"{random.randint(1,12):02d}/01/{random.randint(2020,2025)}"
        y = draw_field(draw, "Effective Date:", eff_date, MARGIN_L, y, gap=200)
        y += 15
        draw.text((MARGIN_L, y), "BENEFITS SUMMARY:", fill=10, font=F_MEDB)
        y += 25

        copay = random.choice(["$20","$30","$40","$50","$70","$75"])
        specialist_copay = random.choice(["$40","$50","$60","$70","$75"])
        deductible = random.choice(["$500","$1000","$1500","$2500","$3000"])
        oop = random.choice(["$3000","$5000","$6500","$7500","$8700"])

        y = draw_field(draw, "PCP Copay:", copay, MARGIN_L + 20, y, gap=240)
        y = draw_field(draw, "Specialist Copay:", specialist_copay, MARGIN_L + 20, y, gap=240)
        y = draw_field(draw, "Deductible:", deductible, MARGIN_L + 20, y, gap=240)
        y = draw_field(draw, "Out-of-Pocket Max:", oop, MARGIN_L + 20, y, gap=240)

        if insurance["type"] == "HMO":
            y += 15
            draw.text((MARGIN_L, y), "** REFERRAL REQUIRED for specialist visits **", fill=10, font=F_MEDB)
            y += 25
            draw.text((MARGIN_L, y), "Prior authorization required for sleep studies (PSG, HSAT).", fill=30, font=F_NORM)

    return img


def gen_athena_referral_order(patient, insurance, practice, doctor, fax_date=None):
    """Generate an athenahealth-style referral order page."""
    img, draw = new_page()
    fax_date = fax_date or rand_date_recent(14)

    # athena header
    draw.text((MARGIN_L, 8), "athena", fill=60, font=F_MED)
    athena_id = f"{uuid.uuid4()}"
    draw.text((PAGE_W // 3, 8), f"{fax_date} {random.randint(7,11)}:{random.randint(10,59):02d} am EDT", fill=60, font=F_SMALL)
    draw.text((PAGE_W // 2 + 50, 8), athena_id[:30], fill=60, font=F_SMALL)
    draw.text((MARGIN_R - 120, 8), f"Page: 01 / {random.randint(3,12)}", fill=60, font=F_SMALL)

    y = MARGIN_T

    draw.text((MARGIN_L, y), practice["name"], fill=10, font=F_LG)
    y += 28
    draw.text((MARGIN_L, y), f"{practice['addr']}, {practice['city']}", fill=40, font=F_NORM)
    y += 40

    # Privacy notice
    privacy = (
        "This fax may contain sensitive and confidential personal health information that is being "
        "sent for the sole use of the intended recipient. Unintended recipients are directed to securely "
        "destroy any materials received."
    )
    y = draw_text_wrapped(draw, privacy, MARGIN_L, y, F_SMALL, fill=50)
    y += 20

    draw.text((PAGE_W // 2 - 100, y), "Referral Order", fill=10, font=F_XL)
    y += 40
    draw.text((PAGE_W // 2, y), f"Date: {fax_date}", fill=30, font=F_NORM)
    y += 30

    # To/From boxes
    draw_box(draw, MARGIN_L, y, PAGE_W // 2 - 20, y + 130)
    draw.text((MARGIN_L + 5, y + 3), "To Provider", fill=10, font=F_MEDB)
    strc_prov = random.choice(STRC_PROVIDERS)
    draw.text((MARGIN_L + 8, y + 25), strc_prov, fill=30, font=F_NORM)
    draw.text((MARGIN_L + 8, y + 48), STRC_ADDR, fill=30, font=F_NORM)
    draw.text((MARGIN_L + 8, y + 68), STRC_CITY, fill=30, font=F_NORM)
    draw.text((MARGIN_L + 8, y + 88), f"Phone: {STRC_PHONE}", fill=30, font=F_NORM)
    draw.text((MARGIN_L + 8, y + 108), f"Fax: {STRC_FAX}", fill=30, font=F_NORM)

    fx = PAGE_W // 2 + 10
    draw_box(draw, fx, y, MARGIN_R, y + 130)
    draw.text((fx + 5, y + 3), "From Provider", fill=10, font=F_MEDB)
    draw.text((fx + 8, y + 25), doctor, fill=30, font=F_NORM)
    draw.text((fx + 8, y + 48), practice["name"][:35], fill=30, font=F_NORM)
    draw.text((fx + 8, y + 68), f"{practice['addr']}, {practice['city']}", fill=30, font=F_SMALL)
    draw.text((fx + 8, y + 88), f"Phone: {practice['phone']}", fill=30, font=F_NORM)
    draw.text((fx + 8, y + 108), f"Fax: {practice['fax']}", fill=30, font=F_NORM)
    y += 145

    # Referral order info
    draw.text((PAGE_W // 2 - 120, y), "Referral Order Information", fill=10, font=F_LG)
    y += 35

    dx = rand_dx(1)[0]
    draw_box(draw, MARGIN_L, y, PAGE_W // 2 - 20, y + 35)
    draw.text((MARGIN_L + 5, y + 3), "Diagnosis", fill=10, font=F_MEDB)
    draw.text((MARGIN_L + 5, y + 20), f"ICD-10: {dx[0]}: {dx[1]}", fill=30, font=F_SMALL)

    draw_box(draw, PAGE_W // 2 + 10, y, MARGIN_R, y + 105)
    draw.text((fx + 5, y + 3), "Order Name", fill=10, font=F_MEDB)
    draw.text((fx + 5, y + 20), f"SLEEP MEDICINE REFERRAL", fill=30, font=F_NORM)
    draw.text((fx + 5, y + 40), f"Schedule Within: provider's discretion", fill=30, font=F_SMALL)

    auth_line = f"Authorization: {'NOT REQUIRED' if insurance['type'] == 'PPO' else 'REQUIRED'} ({insurance['type']})"
    visits = random.choice([1, 2, 5, 12, 24])
    start = rand_date_recent(7)
    end = rand_date_future(365)
    draw.text((fx + 5, y + 60), auth_line, fill=30, font=F_SMALL)
    draw.text((fx + 5, y + 78), f"| {start} to {end} | Visits approved: {visits}", fill=30, font=F_SMALL)
    y += 120

    # Patient info
    draw.text((PAGE_W // 2 - 80, y), "Patient Information", fill=10, font=F_LG)
    y += 30

    fields = [
        ("Patient Name", patient["name"]),
        ("Sex - DOB - Age", f"{patient['sex']}  {patient['dob']}  {patient['age']}yo"),
        ("Address", f"{patient['addr1']}, {patient['addr2']}"),
        ("Phone", f"H: {patient['phone']}"),
        ("Primary Insurance", f"{insurance['company']} ({insurance['type']})"),
    ]
    for label, val in fields:
        draw_box(draw, MARGIN_L, y, MARGIN_L + 180, y + 25, fill_color=235)
        draw.text((MARGIN_L + 5, y + 3), label, fill=10, font=F_MEDB)
        draw.text((MARGIN_L + 185, y + 3), val, fill=30, font=F_NORM)
        y += 28

    y += 20
    draw.text((MARGIN_L, y), f"Electronically Signed by: {doctor}", fill=30, font=F_MED)

    return img


def gen_dme_order_form(patient, page_num=1, total_pages=1, fax_date=None):
    """Generate a DME (CPAP supplies) order form."""
    img, draw = new_page()
    fax_date = fax_date or rand_date_recent(30)
    dme_company = random.choice([
        "Apria Healthcare", "AdaptHealth", "Lincare", "Rotech Healthcare",
        "South Texas DME", "Aeroflow Healthcare",
    ])
    add_fax_header(draw, dme_company[:25], page_num, total_pages, fax_date)
    y = MARGIN_T

    draw.text((MARGIN_L, y), dme_company, fill=10, font=F_LG)
    y += 35
    draw.text((MARGIN_L, y), "DME ORDER / PRESCRIPTION FORM", fill=10, font=F_XL)
    y += 50
    draw_line(draw, y)
    y += 20

    y = draw_field(draw, "Patient:", patient["name"], MARGIN_L, y, gap=160)
    y = draw_field(draw, "DOB:", patient["dob"], MARGIN_L, y, gap=160)
    y = draw_field(draw, "Phone:", patient["phone"], MARGIN_L, y, gap=160)
    y = draw_field(draw, "Address:", f"{patient['addr1']}, {patient['addr2']}", MARGIN_L, y, gap=160)
    y += 15

    draw.text((MARGIN_L, y), "ITEMS ORDERED:", fill=10, font=F_MEDB)
    y += 25

    items = random.sample([
        ("E0601", "CPAP device", "1", "Purchase"),
        ("A7027", "CPAP full face mask", "1", "Rental"),
        ("A7030", "CPAP mask cushion", "2", "Purchase"),
        ("A7037", "CPAP tubing", "1", "Purchase"),
        ("A7038", "CPAP disposable filter (pack)", "2", "Purchase"),
        ("A7046", "Humidifier chamber", "1", "Purchase"),
        ("A7035", "CPAP headgear", "1", "Purchase"),
        ("A7034", "Nasal mask interface", "1", "Rental"),
        ("E0562", "Heated humidifier", "1", "Purchase"),
    ], random.randint(3, 6))

    draw_box(draw, MARGIN_L, y, MARGIN_R, y + 25, fill_color=235)
    draw.text((MARGIN_L + 5, y + 3), "HCPCS", fill=10, font=F_MEDB)
    draw.text((MARGIN_L + 100, y + 3), "Description", fill=10, font=F_MEDB)
    draw.text((MARGIN_L + 500, y + 3), "Qty", fill=10, font=F_MEDB)
    draw.text((MARGIN_L + 580, y + 3), "Type", fill=10, font=F_MEDB)
    y += 28

    for hcpcs, desc, qty, ptype in items:
        draw.text((MARGIN_L + 5, y), hcpcs, fill=30, font=F_NORM)
        draw.text((MARGIN_L + 100, y), desc, fill=30, font=F_NORM)
        draw.text((MARGIN_L + 500, y), qty, fill=30, font=F_NORM)
        draw.text((MARGIN_L + 580, y), ptype, fill=30, font=F_NORM)
        y += 22

    y += 20
    draw.text((MARGIN_L, y), f"Ordering Provider: {random.choice(STRC_PROVIDERS)}", fill=30, font=F_MED)
    y += 25
    draw.text((MARGIN_L, y), f"NPI: {STRC_NPI}", fill=30, font=F_NORM)
    y += 25
    draw.text((MARGIN_L, y), f"Date: {fax_date}", fill=30, font=F_NORM)

    return img


def gen_cardiology_clearance(patient, page_num=1, total_pages=1, fax_date=None):
    """Generate a cardiology pre-procedure clearance letter."""
    img, draw = new_page()
    fax_date = fax_date or rand_date_recent(30)
    cardio_practice = random.choice([
        "South Texas Cardiology Associates", "Alamo Heart Center",
        "SA Cardiovascular Consultants", "Heart Clinic of San Antonio",
    ])
    cardio_doc = random.choice([
        "Michael Sioco MD FACC", "David Chen MD FACC",
        "Robert Martinez MD", "Lisa Patel MD FACC",
    ])
    add_fax_header(draw, cardio_practice[:25], page_num, total_pages, fax_date)
    y = MARGIN_T

    draw.text((MARGIN_L, y), cardio_practice, fill=10, font=F_LG)
    y += 30
    draw.text((MARGIN_L, y), f"9465 Huebner Rd, San Antonio, TX 78240", fill=40, font=F_NORM)
    y += 22
    draw.text((MARGIN_L, y), f"Phone: (210) 614-8800   Fax: (210) 614-8805", fill=40, font=F_NORM)
    y += 40

    draw.text((MARGIN_L, y), f"Date: {fax_date}", fill=30, font=F_NORM)
    y += 30
    draw.text((MARGIN_L, y), f"To: {STRC_NAME}", fill=30, font=F_NORM)
    y += 22
    draw.text((MARGIN_L, y), f"Fax: {STRC_FAX}", fill=30, font=F_NORM)
    y += 30

    draw.text((MARGIN_L, y), f"RE: {patient['name']}  DOB: {patient['dob']}", fill=10, font=F_MEDB)
    y += 30
    draw.text((MARGIN_L, y), "CARDIOVASCULAR CLEARANCE FOR SLEEP STUDY", fill=10, font=F_LG)
    y += 40

    draw.text((MARGIN_L, y), f"Dear {random.choice(STRC_PROVIDERS)},", fill=30, font=F_NORM)
    y += 30

    conditions = random.sample(COMORBIDITIES[:8], random.randint(1, 3))
    cond_text = ", ".join(conditions)

    body = (
        f"I have evaluated the above-referenced patient in my office on {rand_date_recent(14)}. "
        f"The patient has a history of {cond_text}. "
        f"Current cardiac status is stable. "
        f"{'Recent echocardiogram shows EF of ' + str(random.randint(40,65)) + '%. ' if random.random() > 0.5 else ''}"
        f"{'EKG shows ' + random.choice(['normal sinus rhythm','sinus bradycardia','atrial fibrillation with controlled rate']) + '. ' if random.random() > 0.3 else ''}"
        f"\n\n"
        f"From a cardiovascular standpoint, the patient is cleared for sleep study "
        f"{'and CPAP/BiPAP therapy' if random.random() > 0.3 else ''}. "
        f"{'Please monitor blood pressure during the study as patient is on antihypertensive medications. ' if random.random() > 0.5 else ''}"
        f"\n\n"
        f"Please do not hesitate to contact our office if you have any questions."
    )
    y = draw_text_wrapped(draw, body, MARGIN_L, y, F_NORM, fill=30)

    y += 40
    draw.text((MARGIN_L, y), "Sincerely,", fill=30, font=F_NORM)
    y += 30
    draw.text((MARGIN_L, y), cardio_doc, fill=10, font=F_MED)
    y += 25
    draw.text((MARGIN_L, y), cardio_practice, fill=30, font=F_NORM)

    return img


def gen_workers_comp_referral(patient, page_num=1, total_pages=1, fax_date=None):
    """Generate a workers compensation sleep referral."""
    img, draw = new_page()
    fax_date = fax_date or rand_date_recent(30)
    add_fax_header(draw, "TX Workers Comp", page_num, total_pages, fax_date)
    y = MARGIN_T

    draw.text((MARGIN_L, y), "TEXAS WORKERS' COMPENSATION", fill=10, font=F_LG)
    y += 30
    draw.text((MARGIN_L, y), "REFERRAL FOR SLEEP MEDICINE EVALUATION", fill=10, font=F_XL)
    y += 50
    draw_line(draw, y)
    y += 20

    claim_num = f"WC-{random.randint(2024,2026)}-{random.randint(100000,999999)}"
    employer = random.choice(["City of San Antonio","Bexar County","HEB","SAISD","CPS Energy","VIA Metropolitan Transit","Valero Energy"])
    doi = rand_date_recent(365)

    y = draw_field(draw, "Claim #:", claim_num, MARGIN_L, y, gap=200)
    y = draw_field(draw, "Employee:", patient["name"], MARGIN_L, y, gap=200)
    y = draw_field(draw, "DOB:", patient["dob"], MARGIN_L, y, gap=200)
    y = draw_field(draw, "SSN:", patient["ssn"], MARGIN_L, y, gap=200)
    y = draw_field(draw, "Employer:", employer, MARGIN_L, y, gap=200)
    y = draw_field(draw, "Date of Injury:", doi, MARGIN_L, y, gap=200)
    y += 15

    draw.text((MARGIN_L, y), "REASON FOR REFERRAL:", fill=10, font=F_MEDB)
    y += 25
    reason = random.choice([
        "Employee involved in motor vehicle accident while on duty. Suspicion of untreated OSA as contributing factor. "
        "Requesting sleep study evaluation per DOT requirements.",
        "CDL driver requires sleep apnea screening per FMCSA guidelines. BMI > 35, neck circumference > 17 inches.",
        "Employee reports excessive daytime sleepiness affecting job performance. Safety-sensitive position requires clearance.",
        "Post-accident evaluation: employee fell asleep while operating heavy equipment. Sleep disorder screening requested.",
    ])
    y = draw_text_wrapped(draw, reason, MARGIN_L, y, F_NORM, fill=30)
    y += 20

    draw.text((MARGIN_L, y), "AUTHORIZATION:", fill=10, font=F_MEDB)
    y += 25
    draw.text((MARGIN_L, y), "Authorized services: Sleep medicine consultation, diagnostic sleep study (PSG/HSAT)", fill=30, font=F_NORM)
    y += 22
    draw.text((MARGIN_L, y), f"Insurance Carrier: {random.choice(['Texas Mutual','Zenith Insurance','Hartford','Travelers'])}", fill=30, font=F_NORM)
    y += 22
    draw.text((MARGIN_L, y), f"Adjuster: {rand_full_name()}   Phone: {rand_phone()}", fill=30, font=F_NORM)

    return img


# ---------------------------------------------------------------------------
# Document assemblers — combine pages into complete documents
# ---------------------------------------------------------------------------

def make_patient():
    """Create a random patient data dict."""
    first, last = rand_name()
    dob, age = rand_dob()
    addr1, addr2 = rand_addr()
    ins = rand_insurance()
    return {
        "first": first, "last": last, "name": f"{first} {last}",
        "dob": dob, "age": age, "sex": random.choice(["M", "F"]),
        "addr1": addr1, "addr2": addr2,
        "phone": rand_phone(), "ssn": rand_ssn_masked(),
        "pid": str(random.randint(100000, 999999)),
        "ref_doc": random.choice(REFERRING_DOCTORS),
        "insurance": ins,
    }


def assemble_referral_packet():
    """Full referral packet: cover + patient info + referral form + progress note (3-5 pages)."""
    patient = make_patient()
    practice = rand_practice()
    doctor = random.choice(REFERRING_DOCTORS)
    ins = patient["insurance"]
    dx = rand_dx(2)
    fax_date = rand_date_recent(30)
    pages = []

    total = random.randint(3, 5)
    # Cover
    pages.append(gen_fax_cover(practice, doctor, fax_date, f"Sleep referral for {patient['name']}", total))
    # Patient info
    pages.append(gen_patient_info_page(patient, ins, practice, 2, total, fax_date))
    # Referral form
    pages.append(gen_referral_form(patient, ins, practice, doctor, dx, 3, total, fax_date))
    # Optional progress note
    if total >= 4:
        pages.append(gen_progress_note(patient, practice, doctor, 4, total, fax_date))
    if total >= 5:
        pages.append(gen_progress_note(patient, practice, doctor, 5, total, fax_date))
    return pages


def assemble_athena_referral():
    """athenahealth-style referral order with encounter pages (3-6 pages)."""
    patient = make_patient()
    practice = rand_practice()
    doctor = random.choice(REFERRING_DOCTORS)
    ins = patient["insurance"]
    fax_date = rand_date_recent(14)
    pages = []

    pages.append(gen_athena_referral_order(patient, ins, practice, doctor, fax_date))
    # Add 2-5 more progress note pages
    extra = random.randint(2, 5)
    for i in range(extra):
        pages.append(gen_progress_note(patient, practice, doctor, i + 2, 1 + extra, fax_date))
    return pages


def assemble_tricare_auth():
    """TRICARE authorization: cover + auth letter + service details (2-3 pages)."""
    patient = make_patient()
    practice = random.choice([
        {"name": "DOMA Technologies", "phone": "", "fax": "", "addr": "", "city": ""},
    ])
    fax_date = rand_date_recent(14)
    total = random.randint(2, 3)
    pages = []

    pages.append(gen_fax_cover(practice, "DOMA Technologies", fax_date, "", total))
    pages.append(gen_tricare_auth(patient, 2, total, fax_date))
    if total == 3:
        # Service provider detail page
        pages.append(gen_tricare_auth(patient, 3, total, fax_date))
    return pages


def assemble_prior_auth(approved=True):
    """Prior authorization letter (1-2 pages)."""
    patient = make_patient()
    ins = patient["insurance"]
    fax_date = rand_date_recent(14)
    total = random.randint(1, 2)
    pages = [gen_prior_auth_letter(patient, ins, approved, 1, total, fax_date)]
    if total == 2:
        pages.append(gen_insurance_verification(patient, ins, 2, total, fax_date))
    return pages


def assemble_sleep_study_report():
    """Sleep study results (2-4 pages)."""
    patient = make_patient()
    fax_date = rand_date_recent(60)
    total = random.randint(2, 4)
    pages = []
    for i in range(total):
        pages.append(gen_sleep_study_report(patient, i + 1, total, fax_date))
    return pages


def assemble_cpap_rx():
    """CPAP/BiPAP prescription (1-2 pages)."""
    patient = make_patient()
    fax_date = rand_date_recent(30)
    total = random.randint(1, 2)
    pages = [gen_cpap_prescription(patient, 1, total, fax_date)]
    if total == 2:
        pages.append(gen_sleep_study_report(patient, 2, total, fax_date))
    return pages


def assemble_lab_results():
    """Lab results (1-2 pages)."""
    patient = make_patient()
    practice = rand_practice()
    fax_date = rand_date_recent(30)
    total = random.randint(1, 2)
    pages = [gen_lab_results(patient, practice, 1, total, fax_date)]
    if total == 2:
        pages.append(gen_lab_results(patient, practice, 2, total, fax_date))
    return pages


def assemble_insurance_verification():
    """Insurance eligibility response (1-2 pages)."""
    patient = make_patient()
    ins = patient["insurance"]
    fax_date = rand_date_recent(14)
    total = random.randint(1, 2)
    pages = [gen_insurance_verification(patient, ins, 1, total, fax_date)]
    if total == 2:
        pages.append(gen_prior_auth_letter(patient, ins, True, 2, total, fax_date))
    return pages


def assemble_dme_order():
    """DME order form (1-2 pages)."""
    patient = make_patient()
    fax_date = rand_date_recent(30)
    total = random.randint(1, 2)
    pages = [gen_dme_order_form(patient, 1, total, fax_date)]
    if total == 2:
        pages.append(gen_cpap_prescription(patient, 2, total, fax_date))
    return pages


def assemble_cardio_clearance():
    """Cardiology clearance letter (1-2 pages)."""
    patient = make_patient()
    fax_date = rand_date_recent(30)
    total = random.randint(1, 2)
    pages = [gen_cardiology_clearance(patient, 1, total, fax_date)]
    if total == 2:
        pages.append(gen_progress_note(patient, rand_practice(), random.choice(REFERRING_DOCTORS), 2, total, fax_date))
    return pages


def assemble_workers_comp():
    """Workers comp referral (2-3 pages)."""
    patient = make_patient()
    practice = rand_practice()
    doctor = random.choice(REFERRING_DOCTORS)
    fax_date = rand_date_recent(30)
    total = random.randint(2, 3)
    pages = [gen_workers_comp_referral(patient, 1, total, fax_date)]
    pages.append(gen_referral_form(patient, patient["insurance"], practice, doctor, rand_dx(2), 2, total, fax_date))
    if total == 3:
        pages.append(gen_progress_note(patient, practice, doctor, 3, total, fax_date))
    return pages


def assemble_standalone_referral():
    """Just a referral form, no cover sheet (1-2 pages)."""
    patient = make_patient()
    practice = rand_practice()
    doctor = random.choice(REFERRING_DOCTORS)
    ins = patient["insurance"]
    dx = rand_dx(2)
    fax_date = rand_date_recent(30)
    total = random.randint(1, 2)
    pages = [gen_referral_form(patient, ins, practice, doctor, dx, 1, total, fax_date)]
    if total == 2:
        pages.append(gen_patient_info_page(patient, ins, practice, 2, total, fax_date))
    return pages


def assemble_progress_notes():
    """Progress notes from PCP (2-4 pages)."""
    patient = make_patient()
    practice = rand_practice()
    doctor = random.choice(REFERRING_DOCTORS)
    fax_date = rand_date_recent(60)
    total = random.randint(2, 4)
    pages = []
    for i in range(total):
        pages.append(gen_progress_note(patient, practice, doctor, i + 1, total, fax_date))
    return pages


# ---------------------------------------------------------------------------
# Post-processing: apply scanned look
# ---------------------------------------------------------------------------

def apply_scan_effects(img):
    """Make an image look more like a scanned document."""
    # Slight rotation
    if random.random() > 0.6:
        angle = random.uniform(-1.5, 1.5)
        img = img.rotate(angle, fillcolor=random.randint(240, 250), expand=False)

    # Slight blur (simulates scanner imperfection)
    if random.random() > 0.5:
        img = img.filter(ImageFilter.GaussianBlur(radius=0.5))

    # Add noise
    try:
        img = add_scan_noise(img)
    except ImportError:
        pass

    return img


# ---------------------------------------------------------------------------
# Save functions
# ---------------------------------------------------------------------------

def save_as_pdf(pages, filepath):
    """Save list of PIL images as a multi-page image-based PDF."""
    if not pages:
        return
    processed = [apply_scan_effects(p) for p in pages]
    first = processed[0]
    rest = processed[1:] if len(processed) > 1 else []
    first.save(filepath, "PDF", resolution=DPI, save_all=True, append_images=rest)


def save_as_tiff(pages, filepath):
    """Save list of PIL images as a multi-page TIFF."""
    if not pages:
        return
    processed = [apply_scan_effects(p) for p in pages]
    first = processed[0]
    rest = processed[1:] if len(processed) > 1 else []
    first.save(filepath, "TIFF", compression="tiff_lzw", save_all=True, append_images=rest, dpi=(DPI, DPI))


def save_as_png(pages, filepath):
    """Save first page as PNG."""
    if not pages:
        return
    img = apply_scan_effects(pages[0])
    img.save(filepath, "PNG", dpi=(DPI, DPI))


def save_as_jpeg(pages, filepath):
    """Save first page as JPEG."""
    if not pages:
        return
    img = apply_scan_effects(pages[0])
    img.save(filepath, "JPEG", quality=85, dpi=(DPI, DPI))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Define document distribution: (assembler_func, count)
    doc_types = [
        (assemble_referral_packet, 22),
        (assemble_athena_referral, 10),
        (assemble_standalone_referral, 10),
        (assemble_tricare_auth, 6),
        (assemble_prior_auth, 8),          # 6 approved + 2 denied
        (assemble_sleep_study_report, 8),
        (assemble_cpap_rx, 8),
        (assemble_progress_notes, 8),
        (assemble_lab_results, 6),
        (assemble_insurance_verification, 6),
        (assemble_dme_order, 5),
        (assemble_cardio_clearance, 4),
        (assemble_workers_comp, 3),
    ]
    # Total: 22+10+10+6+8+8+8+8+6+6+5+4+3 = 104, we'll take first 100

    # Format distribution targets
    # ~60 PDF, ~25 TIFF, ~10 PNG, ~5 JPEG
    format_queue = (
        ["pdf"] * 60 + ["tiff"] * 25 + ["png"] * 10 + ["jpeg"] * 5
    )
    random.shuffle(format_queue)

    generated = 0
    file_index = 0

    for assembler, count in doc_types:
        for i in range(count):
            if generated >= 100:
                break

            # Handle prior auth approved vs denied
            if assembler == assemble_prior_auth:
                pages = assembler(approved=(i < 6))
            else:
                pages = assembler()

            # Pick format
            fmt = format_queue[file_index % len(format_queue)]
            file_index += 1

            filename = str(uuid.uuid4())
            ext_map = {"pdf": ".pdf", "tiff": ".tiff", "png": ".png", "jpeg": ".jpg"}
            filepath = os.path.join(OUTPUT_DIR, filename + ext_map[fmt])

            if fmt == "pdf":
                save_as_pdf(pages, filepath)
            elif fmt == "tiff":
                save_as_tiff(pages, filepath)
            elif fmt == "png":
                save_as_png(pages, filepath)
            elif fmt == "jpeg":
                save_as_jpeg(pages, filepath)

            page_count = len(pages)
            generated += 1
            print(f"[{generated:3d}/100] {ext_map[fmt]:5s} ({page_count}p) {filename}{ext_map[fmt]}")

        if generated >= 100:
            break

    print(f"\nDone. Generated {generated} files in {OUTPUT_DIR}")


if __name__ == "__main__":
    random.seed(42)  # Reproducible for testing
    main()

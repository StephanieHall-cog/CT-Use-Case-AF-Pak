#!/usr/bin/env python3
"""Generate the SYNTHETIC target-tracking demo dataset (synthetic/targets_demo.json) and the public-reference
site layer (synthetic/sites_reference.json).

Everything in targets_demo.json is fictional: people, kunyas, objective names, phone numbers, IMSI/IMEI, e-mail
addresses, social-media handles, vehicles, CMA accounts, selector correlations, location hits and attacks. Links to
REAL organizations (Haqqani Network, TTP, ISKP, Taliban) are allowed and are flagged dataset='synthetic' on the edge.
Identifiers use obviously non-allocated ranges (555 phone blocks, IMSI 41201-99…, IMEI TAC 00000000, example.com).

sites_reference.json lists real, publicly known diplomatic/military/international sites (USG and other governments)
with approximate coordinates (precision_km given, verified=0) so the map can show them as a layer.

Deterministic: `python3 scripts/synthetic_targets.py` always writes the same files.
"""
import json, os, random, hashlib, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
rng = random.Random(20261012)

# ---- gazetteer (GeoNames picks + hand-set approximations; lat, lon, precision_km) ----
G = {
 "Kabul": (34.5281, 69.1723, 2), "Khost": (33.3395, 69.9204, 2), "Miram Shah": (33.0006, 70.0712, 2), "Mir Ali": (32.99, 70.383, 3),
 "Peshawar": (34.008, 71.5785, 3), "Quetta": (30.1841, 67.0014, 3), "Kandahar": (31.6133, 65.7101, 3), "Jalalabad": (34.4265, 70.4515, 2),
 "Gardez": (33.5974, 69.2259, 2), "Wana": (32.2989, 69.5725, 3), "Parachinar": (33.8997, 70.1001, 2), "Bannu": (32.9853, 70.604, 2),
 "Dera Ismail Khan": (31.8596, 70.6488, 3), "Chaman": (30.9177, 66.4526, 2), "Spin Boldak": (31.0058, 66.4, 2), "Torkham": (34.113, 71.094, 1),
 "Ghulam Khan": (33.07, 70.176, 1), "Angoor Adda": (32.286, 69.433, 1), "Bagram": (34.946, 69.265, 1), "Ghazni": (33.5539, 68.421, 2),
 "Asadabad": (34.8731, 71.147, 2), "Qalat": (32.1058, 66.9083, 2), "Sharan": (33.2002, 68.7285, 3), "Urgun": (32.9515, 69.1828, 2),
 "Datta Khel": (32.9085, 69.7448, 3), "Rawalpindi": (33.5973, 73.0479, 3), "Islamabad": (33.7215, 73.0433, 3), "Karachi": (24.8608, 67.0104, 5),
 "Lahore": (31.558, 74.3507, 5), "Pul-i-Alam": (33.9953, 69.0227, 2), "Mihtarlam": (34.6716, 70.2092, 2), "Charikar": (35.0136, 69.1714, 2),
 "Sabari": (33.5435, 69.9118, 4), "Tani": (33.1725, 69.75, 4), "Zurmat": (33.4378, 69.0277, 2), "Chitral": (35.8518, 71.7864, 2),
 "Mingora": (34.7795, 72.3627, 2), "Kohat": (33.4491, 71.5439, 3), "Hangu": (33.532, 71.0595, 2), "Nowshera": (34.0158, 71.9812, 2),
 "Mardan": (34.3067, 72.0904, 3), "Akora Khattak": (34.0034, 72.1256, 1), "Jamrud": (34.0015, 71.3801, 1), "Landi Kotal": (34.0988, 71.1411, 1),
 "Bara": (33.98, 71.5, 3), "Darra Adam Khel": (33.68, 71.54, 2), "Tank": (32.24, 70.3926, 3), "Zhob": (31.3408, 69.4493, 2),
 "Kuchlak": (30.35, 66.97, 2), "Pishin": (30.5818, 66.9941, 2), "Shamshatoo": (33.92, 71.73, 2), "Garda Saray": (33.45, 69.62, 4),
 "Dande Darpa Khel": (33.01, 70.04, 1), "Boya": (33.03, 69.93, 2), "Razmak": (32.75, 69.84, 2), "Shawal": (32.88, 69.54, 6), "Makeen": (32.47, 69.89, 3),
 "Ladha": (32.4, 69.83, 3), "Shakai": (32.52, 69.79, 4), "Mandozai": (33.36, 69.88, 3), "Barmal": (32.7143, 69.275, 4), "Tora Bora": (34.12, 70.22, 6),
 "Dubai": (25.2048, 55.2708, 10), "Doha": (25.2854, 51.531, 10), "Zahedan": (29.4963, 60.8629, 5), "Tehran": (35.6892, 51.389, 10),
 "Mashhad": (36.2605, 59.6168, 10), "Herat": (34.3482, 62.1997, 3), "Mazar-i-Sharif": (36.709, 67.1109, 3), "Kunduz": (36.728, 68.868, 3),
 "Panjwai": (31.53, 65.44, 4), "Marjah": (31.52, 64.12, 4), "Lashkar Gah": (31.5938, 64.3716, 2), "Sangin": (32.0728, 64.8359, 2),
 "Musa Qala": (32.4457, 64.7449, 2), "Zaranj": (30.9596, 61.8604, 2), "Shah Wali Kot": (32.0795, 66.0057, 5), "Kurram": (33.7102, 70.3401, 8),
}

def jitter(lat, lon, km):
    r = rng.uniform(0, km); a = rng.uniform(0, 6.283)
    return round(lat + (r / 111.0) * (0.5 - rng.random()) * 2 * abs(__import__("math").cos(a)), 5), round(lon + (r / 95.0) * (0.5 - rng.random()) * 2 * abs(__import__("math").sin(a)), 5)

def ts(y, m, d, h=None):
    return f"{y:04d}-{m:02d}-{d:02d}T{(h if h is not None else rng.randint(5, 23)):02d}:{rng.randint(0,59):02d}:00Z"

def rand_date(start, end):
    s = dt.date.fromisoformat(start); e = dt.date.fromisoformat(end)
    d = s + dt.timedelta(days=rng.randint(0, (e - s).days)); return d

# ---- synthetic people ----
TARGETS = [
 dict(id="T01", name="Hafiz Gul Zadran", kunyas=["Abu Hafs Khosti", "Hafiz Sahib"], variants=["Hafez Gul Zadran", "Hafiz Gul Jadran", "حافظ گل ځدراڼ"], objective="OBJECTIVE GRANITE",
      tribe="Zadran", sub_tribe="Mezi", network="Haqqani Network", role="Khost attack planner; coordinates cross-border IED/VBIED cells (fictional)",
      role_history=[["2019", "2021", "Haqqani Network Miram Shah military shura member (fictional)"], ["2022", None, "Khost attack planner (fictional)"]],
      home="Khost", dob="c. 1983", pob="Garda Saray, Paktia (fictional)", priority="1", status="active", summary="SYNTHETIC. Senior Haqqani Network operative assessed to plan attacks in Khost and Paktika; moves between Khost city and Miram Shah."),
 dict(id="T02", name="Qari Nasrullah Mehsud", kunyas=["Abu Umar Waziristani", "Qari Sahib"], variants=["Qari Nasrallah Mahsud", "Nasrullah Masood"], objective="OBJECTIVE BASALT",
      tribe="Mehsud", sub_tribe="Shabi Khel", network="Tehrik-i-Taliban Pakistan", role="TTP Bannu-Lakki regional commander (fictional)",
      role_history=[["2017", "2020", "TTP South Waziristan deputy (fictional)"], ["2021", None, "TTP Bannu regional commander (fictional)"]],
      home="Bannu", dob="c. 1979", pob="Makeen, South Waziristan (fictional)", priority="1", status="active", summary="SYNTHETIC. TTP commander directing attacks on Pakistani security forces in Bannu and Lakki Marwat."),
 dict(id="T03", name="Mawlawi Abdul Rashid Kharoti", kunyas=["Mawlawi Rashid"], variants=["Abdul Rasheed Kharoti", "Maulvi Abdul Rashid"], objective="OBJECTIVE FELDSPAR",
      tribe="Kharoti", sub_tribe="", network="Taliban", role="Head of the (fictional) Finance Shura revenue committee, Kabul",
      role_history=[["2016", "2021", "Taliban shadow finance official, Paktika (fictional)"], ["2021", None, "Finance Shura revenue committee head (fictional)"]],
      home="Kabul", dob="1975-03-10 (fictional)", pob="Barmal, Paktika (fictional)", priority="2", status="active", summary="SYNTHETIC. Controls fictional revenue streams and hawala transfers between Kabul, Dubai and Doha."),
 dict(id="T04", name="Haji Daud Wazir", kunyas=["Haji Daud", "Daud Dawar"], variants=["Hajji Dawood Wazir", "Daud Khan Wazir"], objective="OBJECTIVE OBSIDIAN",
      tribe="Wazir", sub_tribe="Utmanzai (Dawar)", network="Haqqani Network", role="Logistics and vehicle procurement facilitator, Miram Shah–Khost (fictional)",
      role_history=[["2020", None, "Vehicle/explosives logistics facilitator (fictional)"]],
      home="Miram Shah", dob="c. 1988", pob="Dande Darpa Khel (fictional)", priority="2", status="active", summary="SYNTHETIC. Buys vehicles in Bannu and Peshawar and moves them to Khost for the GRANITE cell."),
 dict(id="T05", name="Engineer Sami ul-Haq Afridi", kunyas=["Engineer Sami", "Abu Yahya"], variants=["Samiul Haq Afridi", "Sami-ul-Haq"], objective="OBJECTIVE QUARTZ",
      tribe="Afridi", sub_tribe="Zakha Khel", network="Haqqani Network", role="IED/VBIED builder, Bara–Khost (fictional)",
      role_history=[["2014", "2018", "TTP Khyber bomb-maker (fictional)"], ["2019", None, "Haqqani Network IED builder (fictional)"]],
      home="Bara", dob="c. 1986", pob="Bara, Khyber (fictional)", priority="1", status="active", summary="SYNTHETIC. Technical lead for explosive devices used by the GRANITE cell."),
 dict(id="T06", name="Rahimullah Jadran", kunyas=["Rahim Jan"], variants=["Rahimullah Zadran", "Raheemullah"], objective="OBJECTIVE SLATE",
      tribe="Zadran", sub_tribe="Sultan Khel", network="Haqqani Network", role="Courier / driver for OBJECTIVE GRANITE (fictional)",
      role_history=[["2021", None, "Courier (fictional)"]],
      home="Khost", dob="c. 1996", pob="Sabari, Khost (fictional)", priority="3", status="active", summary="SYNTHETIC. Carries messages and cash between Khost, Gardez and Miram Shah; frequently crosses at Ghulam Khan."),
 dict(id="T07", name="Zahir Shah Mangal", kunyas=["Zahir Mangal", "Haji Zahir"], variants=["Zaher Shah Mangal"], objective="OBJECTIVE MARBLE",
      tribe="Mangal", sub_tribe="", network="Taliban", role="Provincial security official, Paktia (fictional) — de facto Chief of Security contact for the cell",
      role_history=[["2021", None, "Paktia provincial security official (fictional)"]],
      home="Gardez", dob="c. 1980", pob="Zurmat, Paktia (fictional)", priority="2", status="active", summary="SYNTHETIC. Government-side contact who provides movement cover and vehicle registrations."),
 dict(id="T08", name="Noor Alam Shinwari", kunyas=["Abu Talha Khorasani", "Noor Alam"], variants=["Nur Alam Shinwari"], objective="OBJECTIVE PYRITE",
      tribe="Shinwari", sub_tribe="", network="Islamic State Khorasan Province", role="ISKP media and recruitment node, Jalalabad–Peshawar (fictional)",
      role_history=[["2018", "2020", "ISKP Nangarhar media cell (fictional)"], ["2022", None, "ISKP recruiter / media (fictional)"]],
      home="Jalalabad", dob="c. 1992", pob="Achin, Nangarhar (fictional)", priority="2", status="active", summary="SYNTHETIC. Runs recruitment channels and claims; detained briefly in 2024 (fictional) and released."),
 dict(id="T09", name="Shams ud-Din Dawar", kunyas=["Shamsuddin", "Shams Mir Ali"], variants=["Shamsuddin Dawar", "Shams-ud-Din"], objective="OBJECTIVE TOPAZ",
      tribe="Dawar", sub_tribe="Malikshahi", network="Tehrik-i-Taliban Pakistan", role="TTP Mir Ali cell leader; suicide-bomber facilitator (fictional)",
      role_history=[["2019", None, "TTP Mir Ali cell leader (fictional)"]],
      home="Mir Ali", dob="c. 1985", pob="Mir Ali (fictional)", priority="1", status="active", summary="SYNTHETIC. Facilitates movement of bombers from North Waziristan into Bannu and D.I. Khan."),
 dict(id="T10", name="Bilal Ahmad Zadran", kunyas=["Bilal Khosti"], variants=["Belal Ahmad Zadran"], objective="OBJECTIVE AGATE",
      tribe="Zadran", sub_tribe="Mezi", network="Haqqani Network", role="Deputy to OBJECTIVE GRANITE; Khost city cell lead (fictional)",
      role_history=[["2022", None, "Deputy attack planner (fictional)"]],
      home="Khost", dob="c. 1990", pob="Khost city (fictional)", priority="1", status="active", summary="SYNTHETIC. Younger brother-in-law of GRANITE; runs the Khost city cell."),
 dict(id="T11", name="Mohammad Nabi Hawaladar", kunyas=["Nabi Sarraf", "Haji Nabi"], variants=["Muhammad Nabi Hawaladar", "Nabi the money-changer"], objective="OBJECTIVE JASPER",
      tribe="Ahmadzai", sub_tribe="", network="Taliban", role="Hawala operator, Sarai Shahzada, Kabul; moves funds for the Finance Shura committee (fictional)",
      role_history=[["2012", None, "Hawala operator (fictional)"]],
      home="Kabul", dob="c. 1970", pob="Pul-i-Alam, Logar (fictional)", priority="3", status="active", summary="SYNTHETIC. Financial facilitator linking Kabul hawala market to Dubai and Peshawar."),
 dict(id="T12", name="Abdul Wakil Achakzai", kunyas=["Wakil Agha"], variants=["Abdul Wakeel Achakzai"], objective="OBJECTIVE ONYX",
      tribe="Achakzai", sub_tribe="", network="Taliban", role="Quetta-based liaison and document facilitator (fictional)",
      role_history=[["2015", None, "Quetta liaison (fictional)"]],
      home="Quetta", dob="c. 1977", pob="Chaman (fictional)", priority="3", status="active", summary="SYNTHETIC. Provides travel documents and SIMs registered in Balochistan."),
 dict(id="T13", name="Ihsanullah Tanai", kunyas=["Ihsan Tanai", "Abu Bakr Tani"], variants=["Ehsanullah Tanai"], objective="OBJECTIVE CORUNDUM",
      tribe="Tani", sub_tribe="", network="Haqqani Network", role="Border-crossing coordinator, Ghulam Khan (fictional)",
      role_history=[["2021", None, "Ghulam Khan crossing coordinator (fictional)"]],
      home="Tani", dob="c. 1989", pob="Tani, Khost (fictional)", priority="3", status="active", summary="SYNTHETIC. Controls which vehicles pass unchecked at Ghulam Khan; paid by OBJECTIVE OBSIDIAN."),
 dict(id="T14", name="Sher Zaman Burki", kunyas=["Sher Zaman"], variants=["Sherzaman Burki", "Sher Zaman Baraki"], objective="OBJECTIVE GARNET",
      tribe="Burki", sub_tribe="", network="Tehrik-i-Taliban Pakistan", role="TTP finance collector, D.I. Khan–Tank (fictional)",
      role_history=[["2020", None, "TTP extortion/finance collector (fictional)"]],
      home="Dera Ismail Khan", dob="c. 1982", pob="Kaniguram, South Waziristan (fictional)", priority="3", status="active", summary="SYNTHETIC. Collects extortion payments and moves cash to BASALT via Tank."),
]
FAMILY = [("T01", "T10", "brother_in_law_of"), ("T01", "T06", "uncle_of"), ("T02", "T09", "cousin_of"), ("T04", "T13", "brother_of"), ("T03", "T11", "father_in_law_of")]
LINKS = [("T10", "T01", "deputy_of"), ("T06", "T01", "courier_for"), ("T04", "T01", "supplies"), ("T05", "T01", "supplies"), ("T13", "T04", "paid_by"),
         ("T07", "T01", "protects"), ("T07", "T04", "registers_vehicles_for"), ("T11", "T03", "moves_funds_for"), ("T03", "T01", "funds"), ("T12", "T04", "provides_documents_to"),
         ("T12", "T02", "provides_documents_to"), ("T14", "T02", "collects_for"), ("T09", "T02", "subordinate_of"), ("T08", "T05", "procures_from"), ("T02", "T01", "coordinates_with")]
AFFIL = {"T01": "Haqqani Network", "T02": "Tehrik-i-Taliban Pakistan", "T03": "Taliban", "T04": "Haqqani Network", "T05": "Haqqani Network", "T06": "Haqqani Network", "T07": "Taliban",
         "T08": "Islamic State Khorasan Province", "T09": "Tehrik-i-Taliban Pakistan", "T10": "Haqqani Network", "T11": "Taliban", "T12": "Taliban", "T13": "Haqqani Network", "T14": "Tehrik-i-Taliban Pakistan"}

CARRIERS_AF = [("Roshan", "41220"), ("AWCC", "41201"), ("MTN Afghanistan", "41240"), ("Etisalat Afghanistan", "41250")]
CARRIERS_PK = [("Jazz", "41001"), ("Zong", "41004"), ("Telenor PK", "41006"), ("Ufone", "41003")]
VEHICLES = [("Toyota", "Corolla", "2008", "white"), ("Toyota", "Hilux Vigo", "2012", "silver"), ("Toyota", "Land Cruiser 80", "1998", "beige"), ("Suzuki", "Bolan", "2015", "white"),
            ("Toyota", "Fielder", "2010", "silver"), ("Toyota", "Surf", "2004", "green"), ("Honda", "CD-70 motorcycle", "2019", "red"), ("Toyota", "Corolla", "2014", "grey"), ("Hyundai", "Shehzore", "2017", "white")]
PLATFORMS = ["Facebook", "Telegram", "X", "WhatsApp", "TikTok", "Instagram"]
sel_counter = [0]
def sid(): sel_counter[0] += 1; return f"SEL-{sel_counter[0]:04d}"

def phone(cc):
    if cc == "AF": return f"+93 7{rng.choice([0,1,2,7,8,9])}{rng.randint(0,9)} 555 {rng.randint(0,9999):04d}"
    return f"+92 3{rng.choice([0,1,2,3,4])}{rng.randint(0,9)} 555 {rng.randint(0,9999):04d}"
def imsi(cc):
    name, mcc = rng.choice(CARRIERS_AF if cc == "AF" else CARRIERS_PK); return name, f"{mcc}99{rng.randint(0,99999999):08d}"
def imei(): body = f"00000000{rng.randint(0,999999):06d}"; return body + "0"
def email(nm): first = nm.split()[0].lower().replace("'", ""); return f"{first}.{rng.choice(['khost','kabul','psh','qta','waz'])}{rng.randint(10,99)}@example.{rng.choice(['com','net','org'])}"
def handle(nm): return "@" + nm.split()[0].lower().replace("'", "") + rng.choice(["_", "."]) + rng.choice(["afg", "ps", "313", "khr", "wzr"]) + str(rng.randint(1, 99))

def gen_selectors(t):
    cc = "PK" if t["home"] in ("Miram Shah", "Mir Ali", "Bannu", "Peshawar", "Quetta", "Bara", "Dera Ismail Khan", "Wana") else "AF"
    S, L = [], []
    def add(kind, value, **f):
        s = dict(id=sid(), entity=t["id"], kind=kind, value=value, dataset="synthetic", **f); S.append(s); return s["id"]
    phones = []
    for i in range(rng.randint(1, 3)):
        c = cc if i == 0 else rng.choice(["AF", "PK"])
        carrier, im = imsi(c)
        p = add("phone", phone(c), label=f"handset {i+1}", provider=carrier, country=c, first_seen=str(rand_date("2024-01-01", "2025-06-30")), confidence=rng.choice(["high", "high", "medium"]))
        s_imsi = add("imsi", im, provider=carrier, country=c, label=f"SIM for handset {i+1}")
        s_imei = add("imei", imei(), label=f"handset {i+1} hardware", provider=rng.choice(["Samsung", "Tecno", "Infinix", "Nokia", "Oppo", "Xiaomi"]))
        L += [(p, s_imsi, "same_subscriber", "SS7/CDR: MSISDN and IMSI observed together", "high"), (s_imsi, s_imei, "used_with", "CDR: IMSI registered on this IMEI", "high")]
        phones.append((p, s_imsi, s_imei))
    e = add("email", email(t["name"]), provider="example.com (fictional)")
    apps = rng.sample(PLATFORMS, rng.randint(1, 3))
    for a in apps:
        h = add("social", handle(t["name"]), platform=a, label=f"{a} account", confidence=rng.choice(["high", "medium", "low"]))
        if a in ("WhatsApp", "Telegram"): L.append((h, phones[0][0], "registered_with", f"{a} account registered to this number", "high"))
        else: L.append((h, e, "recovery_contact", f"{a} recovery e-mail", "medium"))
    if t["id"] in ("T03", "T11", "T14", "T04", "T12"):
        cma = add("cma_account", f"{t['name'].split()[0]} {rng.choice(['Trading','Exchange','General Store','Transport','Money Changer'])} (fictional)", platform=rng.choice(["EasyPaisa", "JazzCash", "HesabPay", "M-Paisa"]),
                  label="mobile-money / CMA account", confidence="medium")
        L += [(cma, phones[0][0], "registered_with", "CMA account registered to this MSISDN", "high"), (cma, e, "registered_with", "CMA account contact e-mail", "medium")]
    if t["id"] in ("T01", "T04", "T06", "T07", "T10", "T02", "T09", "T12", "T14"):
        mk, md, yr, col = rng.choice(VEHICLES)
        v = add("vehicle", f"{col} {mk} {md} ({yr})", label="vehicle", platform=f"plate {rng.choice(['KHO','PKT','BNU','QTA','KBL'])}-{rng.randint(1000,9999)} (fictional)", confidence="medium")
        L.append((v, phones[0][0], "co_located", "ISR: handset tracked inside this vehicle on 3+ occasions", "medium"))
    return S, L, phones

SITES = [
 # name, kind, operator, status, place, lat, lon, precision_km, note
 ("U.S. Embassy Kabul (suspended 2021)", "usg_diplomatic", "United States", "closed", "Kabul", 34.5346, 69.1860, 1, "Operations suspended 31 Aug 2021; approximate location, verify."),
 ("U.S. Embassy Islamabad", "usg_diplomatic", "United States", "active", "Islamabad", 33.7250, 73.1150, 2, "Diplomatic Enclave; approximate."),
 ("U.S. Consulate General Peshawar", "usg_diplomatic", "United States", "active", "Peshawar", 34.0030, 71.5280, 2, "Approximate."),
 ("U.S. Consulate General Karachi", "usg_diplomatic", "United States", "active", "Karachi", 24.8450, 67.0320, 3, "Approximate."),
 ("U.S. Consulate General Lahore", "usg_diplomatic", "United States", "active", "Lahore", 31.5500, 74.3300, 3, "Approximate."),
 ("U.S. Consulate Herat (closed 2021)", "usg_diplomatic", "United States", "closed", "Herat", 34.3480, 62.2030, 3, "Approximate."),
 ("U.S. Consulate Mazar-e Sharif (closed 2021)", "usg_diplomatic", "United States", "closed", "Mazar-i-Sharif", 36.7090, 67.1100, 3, "Approximate."),
 ("Bagram Airfield (handed over 2021)", "usg_military", "United States / NATO", "historical", "Bagram", 34.9461, 69.2650, 1, "Former main US base; now Afghan/Taliban controlled."),
 ("Camp Chapman / Khost Airfield", "usg_military", "United States (former)", "historical", "Khost", 33.3330, 69.9530, 1, "Site of Dec 2009 attack; approximate."),
 ("FOB Salerno (former)", "usg_military", "United States (former)", "historical", "Khost", 33.3640, 69.9560, 1, "Approximate."),
 ("Kandahar Airfield (former ISAF)", "usg_military", "United States / NATO (former)", "historical", "Kandahar", 31.5058, 65.8478, 1, ""),
 ("Camp Bastion / Leatherneck (former)", "other_gov_military", "United Kingdom / United States (former)", "historical", "Lashkar Gah", 31.8638, 64.2246, 1, ""),
 ("Shamsi Airfield", "other_gov_military", "Pakistan", "active", "Dalbandin", 27.8450, 65.1630, 2, "Formerly used for US drone operations (to 2011)."),
 ("British Embassy Kabul (suspended 2021)", "other_gov_diplomatic", "United Kingdom", "closed", "Kabul", 34.5330, 69.1850, 1, "Wazir Akbar Khan area; approximate."),
 ("British High Commission Islamabad", "other_gov_diplomatic", "United Kingdom", "active", "Islamabad", 33.7260, 73.1170, 2, "Approximate."),
 ("Embassy of Pakistan, Kabul", "other_gov_diplomatic", "Pakistan", "active", "Kabul", 34.5340, 69.1800, 1, "Approximate."),
 ("Embassy of China, Kabul", "other_gov_diplomatic", "China", "active", "Kabul", 34.5320, 69.1800, 1, "Approximate."),
 ("Embassy of Russia, Kabul", "other_gov_diplomatic", "Russia", "active", "Kabul", 34.5200, 69.1370, 1, "Darulaman Road; attacked Sep 2022; approximate."),
 ("Embassy of Iran, Kabul", "other_gov_diplomatic", "Iran", "active", "Kabul", 34.5300, 69.1830, 1, "Approximate."),
 ("Embassy of Qatar, Kabul", "other_gov_diplomatic", "Qatar", "active", "Kabul", 34.5350, 69.1900, 1, "Approximate."),
 ("Embassy of Turkey, Kabul", "other_gov_diplomatic", "Turkey", "active", "Kabul", 34.5310, 69.1870, 1, "Approximate."),
 ("Consulate of India, Jalalabad (closed)", "other_gov_diplomatic", "India", "closed", "Jalalabad", 34.4300, 70.4500, 2, "Attacked 2013; approximate."),
 ("Consulate of India, Kandahar (closed)", "other_gov_diplomatic", "India", "closed", "Kandahar", 31.6130, 65.7090, 2, "Approximate."),
 ("Consulate of Iran, Jalalabad", "other_gov_diplomatic", "Iran", "active", "Jalalabad", 34.4270, 70.4530, 2, "Approximate."),
 ("Consulate of Pakistan, Jalalabad", "other_gov_diplomatic", "Pakistan", "active", "Jalalabad", 34.4280, 70.4480, 2, "Approximate."),
 ("Consulate of Afghanistan, Peshawar", "host_gov", "Afghanistan", "active", "Peshawar", 34.0120, 71.5600, 2, "Approximate."),
 ("UNAMA HQ Kabul", "intl_org", "United Nations", "active", "Kabul", 34.5370, 69.1960, 1, "Approximate."),
 ("ICRC Kabul delegation", "intl_org", "ICRC", "active", "Kabul", 34.5250, 69.1700, 2, "Approximate."),
 ("Kabul Serena Hotel", "soft_target", "private", "active", "Kabul", 34.5270, 69.1750, 1, "Attacked 2008, 2014."),
 ("Intercontinental Hotel Kabul", "soft_target", "private", "active", "Kabul", 34.5390, 69.1340, 1, "Attacked 2011, 2018."),
 ("Hamid Karzai International Airport", "infrastructure", "Afghanistan", "active", "Kabul", 34.5658, 69.2123, 1, "Abbey Gate attack 26 Aug 2021."),
 ("Torkham border crossing", "border_crossing", "Afghanistan / Pakistan", "active", "Torkham", 34.1130, 71.0940, 1, ""),
 ("Chaman–Spin Boldak border crossing", "border_crossing", "Afghanistan / Pakistan", "active", "Chaman", 30.9200, 66.4450, 1, ""),
 ("Ghulam Khan border crossing", "border_crossing", "Afghanistan / Pakistan", "active", "Ghulam Khan", 33.0700, 70.1760, 1, ""),
 ("Angoor Adda border crossing", "border_crossing", "Afghanistan / Pakistan", "active", "Angoor Adda", 32.2860, 69.4330, 1, ""),
 ("Pakistan Army 11 Corps HQ Peshawar", "host_gov_military", "Pakistan", "active", "Peshawar", 34.0050, 71.5400, 2, "Approximate."),
 ("Bannu Cantonment", "host_gov_military", "Pakistan", "active", "Bannu", 32.9900, 70.6100, 2, "Approximate; attacked 2024/2025."),
 ("Miran Shah Cantonment / FC camp", "host_gov_military", "Pakistan", "active", "Miram Shah", 33.0030, 70.0800, 2, "Approximate."),
]

def main():
    persons, rels, selectors, links, hits, attacks = [], [], [], [], [], []
    tmap = {t["id"]: t for t in TARGETS}
    def person_rec(t):
        return dict(name=t["name"], aliases=t["kunyas"] + t["variants"] + [t["objective"]], role=t["role"], organizations=[AFFIL[t["id"]]], nationality_or_origin=("Pakistani" if t["home"] in ("Miram Shah","Mir Ali","Bannu","Peshawar","Quetta","Bara","Dera Ismail Khan") else "Afghan") + " (fictional)",
                    status="alive", family=[], locations=[t["home"]], is_presenter_or_guest=False, mentions=[{"timestamp": "000:00", "quote": "SYNTHETIC target record for demonstration."}])
    for t in TARGETS:
        persons.append(person_rec(t))
        S, L, phones = gen_selectors(t); selectors += S; links += L; t["_phones"] = phones
        # location hits: home-centred pattern + travel
        n = rng.randint(6, 18); last = None
        places = [t["home"]] * 4 + {"T01": ["Miram Shah", "Gardez", "Sabari", "Dande Darpa Khel"], "T02": ["Mir Ali", "Makeen", "Dera Ismail Khan", "Tank"], "T03": ["Dubai", "Doha", "Kabul", "Pul-i-Alam"],
                                     "T04": ["Bannu", "Peshawar", "Khost", "Ghulam Khan"], "T05": ["Peshawar", "Jamrud", "Khost", "Landi Kotal"], "T06": ["Gardez", "Miram Shah", "Ghulam Khan", "Khost"],
                                     "T07": ["Kabul", "Zurmat", "Khost"], "T08": ["Peshawar", "Torkham", "Shamshatoo", "Jalalabad"], "T09": ["Bannu", "Datta Khel", "Miram Shah"], "T10": ["Khost", "Mandozai", "Tani"],
                                     "T11": ["Dubai", "Peshawar", "Kabul", "Jalalabad"], "T12": ["Chaman", "Kuchlak", "Spin Boldak", "Kandahar"], "T13": ["Ghulam Khan", "Khost", "Miram Shah"], "T14": ["Tank", "Bannu", "Wana"]}[t["id"]]
        for i in range(n):
            pl = rng.choice(places); lat0, lon0, prec = G[pl]
            kind = rng.choices(["gsm_cdr", "ss7", "travel", "isr", "humint", "open_source"], weights=[5, 3, 2, 2, 1, 1])[0]
            d = rand_date("2025-01-01", "2026-09-30"); when = ts(d.year, d.month, d.day)
            ph = rng.choice(phones)
            if kind == "gsm_cdr":
                lat, lon = jitter(lat0, lon0, 2.5); h = dict(kind=kind, precision_km=round(rng.uniform(0.8, 3.0), 1), selector=ph[1], detail=f"Cell registration on tower {pl[:3].upper()}-{rng.randint(100,999)} (LAC {rng.randint(1000,9999)}/CID {rng.randint(10000,65000)}), {rng.randint(2,48)} events over {rng.randint(1,6)} h", confidence="high")
            elif kind == "ss7":
                lat, lon = jitter(lat0, lon0, 4); h = dict(kind=kind, precision_km=round(rng.uniform(2, 8), 1), selector=ph[1], detail=f"SS7 ATI/PSI location query: VLR {pl}, cell-level answer", confidence="medium")
            elif kind == "travel":
                xp = rng.choice(["Ghulam Khan", "Torkham", "Chaman", "Angoor Adda"]) if pl not in ("Dubai", "Doha") else pl
                lat, lon, prec = G[xp]; lat, lon = jitter(lat, lon, 0.3); h = dict(kind=kind, precision_km=0.5, selector=None, detail=(f"Border crossing record at {xp} (vehicle {rng.choice(['white Corolla','Hilux','Land Cruiser','bus'])})" if xp not in ("Dubai","Doha") else f"Air travel: arrival {xp} (passenger manifest, document #{rng.randint(100000,999999)} fictional)"), confidence="high"); pl = xp
            elif kind == "isr":
                lat, lon = jitter(lat0, lon0, 0.8); h = dict(kind=kind, precision_km=0.1, selector=None, detail=f"ISR full-motion video: subject identified at compound, {rng.randint(10,90)} min dwell", confidence="high")
            elif kind == "humint":
                lat, lon = jitter(lat0, lon0, 3); h = dict(kind=kind, precision_km=5.0, selector=None, detail="Source report: subject seen at a meeting (single-source, uncorroborated)", confidence="low")
            else:
                lat, lon = jitter(lat0, lon0, 3); h = dict(kind=kind, precision_km=3.0, selector=None, detail="Geotagged social-media post by associate account", confidence="low")
            h.update(entity=t["id"], ts=when, lat=lat, lon=lon, place=pl, dataset="synthetic"); hits.append(h)
    # family + operational links (fictional person ↔ fictional person) and member_of real orgs
    for a, b, rel in FAMILY:
        rels.append(dict(source=tmap[a]["name"], target=tmap[b]["name"], type=rel, detail="SYNTHETIC family link", date="2025", confidence="stated", timestamp="000:00", quote="SYNTHETIC"))
    for a, b, rel in LINKS:
        rels.append(dict(source=tmap[a]["name"], target=tmap[b]["name"], type=rel, detail="SYNTHETIC operational link", date="2025", confidence="stated", timestamp="000:00", quote="SYNTHETIC"))
    for t in TARGETS:
        rels.append(dict(source=t["name"], target=AFFIL[t["id"]], type="member_of", detail="SYNTHETIC link to a real organization", date="2025", confidence="stated", timestamp="000:00", quote="SYNTHETIC"))
    # cross-target selector correlations (shared handset, shared vehicle, calling pattern)
    byent = {}
    for s in selectors: byent.setdefault(s["entity"], []).append(s)
    def first(eid_, kind): return next(s["id"] for s in byent[eid_] if s["kind"] == kind)
    links += [(first("T06", "imei"), first("T01", "imsi"), "used_with", "CDR: GRANITE's SIM registered on courier's handset 2026-03-14 to 2026-03-16 (handset hand-off)", "high"),
              (first("T04", "vehicle"), first("T13", "phone"), "co_located", "ISR: CORUNDUM's handset inside OBSIDIAN's Hilux at Ghulam Khan", "medium"),
              (first("T10", "phone"), first("T01", "phone"), "frequent_contact", "CDR: 140 calls / 90 days", "high"),
              (first("T06", "phone"), first("T01", "phone"), "frequent_contact", "CDR: 85 calls / 90 days", "high"),
              (first("T11", "phone"), first("T03", "phone"), "frequent_contact", "CDR: 60 calls / 90 days; spikes before Dubai trips", "high"),
              (first("T14", "cma_account"), first("T02", "phone"), "transfers_to", "Mobile-money transfers to BASALT's number, 12 × PKR 25k (fictional)", "medium"),
              (first("T05", "email"), first("T08", "social"), "recovery_contact", "QUARTZ e-mail is recovery address on PYRITE's Telegram (fictional)", "low"),
              (first("T09", "phone"), first("T02", "phone"), "frequent_contact", "CDR: 44 calls / 90 days", "high")]
    # attacks (synthetic events with geometry)
    ATT = [("2025-02-11", "Khost", "Haqqani Network", "VBIED against district police HQ (fictional)", ["T01", "T05", "T10"]), ("2025-03-03", "Bannu", "Tehrik-i-Taliban Pakistan", "Complex attack on cantonment gate (fictional)", ["T02", "T09"]),
           ("2025-04-18", "Dera Ismail Khan", "Tehrik-i-Taliban Pakistan", "IED on security convoy (fictional)", ["T02", "T14"]), ("2025-05-22", "Jalalabad", "Islamic State Khorasan Province", "Suicide bombing at bank queue (fictional)", ["T08"]),
           ("2025-06-09", "Gardez", "Haqqani Network", "Magnetic IED on official vehicle (fictional)", ["T06", "T05"]), ("2025-07-14", "Mir Ali", "Tehrik-i-Taliban Pakistan", "Ambush on FC patrol (fictional)", ["T09"]),
           ("2025-08-02", "Kabul", "Islamic State Khorasan Province", "Attack near foreign embassy quarter, Wazir Akbar Khan (fictional)", ["T08"]), ("2025-08-29", "Tank", "Tehrik-i-Taliban Pakistan", "Extortion-related grenade attack (fictional)", ["T14"]),
           ("2025-09-17", "Sabari", "Haqqani Network", "Rocket attack on district centre (fictional)", ["T10"]), ("2025-10-05", "Peshawar", "Islamic State Khorasan Province", "Targeted killing of cleric (fictional)", ["T08"]),
           ("2025-11-20", "Khost", "Haqqani Network", "VBIED intercepted at checkpoint; vehicle traced to OBSIDIAN (fictional)", ["T04", "T13"]), ("2025-12-12", "Bannu", "Tehrik-i-Taliban Pakistan", "Quadcopter-dropped munition on police post (fictional)", ["T02"]),
           ("2026-01-08", "Parachinar", "Tehrik-i-Taliban Pakistan", "Convoy ambush (fictional)", ["T09"]), ("2026-02-14", "Jamrud", "Islamic State Khorasan Province", "IED near checkpoint (fictional)", ["T05", "T08"]),
           ("2026-03-21", "Miram Shah", "Haqqani Network", "Attack planning meeting raided; two detained (fictional)", ["T01", "T04"]), ("2026-04-10", "Zurmat", "Haqqani Network", "IED on Taliban security vehicle after internal dispute (fictional)", ["T07"]),
           ("2026-05-05", "Hangu", "Tehrik-i-Taliban Pakistan", "Attack on police station (fictional)", ["T02"]), ("2026-06-19", "Khost", "Haqqani Network", "Suicide bomber neutralised near market (fictional)", ["T10", "T05"]),
           ("2026-07-07", "Chaman", "Tehrik-i-Taliban Pakistan", "IED at border market (fictional)", ["T12"]), ("2026-08-15", "Kabul", "Islamic State Khorasan Province", "Attempted attack on hotel hosting foreign delegation (fictional)", ["T08"]),
           ("2026-09-02", "Bannu", "Tehrik-i-Taliban Pakistan", "VBIED on cantonment perimeter (fictional)", ["T02", "T09", "T14"]), ("2026-09-20", "Ghulam Khan", "Haqqani Network", "Explosives seizure at crossing (fictional)", ["T13", "T04"])]
    for d, pl, grp, desc, actors in ATT:
        lat, lon = jitter(*G[pl][:2], 1.5)
        attacks.append(dict(date=d, date_precision="day", type="attack", description=f"SYNTHETIC: {desc}", place=pl, actors=[tmap[a]["name"] for a in actors] + [grp], timestamp="000:00", lat=lat, lon=lon, precision_km=1.5, group=grp))
    cards = [dict(entity=t["id"], name=t["name"], objective_name=t["objective"], kunyas=t["kunyas"], name_variants=t["variants"], tribe=t["tribe"], sub_tribe=t["sub_tribe"], network=t["network"],
                  role_current=t["role"], role_history=t["role_history"], priority=t["priority"], status=t["status"], dob=t["dob"], pob=t["pob"], home_area=t["home"], summary=t["summary"], dataset="synthetic") for t in TARGETS]
    out = dict(scenario_kind="targets", episode={"idx": None, "title": "SYNTHETIC: target-tracking demo — Khost/Waziristan attack network", "published": "2026-10-12"},
               persons=persons, organizations=[], places=[{"name": p, "type": "populated place", "country": "Afghanistan" if G[p][0] > 0 else ""} for p in sorted({t["home"] for t in TARGETS})],
               events=attacks, relationships=rels, target_cards=cards, selectors=selectors,
               selector_links=[dict(a=a, b=b, relation=r, evidence=e, confidence=c, dataset="synthetic") for a, b, r, e, c in links], location_hits=hits)
    json.dump(out, open(f"{ROOT}/synthetic/targets_demo.json", "w"), indent=1, ensure_ascii=False)
    json.dump([dict(name=n, kind=k, operator=o, status=s, place=p, lat=la, lon=lo, precision_km=pr, verified=0, source="public_reference", note=nt) for n, k, o, s, p, la, lo, pr, nt in SITES],
              open(f"{ROOT}/synthetic/sites_reference.json", "w"), indent=1, ensure_ascii=False)
    print("targets", len(cards), "selectors", len(selectors), "links", len(out["selector_links"]), "hits", len(hits), "attacks", len(attacks), "sites", len(SITES))

if __name__ == "__main__":
    main()

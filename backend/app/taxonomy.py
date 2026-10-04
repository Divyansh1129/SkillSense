"""Seed taxonomy.

NOTE (data honesty): NCO codes are unit-group-level codes aligned to NCO-2015 / ISCO-08 structure, NSQF levels and SSC
labels are *illustrative* for the demo and must be verified against official NCO/NSQF registers before production.
District codes are LGD-style *illustrative* codes ("UP-LKO"), not official LGD codes.
"""

STATES = [("UP", "Uttar Pradesh"), ("MH", "Maharashtra")]

# code, name, state, type, size_factor, aliases (English / Hindi / Marathi spellings)
DISTRICTS = [
    ("UP-LKO", "Lucknow", "UP", "urban", 1.3, ["lucknow", "lko", "lakhnau", "लखनऊ"]),
    ("UP-KNP", "Kanpur Nagar", "UP", "urban", 1.2, ["kanpur nagar", "kanpur", "knp", "कानपुर"]),
    ("UP-VNS", "Varanasi", "UP", "urban", 1.0, ["varanasi", "banaras", "benares", "वाराणसी"]),
    ("UP-PRY", "Prayagraj", "UP", "semi", 1.0, ["prayagraj", "allahabad", "प्रयागराज", "इलाहाबाद"]),
    ("UP-GBN", "Gautam Buddh Nagar", "UP", "urban", 1.4, ["gautam buddh nagar", "gb nagar", "noida", "greater noida", "नोएडा"]),
    ("UP-AGR", "Agra", "UP", "semi", 0.9, ["agra", "आगरा"]),
    ("UP-GKP", "Gorakhpur", "UP", "semi", 0.8, ["gorakhpur", "गोरखपुर"]),
    ("UP-BRH", "Bahraich", "UP", "rural", 0.5, ["bahraich", "बहराइच"]),
    ("UP-STP", "Sitapur", "UP", "rural", 0.5, ["sitapur", "सीतापुर"]),
    ("UP-JHS", "Jhansi", "UP", "semi", 0.6, ["jhansi", "झांसी"]),
    ("MH-MUS", "Mumbai Suburban", "MH", "urban", 1.6, ["mumbai suburban", "mumbai", "bombay", "andheri", "मुंबई"]),
    ("MH-PUN", "Pune", "MH", "urban", 1.5, ["pune", "poona", "पुणे"]),
    ("MH-NGP", "Nagpur", "MH", "urban", 1.1, ["nagpur", "नागपूर"]),
    ("MH-NSK", "Nashik", "MH", "semi", 1.0, ["nashik", "nasik", "नाशिक"]),
    ("MH-AUR", "Chhatrapati Sambhajinagar", "MH", "semi", 0.9, ["chhatrapati sambhajinagar", "sambhajinagar", "aurangabad", "औरंगाबाद"]),
    ("MH-THN", "Thane", "MH", "urban", 1.4, ["thane", "navi mumbai", "kalyan", "ठाणे"]),
    ("MH-KOP", "Kolhapur", "MH", "semi", 0.7, ["kolhapur", "कोल्हापूर"]),
    ("MH-GAD", "Gadchiroli", "MH", "rural", 0.25, ["gadchiroli", "गडचिरोली"]),
    ("MH-NND", "Nanded", "MH", "semi", 0.6, ["nanded", "नांदेड"]),
    ("MH-AMT", "Amravati", "MH", "semi", 0.6, ["amravati", "amaravati", "अमरावती"]),
]

SECTORS = [("ELE", "Electronics & Electrical"), ("REN", "Renewable Energy / Green Jobs"), ("HLT", "Healthcare")]

# code, name, sector, nco_code, nsqf_level, ssc, turnover_rate (annual openings / employment), seed phrases
TRADES = [
    ("ELE01", "Electrician (Domestic)", "ELE", "7411", 4, "PSSC", 0.14,
     ["electrician", "domestic electrician", "house wiring electrician", "wireman", "electrician helper",
      "bijli mistri", "vij mistri", "इलेक्ट्रीशियन", "बिजली मिस्त्री", "वीज मिस्त्री"]),
    ("ELE02", "Field Technician (Electronics)", "ELE", "7421", 4, "ESSCI",  0.14,
     ["field technician electronics", "electronics field technician", "field service technician",
      "service engineer electronics", "installation technician electronics", "फील्ड टेक्नीशियन"]),
    ("ELE03", "CCTV Installer", "ELE", "7422", 4, "ESSCI", 0.14,
     ["cctv installer", "cctv technician", "security camera installer", "cctv camera fitting technician",
      "surveillance camera installation", "dvr cctv technician", "सीसीटीवी टेक्नीशियन"]),
    ("ELE04", "Consumer Electronics Repair Technician", "ELE", "7421", 4, "ESSCI", 0.14,
     ["consumer electronics repair technician", "tv repair technician", "home appliance repair technician",
      "washing machine repair technician", "tv mechanic", "television mistri", "टीवी मिस्त्री"]),
    ("ELE05", "Electrical Maintenance Technician", "ELE", "7412", 5, "PSSC", 0.14,
     ["electrical maintenance technician", "maintenance electrician", "plant electrician", "industrial electrician",
      "factory maintenance technician electrical", "इलेक्ट्रिकल मेंटेनेंस टेक्नीशियन"]),
    ("ELE06", "Mobile Phone Repair Technician", "ELE", "7421", 3, "ESSCI", 0.14,
     ["mobile phone repair technician", "mobile repairing", "mobile mistri", "smartphone repair technician",
      "mobile service technician", "मोबाइल मिस्त्री", "मोबाइल रिपेयरिंग"]),

    ("REN01", "Solar PV Installer", "REN", "7412", 4, "SCGJ", 0.20,
     ["solar pv installer", "solar panel installer", "suryamitra", "solar installation technician",
      "rooftop solar installer", "solar technician", "solar fitter", "सोलर टेक्नीशियन", "सोलर पैनल इंस्टॉलर"]),
    ("REN02", "Solar Rooftop O&M Technician", "REN", "7412", 4, "SCGJ", 0.20,
     ["solar rooftop o&m technician", "solar maintenance technician", "solar plant operator", "solar o&m technician",
      "solar rooftop service technician", "solar inverter service technician"]),
    ("REN03", "Solar Pump Technician", "REN", "7412", 4, "SCGJ", 0.20,
     ["solar pump technician", "solar water pump installer", "solar pump mechanic", "solar pump service technician",
      "solar pump fitter"]),
    ("REN04", "Wind Turbine Technician", "REN", "7412", 5, "SCGJ", 0.20,
     ["wind turbine technician", "wind turbine maintenance technician", "wind farm technician", "wind o&m technician",
      "windmill technician", "wtg technician"]),
    ("REN05", "EV Charging Technician", "REN", "7412", 4, "SCGJ", 0.20,
     ["ev charging station technician", "ev charger installer", "electric vehicle charging technician",
      "ev charging maintenance technician", "charging point technician"]),
    ("REN06", "Biogas Plant Technician", "REN", "3131", 4, "SCGJ", 0.20,
     ["biogas plant technician", "biogas technician", "gobar gas technician", "biogas plant operator",
      "biogas mistri", "biogas maintenance technician"]),

    ("HLT01", "General Duty Assistant", "HLT", "5321", 4, "HSSC", 0.12,
     ["general duty assistant", "gda", "ward boy", "hospital attendant", "patient care assistant", "nursing assistant",
      "ward assistant", "hospital helper", "वार्ड बॉय", "जनरल ड्यूटी असिस्टेंट"]),
    ("HLT02", "Phlebotomist", "HLT", "3212", 4, "HSSC", 0.12,
     ["phlebotomist", "phlebotomy technician", "blood collection technician", "sample collection executive",
      "lab sample collector", "home sample collection phlebotomist", "फ्लेबोटोमिस्ट"]),
    ("HLT03", "Home Health Aide", "HLT", "5322", 4, "HSSC", 0.12,
     ["home health aide", "home care assistant", "home nurse attendant", "elderly care attendant", "caregiver home",
      "patient attendant home care", "home health attendant", "ayah", "आया", "होम केयर अटेंडेंट"]),
    ("HLT04", "Emergency Medical Technician (Basic)", "HLT", "3258", 4, "HSSC", 0.12,
     ["emergency medical technician", "emt basic", "ambulance technician", "ambulance paramedic assistant",
      "paramedic", "emergency medical responder", "एम्बुलेंस टेक्नीशियन"]),
    ("HLT05", "Dialysis Technician", "HLT", "3212", 5, "HSSC", 0.12,
     ["dialysis technician", "hemodialysis technician", "renal dialysis technician", "dialysis assistant",
      "dialysis machine technician", "dialysis unit technician"]),
    ("HLT06", "Medical Lab Technician (Assistant)", "HLT", "3212", 5, "HSSC", 0.12,
     ["lab technician", "medical lab technician", "pathology lab technician", "laboratory assistant", "dmlt technician",
      "lab assistant pathology", "लैब टेक्नीशियन"]),
]

TRADE_BY_CODE = {t[0]: t for t in TRADES}
DISTRICT_BY_CODE = {d[0]: d for d in DISTRICTS}
SECTOR_NAME = dict(SECTORS)
STATE_NAME = dict(STATES)


def seed_rows() -> list[tuple[str, str]]:
    """(seed phrase, trade_code) rows for the taxonomy_seeds table."""
    return [(s, t[0]) for t in TRADES for s in t[7]]

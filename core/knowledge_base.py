"""
GehunGuru knowledge base (sample data for the project).

Content is PARAPHRASED from publicly available wheat guidance for the
North-Western Plains Zone of India (ICAR-IIWBR Karnal, PAU Ludhiana and
CCS HAU Hisar packages of practices, Kisan Call Centre material). It is a
teaching dataset, not an official document. Pesticide doses are deliberately
left out: the bot must send farmers to the product label / KVK for doses.

Each entry:
    id        stable id the model must cite, e.g. "KB-08"
    title     short English title
    stages    crop-stage keys the entry is most relevant to
    keywords  English + Hindi + Hinglish + Punjabi words (used by the
              offline fallback search when the AI is unavailable)
    text      the fact sheet the model is grounded on
"""

from __future__ import annotations

import re
from typing import Iterable

SOURCE_NOTE = (
    "Paraphrased from public guidance by ICAR-IIWBR (Karnal), PAU (Ludhiana) and "
    "CCS HAU (Hisar); compiled as sample data for an academic project. Verify with "
    "the latest state package of practices or your KVK before acting."
)

KB: list[dict] = [
    {
        "id": "KB-01",
        "title": "Sowing window for wheat in North-West India",
        "stages": ["pre_sowing"],
        "keywords": ["sowing", "sow", "time", "date", "when", "buvai", "buwai", "बुवाई", "बिजाई",
                     "bijai", "ਬਿਜਾਈ", "late", "pichheti", "पछेती", "timely", "agheti", "अगेती"],
        "text": (
            "Timely sowing for irrigated wheat in Punjab and Haryana is roughly 25 October to 15 November; "
            "in western Uttar Pradesh, Delhi NCR and north Rajasthan roughly 1 to 20 November. "
            "Late sowing runs from the end of that timely window (mid to late November) up to about 20 December, "
            "using late-sown varieties and a higher seed rate; sowing after about 20 December is very late. "
            "Yield potential falls steadily with every week of delay because the crop meets terminal heat "
            "at grain filling in March. Sow when the average day temperature has come down to about 20 to 22 °C "
            "and the soil has proper moisture (vattar). Sowing too early in hot weather causes poor tillering."
        ),
    },
    {
        "id": "KB-02",
        "title": "Choosing a variety",
        "stages": ["pre_sowing"],
        "keywords": ["variety", "varieties", "seed", "kism", "किस्म", "ਕਿਸਮ", "HD", "PBW", "DBW",
                     "best", "which", "kaunsi", "कौनसी", "beej", "बीज"],
        "text": (
            "Choose a variety notified for the North-Western Plains Zone and for your sowing time. "
            "Examples for timely sown irrigated conditions: HD 3086, DBW 187, DBW 222, DBW 303, HD 3226, PBW 826. "
            "Examples for late sown irrigated conditions: PBW 752, DBW 173, HD 3059. "
            "Prefer varieties with resistance to yellow rust and brown rust, especially in foothill districts. "
            "New varieties are released every year, so confirm the current list for your district with the KVK "
            "or state agriculture university. Buy certified seed from an authorised source and keep the bill."
        ),
    },
    {
        "id": "KB-03",
        "title": "Seed rate, spacing and depth",
        "stages": ["pre_sowing"],
        "keywords": ["seed rate", "kg", "acre", "quantity", "spacing", "row", "depth", "kitna beej",
                     "कितना बीज", "बीज दर", "ਬੀਜ", "line", "kataar", "कतार"],
        "text": (
            "Seed rate for timely sowing is about 100 kg per hectare, i.e. about 40 kg per acre. "
            "For late sowing increase it to about 125 kg per hectare (about 50 kg per acre) because late-sown "
            "plants make fewer tillers. Keep row-to-row spacing about 20 cm for timely sowing and about 18 cm for "
            "late sowing. Sow 4 to 5 cm deep with a seed drill for even germination. 1 acre is about 0.4 hectare."
        ),
    },
    {
        "id": "KB-04",
        "title": "Seed treatment",
        "stages": ["pre_sowing"],
        "keywords": ["seed treatment", "treat", "upchar", "बीज उपचार", "beej upchar", "smut", "kangiyari",
                     "कांगियारी", "termite", "deemak", "दीमक", "ਸਿਉਂਕ"],
        "text": (
            "Treat seed before sowing to prevent seed-borne diseases such as loose smut and to protect "
            "seedlings from termites in fields where termites are a problem. Use a fungicide seed treatment "
            "recommended for wheat (for example products based on carboxin or tebuconazole) and, where needed, "
            "a recommended insecticide seed treatment. Follow the dose and method printed on the product label "
            "or advised by the KVK, dry the seed in shade, and sow the same day. Wear gloves while treating seed."
        ),
    },
    {
        "id": "KB-05",
        "title": "Paddy stubble management before wheat",
        "stages": ["pre_sowing"],
        "keywords": ["stubble", "parali", "पराली", "ਪਰਾਲੀ", "burn", "burning", "jalana", "जलाना", "residue",
                     "happy seeder", "super seeder", "decomposer", "zero till", "straw", "naal", "नाड़"],
        "text": (
            "Do not burn paddy straw. Burning is banned, is a major cause of winter air pollution in Delhi NCR, "
            "and destroys soil organic matter and useful soil organisms. Wheat can be sown directly into standing "
            "stubble with a Happy Seeder, Super Seeder or zero-till drill, or the straw can be incorporated or "
            "treated with a microbial decomposer such as the PUSA decomposer. Crop-residue machines are available "
            "on subsidy and through custom hiring centres; ask the agriculture department or KVK. Straw left as "
            "mulch also conserves soil moisture and suppresses Phalaris minor weed."
        ),
    },
    {
        "id": "KB-06",
        "title": "Field preparation and pre-sowing irrigation",
        "stages": ["pre_sowing"],
        "keywords": ["field preparation", "tillage", "plough", "jutai", "जुताई", "palewa", "पलेवा",
                     "rauni", "ਰੌਣੀ", "moisture", "vattar", "वत्तर", "ਵੱਤਰ", "laser", "levelling"],
        "text": (
            "Give a pre-sowing irrigation (palewa / rauni) if the soil is dry, and sow when the soil reaches "
            "proper moisture (vattar): moist enough to form a ball but not sticky. Laser land levelling gives "
            "even irrigation and saves water. Where conventional tillage is used, prepare a fine but firm seedbed; "
            "zero tillage after rice saves time, diesel and water."
        ),
    },
    {
        "id": "KB-07",
        "title": "Fertiliser (nutrient) management",
        "stages": ["pre_sowing", "germination", "seedling", "cri", "tillering"],
        "keywords": ["fertilizer", "fertiliser", "urea", "dap", "khad", "खाद", "ਖਾਦ", "nitrogen", "npk",
                     "potash", "zinc", "yuria", "यूरिया", "dose", "top dressing", "soil test"],
        "text": (
            "General recommendation for timely sown irrigated wheat in this zone is about 150 kg nitrogen (N), "
            "60 kg phosphorus (P2O5) and 40 kg potash (K2O) per hectare, which is about 60 kg N, 24 kg P2O5 and "
            "16 kg K2O per acre. Adjust using your Soil Health Card. Apply all phosphorus and potash and about "
            "half the nitrogen at sowing; apply the remaining nitrogen in split doses with the first irrigation "
            "(crown root initiation, about 21 days after sowing) and, where recommended, the second irrigation. "
            "Apply urea just before irrigation on moist soil, not before heavy rain. Apply zinc sulphate only if "
            "the soil test shows zinc deficiency. Ask the KVK to convert nutrients into bags of urea/DAP for your field."
        ),
    },
    {
        "id": "KB-08",
        "title": "Irrigation at critical growth stages",
        "stages": ["germination", "seedling", "cri", "tillering", "jointing", "booting", "heading", "milk", "dough"],
        "keywords": ["irrigation", "irrigate", "water", "pani", "पानी", "sinchai", "सिंचाई", "ਪਾਣੀ", "ਸਿੰਚਾਈ",
                     "CRI", "crown root", "when to water", "kab pani"],
        "text": (
            "Wheat normally needs 4 to 6 irrigations depending on soil and winter rain. Critical stages and "
            "approximate days after sowing (DAS): crown root initiation (CRI) 20-25 DAS, the most critical; "
            "tillering 40-45 DAS; jointing 60-65 DAS; flowering 80-85 DAS; milk stage 100-105 DAS; dough stage "
            "115-120 DAS. If water is limited, never miss the CRI irrigation, then prioritise flowering and "
            "jointing. Light soils need more frequent, lighter irrigations. Skip or delay irrigation when good "
            "rain is forecast. At later stages avoid irrigating when strong wind is expected, to prevent lodging."
        ),
    },
    {
        "id": "KB-09",
        "title": "Weed management (Phalaris minor and broadleaf weeds; खरपतवार / ਨਦੀਨ)",
        "stages": ["seedling", "cri", "tillering"],
        "keywords": ["weed", "weeds", "kharpatwar", "खरपतवार", "ਨਦੀਨ", "gulli danda", "गुल्ली डंडा",
                     "mandusi", "ਗੁੱਲੀ ਡੰਡਾ", "phalaris", "bathua", "बथुआ", "herbicide", "weedicide", "nadeen"],
        "text": (
            "Phalaris minor (gulli danda / mandusi / kanki) is the main grassy weed of wheat in rice-wheat areas; "
            "broadleaf weeds include bathua, maina and wild pea. Post-emergence herbicides are usually applied "
            "about 30-35 days after sowing, after the first irrigation, when weeds have 2-4 leaves. Phalaris has "
            "developed resistance to some herbicides, so rotate herbicides with different modes of action and do "
            "not use the same product year after year. Use only herbicides recommended for wheat, at the dose on "
            "the label, with a flat-fan nozzle and the recommended water volume; do not spray in wind or before "
            "rain. Zero tillage and residue mulch reduce Phalaris emergence."
        ),
    },
    {
        "id": "KB-10",
        "title": "Yellow (stripe) rust (पीला रतुआ / ਪੀਲੀ ਕੁੰਗੀ)",
        "stages": ["tillering", "jointing", "booting", "heading"],
        "keywords": ["yellow rust", "stripe rust", "peela ratua", "पीला रतुआ", "ਪੀਲੀ ਕੁੰਗੀ", "peeli kungi",
                     "rust", "ratua", "रतुआ", "yellow powder", "peela", "पीला", "yellow stripes", "kungi"],
        "text": (
            "Yellow rust shows as bright yellow to orange powdery pustules arranged in stripes along the leaf "
            "veins; the powder comes off on fingers or a white cloth when an AFFECTED (striped) leaf is rubbed. It appears from "
            "mid-December to February in cool (about 10-15 °C), humid weather with dew or light rain, first in "
            "foothill districts such as Gurdaspur, Pathankot, Hoshiarpur, Ropar, Yamunanagar and Ambala, often near "
            "tree lines. Scout fields weekly from December. On first appearance spray a fungicide recommended for "
            "wheat rust (for example propiconazole- or tebuconazole-based products) at the label dose, as advised "
            "by the KVK; repeat only if advised. Grow resistant varieties. Do not confuse it with yellowing from "
            "nutrient deficiency, which has no powder."
        ),
    },
    {
        "id": "KB-11",
        "title": "Brown (leaf) rust (भूरा रतुआ / ਭੂਰੀ ਕੁੰਗੀ)",
        "stages": ["jointing", "booting", "heading", "milk"],
        "keywords": ["brown rust", "leaf rust", "bhura ratua", "भूरा रतुआ", "ਭੂਰੀ ਕੁੰਗੀ", "orange", "rust",
                     "ratua", "रतुआ", "kungi"],
        "text": (
            "Brown rust shows as small, round, orange-brown powdery pustules scattered irregularly on leaves (not "
            "in stripes). It is favoured by moderate temperatures of about 15-25 °C with moisture, usually from "
            "February to March. Management is similar to yellow rust: resistant varieties, regular scouting, and a "
            "recommended rust fungicide at the label dose when the disease appears, as advised by the KVK."
        ),
    },
    {
        "id": "KB-12",
        "title": "Loose smut (कांगियारी / ਕਾਂਗਿਆਰੀ)",
        "stages": ["heading"],
        "keywords": ["loose smut", "kangiyari", "कांगियारी", "ਕਾਂਗਿਆਰੀ", "black ear", "kali bali", "काली बाली",
                     "black powder", "smut"],
        "text": (
            "In loose smut the ear (bali) emerges as a mass of black powder instead of grains; the powder blows away "
            "leaving a bare stalk. The fungus lives inside the seed, so the real control is using certified, "
            "treated seed next season. Carefully pull out infected plants early in the morning, covering the ear "
            "with a bag so spores do not spread, and destroy them. Do not keep seed from an infected field."
        ),
    },
    {
        "id": "KB-13",
        "title": "Karnal bunt (करनाल बंट / ਕਰਨਾਲ ਬੰਟ)",
        "stages": ["heading", "milk", "dough", "maturity"],
        "keywords": ["karnal bunt", "bunt", "fishy smell", "machhli", "मछली जैसी गंध", "black grain",
                     "kala dana", "काला दाना", "ਕਰਨਾਲ ਬੰਟ"],
        "text": (
            "Karnal bunt partly converts grains into black powdery masses with a fishy smell; usually only some "
            "grains in an ear are affected, so it is often noticed only after harvest. Cloudy, humid or rainy "
            "weather at heading favours infection. It matters for quality and export (quarantine) rules. Use "
            "certified seed, avoid excess nitrogen, and follow any local advisory for a preventive spray at "
            "heading. Report suspected cases to the KVK or agriculture officer."
        ),
    },
    {
        "id": "KB-14",
        "title": "Powdery mildew (चूर्णिल आसिता / ਚਿੱਟਾ ਰੋਗ)",
        "stages": ["tillering", "jointing", "booting", "heading"],
        "keywords": ["powdery mildew", "white powder", "safed", "सफेद चूर्ण", "chitta", "ਚਿੱਟਾ",
                     "mildew", "safed rog"],
        "text": (
            "Powdery mildew appears as white to greyish cottony, powdery patches on leaves and sheaths, later with "
            "small black dots. It is favoured by cool, humid weather and dense crops with high nitrogen, and is "
            "more common in sub-mountain areas. Use resistant varieties and balanced nitrogen; spray only on "
            "KVK advice using a recommended fungicide at the label dose."
        ),
    },
    {
        "id": "KB-15",
        "title": "Termites (दीमक / ਸਿਉਂਕ)",
        "stages": ["germination", "seedling", "cri", "tillering", "maturity"],
        "keywords": ["termite", "termites", "deemak", "दीमक", "ਸਿਉਂਕ", "siunk", "plants drying", "sookh",
                     "सूख", "roots eaten"],
        "text": (
            "Termites eat roots and the underground stem; affected plants dry up in patches and pull out easily. "
            "They are more common in light/sandy soils, rainfed fields and where undecomposed farmyard manure is "
            "used. Prevention: use only well-decomposed FYM, treat seed where termites are a known problem, and "
            "irrigate on time since dry soil favours termites. For a standing-crop attack, take KVK advice before "
            "any soil application."
        ),
    },
    {
        "id": "KB-16",
        "title": "Aphids (तेला, चेपा / ਚੇਪਾ)",
        "stages": ["booting", "heading", "milk"],
        "keywords": ["aphid", "aphids", "tela", "तेला", "chepa", "चेपा", "ਚੇਪਾ", "insects on ear",
                     "keede", "कीड़े", "ਕੀੜੇ", "honeydew", "sticky"],
        "text": (
            "Aphids (tela / chepa) are small soft insects that suck sap from leaves and ears from January to March, "
            "leaving a sticky layer. Ladybird beetles and other natural enemies usually keep them in check. Spray "
            "an insecticide only when aphid numbers cross the economic threshold advised locally, and only with a "
            "product recommended for wheat at the label dose; avoid unnecessary sprays that kill natural enemies."
        ),
    },
    {
        "id": "KB-17",
        "title": "Pink stem borer and armyworm in residue-retained fields",
        "stages": ["germination", "seedling", "cri", "tillering"],
        "keywords": ["stem borer", "pink borer", "tana chedak", "तना छेदक", "ਗੁਲਾਬੀ ਸੁੰਡੀ", "sundi", "सुंडी",
                     "armyworm", "caterpillar", "dead heart", "central shoot dry"],
        "text": (
            "In early-sown wheat sown into rice residue, pink stem borer larvae can bore into young shoots, causing "
            "'dead hearts' (the central shoot dries and pulls out easily); armyworm caterpillars may feed on "
            "leaves. Monitor fields in the first 6-8 weeks, especially near previous rice fields. Light damage is "
            "usually compensated by tillering; if damage is widespread, contact the KVK for a recommended control."
        ),
    },
    {
        "id": "KB-18",
        "title": "Terminal heat stress at grain filling",
        "stages": ["heading", "milk", "dough"],
        "keywords": ["heat", "garmi", "गर्मी", "ਗਰਮੀ", "temperature", "hot", "shrivel", "grain filling",
                     "dana", "दाना", "march", "loo"],
        "text": (
            "Day temperatures above about 32 °C during grain filling (usually March) shorten the grain-filling "
            "period and produce small, shrivelled grains; above about 35 °C the damage is severe. Timely sowing "
            "is the best protection. When heat is forecast, give a light irrigation, preferably in the evening, "
            "so the crop is not under water stress, but avoid irrigating when strong wind is expected. Follow any "
            "KVK advisory on foliar sprays for heat stress."
        ),
    },
    {
        "id": "KB-19",
        "title": "Frost and cold waves (पाला / ਕੋਰਾ)",
        "stages": ["seedling", "cri", "tillering", "jointing", "booting", "heading"],
        "keywords": ["frost", "pala", "पाला", "ਕੋਰਾ", "kora", "cold", "thand", "ठंड", "shit leher", "शीतलहर"],
        "text": (
            "Frost can occur on clear, calm nights in late December and January when the minimum temperature falls "
            "near 0-2 °C; it is most harmful at heading and flowering. A light irrigation in the evening when frost "
            "is forecast keeps the field warmer. Moist soil holds heat better than dry soil."
        ),
    },
    {
        "id": "KB-20",
        "title": "Lodging (crop falling over)",
        "stages": ["booting", "heading", "milk", "dough"],
        "keywords": ["lodging", "girna", "गिरना", "fall", "ਡਿੱਗਣਾ", "wind", "hawa", "हवा", "leta", "bichh gayi"],
        "text": (
            "Lodging (the crop falling flat) happens when heavy irrigation or rain is followed by strong wind at "
            "later stages, and is worse with excess nitrogen and tall varieties. Avoid irrigating when strong wind "
            "is forecast, do not over-apply nitrogen, and choose varieties with strong straw."
        ),
    },
    {
        "id": "KB-21",
        "title": "Yellowing from nutrient deficiency (look-alikes of rust)",
        "stages": ["seedling", "cri", "tillering", "jointing"],
        "keywords": ["yellow", "yellowing", "peela", "पीला", "पीलापन", "ਪੀਲਾ", "deficiency", "kami", "कमी",
                     "nitrogen", "zinc", "manganese", "leaves yellow", "patte peele", "पत्ते पीले"],
        "text": (
            "Not all yellow leaves are rust. Nitrogen deficiency: older (lower) leaves turn uniformly pale yellow "
            "starting from the tip, and the whole crop looks light green. Zinc deficiency: early in the season, "
            "leaves show pale streaks or bronzing in the middle of the leaf and growth is stunted. Manganese "
            "deficiency (common on light soils after rice): grey-yellow spots and streaks between veins on middle "
            "leaves. Waterlogging after heavy irrigation or rain also causes yellowing. Rub the leaf: rust leaves "
            "yellow/orange powder on the finger, deficiency does not (always rub an affected leaf, not a healthy one). "
            "Confirm with a soil test or the KVK."
        ),
    },
    {
        "id": "KB-22",
        "title": "Harvesting and storage",
        "stages": ["dough", "maturity"],
        "keywords": ["harvest", "katai", "कटाई", "ਕਟਾਈ", "combine", "storage", "bhandaran", "भंडारण",
                     "moisture", "nami", "नमी", "store", "godown", "ripe", "pakna"],
        "text": (
            "Harvest when the grains are hard and the straw has turned golden and dry, usually in April in this "
            "zone. Dry the grain well; store only when grain moisture is about 12% or less. Clean and dry the "
            "storage bins or godown before storing, keep bags on wooden pallets away from walls, and use only "
            "recommended storage protectants. Collect and use straw (bhusa) rather than burning wheat stubble."
        ),
    },
    {
        "id": "KB-23",
        "title": "Human help, helplines and schemes",
        "stages": ["pre_sowing", "germination", "seedling", "cri", "tillering", "jointing", "booting",
                   "heading", "milk", "dough", "maturity"],
        "keywords": ["helpline", "call", "human", "officer", "expert", "KVK", "kisan call centre", "KCC",
                     "scheme", "yojana", "योजना", "insurance", "bima", "बीमा", "PMFBY", "soil health card",
                     "madad", "मदद", "ਮਦਦ", "salah", "सलाह"],
        "text": (
            "Kisan Call Centre (KCC): toll-free 1800-180-1551, answers in local languages. Every district has a "
            "Krishi Vigyan Kendra (KVK) with scientists who can visit fields and confirm diagnoses. The state "
            "agriculture department and agriculture development officers give local advisories. Useful schemes: "
            "Soil Health Card (soil testing), Pradhan Mantri Fasal Bima Yojana (crop insurance; enrol through your "
            "bank, CSC or the PMFBY portal before the season's cut-off date), and subsidy on crop-residue machines."
        ),
    },
    {
        "id": "KB-24",
        "title": "Market prices and MSP (outside the bot's scope)",
        "stages": ["maturity"],
        "keywords": ["price", "rate", "mandi", "मंडी", "ਮੰਡੀ", "msp", "bhav", "भाव", "sell", "bechna",
                     "बेचना", "market", "procurement", "kharid", "खरीद"],
        "text": (
            "GehunGuru does not give live market prices. The Government of India announces the wheat Minimum "
            "Support Price (MSP) each year before the rabi season. For current mandi rates check Agmarknet "
            "(agmarknet.gov.in) or e-NAM (enam.gov.in), or ask the local mandi / procurement agency."
        ),
    },
]

KB_BY_ID = {e["id"]: e for e in KB}
VALID_IDS = set(KB_BY_ID)


def kb_as_prompt_text(entries: Iterable[dict] | None = None) -> str:
    """Render the knowledge base as compact text for the system prompt."""
    entries = list(entries) if entries is not None else KB
    lines = []
    for e in entries:
        lines.append(f"[{e['id']}] {e['title']} (stages: {', '.join(e['stages'])})\n{e['text']}")
    return "\n\n".join(lines)


_TOKEN = re.compile(r"[\w\u0900-\u097F\u0A00-\u0A7F]+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN.findall(text or "") if len(t) > 1}


def search(query: str, stage_key: str | None = None, k: int = 2) -> list[dict]:
    """Keyword search used ONLY as the offline fallback when Gemini is unavailable.

    Scores: +3 for every keyword phrase found in the query, +1 per shared word
    with the title/text, +1 if the entry matches the current crop stage.
    """
    q = (query or "").lower()
    q_tokens = _tokens(q)
    scored = []
    for e in KB:
        score = 0.0
        for kw in e["keywords"]:
            if kw.lower() in q:
                score += 3
        score += 0.5 * len(q_tokens & _tokens(e["title"] + " " + e["text"]))
        if stage_key and stage_key in e["stages"]:
            score += 1
        scored.append((score, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for s, e in scored[:k] if s >= 3]


def clean_sources(ids: Iterable[str]) -> list[str]:
    """Keep only citations that really exist (drops hallucinated ids like KB-99)."""
    out = []
    for i in ids or []:
        i = str(i).strip().upper().strip("[]")
        if i in VALID_IDS and i not in out:
            out.append(i)
    return out


def select_for(query: str, stage_key: str | None, limit: int = 9) -> list[dict]:
    """Retrieval for the backup provider, whose free tier has small token limits.

    Order: keyword matches for the question, then entries for the current crop stage, then the
    helpline and out-of-scope entries (always useful). Gemini gets the whole knowledge base instead.
    """
    picked: list[dict] = []
    for e in search(query, stage_key, k=4) + [e for e in KB if stage_key in e["stages"]] + \
            [KB_BY_ID["KB-23"], KB_BY_ID["KB-24"]]:
        if e not in picked:
            picked.append(e)
    keep = picked[:limit - 2] + [x for x in picked[-2:] if x not in picked[:limit - 2]]
    return sorted(keep, key=lambda e: e["id"])

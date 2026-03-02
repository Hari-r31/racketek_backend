#!/usr/bin/env python3
"""
seed_data.py — Full catalogue seed
  10 sports (parent categories)
  10 sub-categories per sport (100 total)
  10 products per sport with 2-4 real images uploaded to Cloudinary (100 total)

Usage (from /backend directory):
  python seed_data.py

Prerequisites:
  • .env file with DATABASE_URL, CLOUDINARY_CLOUD_NAME/KEY/SECRET
  • pip install python-dotenv cloudinary sqlalchemy
"""

import os, sys, re, time, random, hashlib, urllib.request, traceback
from pathlib import Path

# ── bootstrap env & path ─────────────────────────────────────────────────────
load_env_path = Path(__file__).parent / ".env"
if load_env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(load_env_path)

sys.path.insert(0, str(Path(__file__).parent))

from app.db.session import SessionLocal
from app.models.category import Category
from app.models.product import Product, ProductImage, ProductVariant, ProductStatus
from app.utils.cloudinary_util import upload_image, configure_cloudinary


# ════════════════════════════════════════════════════════════════════════════
# CATALOGUE DATA
# ════════════════════════════════════════════════════════════════════════════

SPORTS = [
    ("badminton",    "Badminton",    "Rackets, footwear, shuttles & bags for every level"),
    ("cricket",      "Cricket",      "Bats, pads, gloves, helmets & all cricket gear"),
    ("tennis",       "Tennis",       "Rackets, strings, shoes & court accessories"),
    ("football",     "Football",     "Boots, balls, jerseys & training equipment"),
    ("swimming",     "Swimming",     "Goggles, swimwear, caps & training aids"),
    ("running",      "Running",      "Shoes, apparel, GPS watches & hydration"),
    ("fitness",      "Fitness",      "Dumbbells, bands, yoga mats & home gym gear"),
    ("table-tennis", "Table Tennis", "Blades, rubbers, balls & tables"),
    ("basketball",   "Basketball",   "Balls, shoes, jerseys & protective gear"),
    ("cycling",      "Cycling",      "Helmets, jerseys, shoes & accessories"),
]

SUBS = {
    "badminton":    ["Rackets","Shuttlecocks","Shoes","Bags","Strings","Grips","Apparel","Nets","Court Mats","Accessories"],
    "cricket":      ["Bats","Pads","Gloves","Helmets","Balls","Shoes","Bags","Apparel","Training Aids","Accessories"],
    "tennis":       ["Rackets","Balls","Shoes","Bags","Strings","Grips","Apparel","Overgrips","Court Accessories","Accessories"],
    "football":     ["Boots","Balls","Jerseys","Shorts","Goalkeeper Gear","Shin Guards","Bags","Training Cones","Socks","Accessories"],
    "swimming":     ["Goggles","Swimwear","Caps","Kickboards","Pull Buoys","Training Fins","Earplugs","Bags","Towels","Accessories"],
    "running":      ["Shoes","Socks","Shorts","Compression Tights","Tops","Jackets","GPS Watches","Hydration","Headbands","Accessories"],
    "fitness":      ["Dumbbells","Resistance Bands","Yoga Mats","Kettlebells","Pull-up Bars","Foam Rollers","Jump Ropes","Benches","Gloves","Accessories"],
    "table-tennis": ["Blades","Rubbers","Balls","Tables","Nets","Shoes","Bags","Apparel","Robot Trainers","Accessories"],
    "basketball":   ["Balls","Shoes","Jerseys","Shorts","Compression","Ankle Braces","Bags","Training Hoops","Socks","Accessories"],
    "cycling":      ["Helmets","Jerseys","Shorts","Gloves","Shoes","Lights","Bags","Water Bottles","GPS Computers","Accessories"],
}

# (name, brand, price, compare_price, stock, description, short_desc, is_featured, is_best_seller)
PRODUCTS = {
    "badminton": [
        ("Yonex Astrox 99 Pro",          "Yonex",    12999, 15999, 50, "Head-heavy balance with ROTATIONAL GENERATOR SYSTEM for explosive attack power on every smash.", "Explosive attack racket",     True,  True),
        ("Victor Thruster K 9900",        "Victor",    9999, 12500, 30, "Premium carbon-fiber racket built for advanced smash players requiring maximum power transfer.",    "Pro-level smash racket",      False, True),
        ("Li-Ning N99 Mark IV",           "Li-Ning",  14500, 17000, 20, "Ultra-stiff shaft engineered for world-class power. Used by international champions.",             "World championship racket",   True,  False),
        ("Yonex Aerus Z Court Shoes",     "Yonex",     7499,  9999, 60, "Weighing just 235g — Yonex's lightest badminton shoe with Power Cushion absorption.",             "Featherweight court shoes",   False, True),
        ("Victor SH A960 CF Shoes",       "Victor",    5999,  7499, 45, "Carbon fiber outsole with hexagonal anti-slip traction and Energymax foam midsole.",              "Anti-slip carbon shoes",      False, False),
        ("Yonex Mavis 350 Nylon 6-pack",  "Yonex",      799,   999, 200, "Durable nylon shuttlecock recommended for club training — consistent flight in all conditions.",  "Durable training shuttle",    False, False),
        ("Victor BG80 Badminton String",  "Victor",     599,   749, 150, "High repulsion + sharp touch for players who demand control. 0.68mm gauge.",                     "High-repulsion string",       False, False),
        ("Yonex BA82226EX Tournament Bag","Yonex",     3499,  4499, 40, "6-racket thermal-lined tournament bag with separate shoe compartment and wet pocket.",            "6-racket tournament bag",     False, True),
        ("Ashaway Zymax 66 Fire String",  "Ashaway",    699,   899, 120, "Ultra-thin 0.66mm fire-coated string delivering explosive repulsion and crisp feel.",            "0.66mm power string",         False, False),
        ("Victor Towel Grip 3-pack",      "Victor",      99,   149, 500, "Super-absorbent textured towel grip — eliminate slippage in intense rallies. Pack of 3.",        "Absorbent towel grip pack",   False, False),
    ],
    "cricket": [
        ("SG Savage Edition Bat",         "SG",        6999,  8999, 35, "English willow Grade 1 — thick edges, full spine profile engineered for power hitters.",          "Grade 1 English willow bat",  True,  True),
        ("Kookaburra Kahuna 10.1 Bat",    "Kookaburra",8499, 10500, 20, "Premium Kashmir willow with reinforced toe protection and pre-knocked profile.",                  "Premium KW bat",              False, True),
        ("SS Ton Reserve Edition Bat",    "SS",         5499,  6999, 40, "Tournament-level English willow with multi-layer binding and concave face.",                     "Tournament English willow",   True,  False),
        ("Masuri Vision Series Helmet",   "Masuri",    4999,  6499, 25, "BSI 11624:2015 certified. Adjustable steel grille, moisture-wicking lining.",                    "BSI certified cricket helmet",False, True),
        ("SG Club Cricket Ball Red",      "SG",          399,   549, 200, "5.5 oz BCCI approved red leather ball — perfect seam, consistent swing.",                       "BCCI approved leather ball",  False, False),
        ("Adidas Adipower 2.0 Shoes",     "Adidas",    4299,  5499, 55, "Lightweight rubber spikes with anti-skid grip and padded ankle collar.",                          "Lightweight cricket spikes",  False, False),
        ("GM Prima 808 Batting Gloves",   "GM",         2199,  2799, 60, "Clarino palm, PU back with contoured finger rolls for maximum bat control.",                     "Premium batting gloves",      False, True),
        ("Kookaburra Pro 2.5 Wheelie Bag","Kookaburra",3699,  4799, 30, "Roller bag with dual bat sleeves, separate shoe bay and document pocket.",                       "Pro cricket wheelie bag",     False, False),
        ("DSP Thigh Guard Pro",           "DSP",         899,  1299, 80, "Impact-resistant thigh guard with mesh ventilation channels and adjustable straps.",             "Impact-resistant thigh guard",False, False),
        ("Dukes SLA County Ball",         "Dukes",       449,   599, 180, "Premium hand-stitched county-grade leather ball — consistent line, length and bounce.",         "Hand-stitched county ball",   False, False),
    ],
    "tennis": [
        ("Wilson Blade 98 V8 Racket",     "Wilson",   14999, 17999, 20, "16x19 string pattern, carbon-fiber braiding delivers benchmark feel, control and spin.",          "Control benchmark racket",    True,  True),
        ("Babolat Pure Drive 2023",       "Babolat",  12499, 15000, 25, "Woofer grommets + HTR System — used by top ATP/WTA players demanding power and spin.",            "Power & spin racket",         False, True),
        ("Head Gravity MP 2023",          "Head",     13999, 16500, 15, "Graphene 360+ distributes energy from baseline to net with precision dampening.",                 "All-court precision racket",  True,  False),
        ("Nike Zoom Vapor Pro 2",         "Nike",      8999, 10999, 40, "Full-length Zoom Air unit, durable herringbone outsole for aggressive court play.",               "Zoom Air court shoe",         False, True),
        ("Wilson Clash 100 V2 Racket",    "Wilson",   10499, 12999, 18, "Patented StableSmart frame — ultra-flexible for effortless power on every swing.",               "Ultra-flexible power frame",  False, False),
        ("Babolat RPM Blast 200m Reel",   "Babolat",   2999,  3499, 80, "Octagonal polyester co-poly string — the benchmark for topspin and durability on tour.",         "Topspin benchmark string",    False, False),
        ("Wilson US Open Extra Duty 4pk", "Wilson",     699,   899, 150, "Extra-duty felt hard court ball approved for US Open — consistent bounce and durability.",       "Hard court tennis balls",     False, False),
        ("Babolat 6-Racket Team Bag",     "Babolat",   3299,  4199, 45, "3-compartment thermobag fits 6 rackets + shoes with ventilated wet pocket.",                     "6-racket thermobag",          False, True),
        ("Solinco Hyper G 17g 200m",      "Solinco",   2799,  3299, 60, "Square co-poly polyester — delivers maximum spin with tour-level durability.",                   "Tour-grade spin string",      False, False),
        ("Tourna Mega Tac Overgrip 30pk", "Tourna",     699,   899, 200, "Tacky, dry feel overgrip — preferred by professionals for maximum handle control.",              "Tacky overgrip 30-pack",      False, False),
    ],
    "football": [
        ("Nike Phantom GX Elite FG",      "Nike",     15999, 19999, 20, "FlyKnit upper with Grip Zone texture — unmatched first-touch and close ball control.",           "Elite FG football boots",     True,  True),
        ("Adidas Predator Accuracy+ FG",  "Adidas",   14999, 18000, 15, "Controlframe outsole + Zonesskin rubber zones for lethal passing and shooting accuracy.",        "Accuracy+ FG boots",          False, True),
        ("Puma Future 7 Ultimate FG",     "Puma",     12499, 15500, 22, "FUZIONFIT+ upper adapts to foot shape — superior lockdown without pressure points.",              "Adaptive fit boots",          False, False),
        ("Nike Premier League Flight Ball","Nike",      2999,  3999, 100, "FIFA Quality Pro — Aerow grooves for accurate true-flight in all weather conditions.",          "FIFA Quality Pro ball",       False, True),
        ("Adidas Condivo 22 Jersey",      "Adidas",    1499,  1999, 120, "Aeroready moisture-wicking polyester — slim club-cut fit for maximum mobility.",                "Aeroready club jersey",       False, False),
        ("Sells Silhouette Pro GK Glove", "Sells",     2999,  3799, 40, "NC Flat cut palm with Sells contact latex — professional grip in all conditions.",               "Pro goalkeeper gloves",       False, False),
        ("Nike Mercurial Lite Shin Guard","Nike",        499,   699, 200, "Lightweight anatomical PE/EVA guard with integrated compression sleeve.",                       "Lightweight shin guards",     False, False),
        ("Hummel Elite Football Bag",     "Hummel",    2499,  3199, 55, "Spacious main compartment, ball net holder, and ventilated cleats pocket.",                      "Elite football bag",          False, True),
        ("Under Armour Crew Sock 3-pack", "Under Armour",499,   699, 300, "Anti-blister Arch Lock construction — pack of 3 pairs.",                                       "Anti-blister crew socks 3pk", False, False),
        ("Adidas Tiro 23 Training Short", "Adidas",     999,  1399, 150, "Aeroready woven shorts — slim cut, flatlock seams, small zip pocket.",                          "Aeroready training shorts",   False, False),
    ],
    "swimming": [
        ("Speedo Fastskin Pure Focus",    "Speedo",    2999,  3999, 60, "IQfit gasket sealing system — ultra-low profile racing goggle approved for competition.",        "IQfit racing goggles",        True,  True),
        ("Arena Cobra Ultra Mirrored",    "Arena",     3499,  4499, 45, "Anti-scratch mirrored lens with dual-density Ultra-soft gasket — zero water entry.",             "Mirrored racing goggles",     False, True),
        ("Speedo Endurance+ Jammer",      "Speedo",    2299,  2999, 80, "Polyester/PBT chlorine-resistant jammer — maintains shape after 200+ hours in the pool.",        "Chlorine-resistant jammer",   False, False),
        ("TYR Hurricane Category 5 Suit", "TYR",       3999,  4999, 30, "Lightweight polyester swim-skin designed for triathletes and open-water swimmers.",              "Triathlete swim-skin",        False, True),
        ("Speedo Long Life Silicone Cap", "Speedo",      399,   549, 200, "Moulded silicone — wrinkle-free fit that reduces drag vs latex caps.",                          "Long-life silicone cap",      False, False),
        ("Finis Axis Aquatic Kickboard",  "Finis",     1199,  1599, 70, "Streamlined short board — targets core and legs without hunching the spine.",                    "Core training kickboard",     False, False),
        ("Speedo Biofuse Earplugs",       "Speedo",      299,   399, 300, "Medical-grade soft silicone — flexible custom-fit reduces water ingress.",                      "Medical-grade earplugs",      False, False),
        ("Zoggs Predator Flex Goggle",    "Zoggs",     1699,  2199, 55, "Flexiseal frame conforms to any face shape — tri-lens UV protection.",                           "Flexiseal training goggles",  False, True),
        ("Arena Powerskin R-EVO Open",    "Arena",     4499,  5999, 25, "FINA-approved 100 percent polyester race suit — suits all stroke disciplines.",                  "FINA approved race suit",     False, False),
        ("Speedo Squad Kit Bag 35L",      "Speedo",    1999,  2699, 50, "Tarpaulin base, large mesh wet pocket, and a zip valuables pouch — 35L capacity.",               "Waterproof 35L swim bag",     False, False),
    ],
    "running": [
        ("Nike Air Zoom Pegasus 41",      "Nike",      9499, 11499, 80, "React foam + forefoot Zoom Air — versatile everyday trainer for easy days and tempo runs.",      "Versatile daily trainer",     True,  True),
        ("ASICS Gel-Nimbus 26",           "ASICS",    12999, 15999, 40, "PureGEL technology + FF BLAST+ midsole — maximum plush cushioning for long runs.",               "Plush long-run shoe",         False, True),
        ("Brooks Ghost 16",               "Brooks",   10999, 13499, 55, "BioMoGo DNA midsole adapts to weight, speed and gait — ideal for neutral runners.",              "Adaptive neutral trainer",    False, False),
        ("Garmin Forerunner 265",         "Garmin",   29999, 34999, 15, "AMOLED display, training readiness score, HRV status and suggested daily workouts.",             "Premium AMOLED running watch", True, True),
        ("2XU Compression Run Tights",    "2XU",       4499,  5999, 60, "Medical-grade 70 denier graduated compression — measurably reduces DOMS and fatigue.",           "Graduated compression tights",False, True),
        ("Nathan SpeedDraw Plus Flask",   "Nathan",    1499,  1999, 90, "310ml BPA-free handheld flask — ergonomic strap, storage pocket.",                               "Handheld hydration flask",    False, False),
        ("On Running Ultra-Shorts 5in",   "On",        2999,  3799, 75, "Technical 5-inch shorts with built-in liner and reflective details.",                            "Technical running shorts",    False, False),
        ("Balega Blister Resist Crew",    "Balega",     699,   899, 200, "Mohair blend with drynamix — proven anti-blister performance.",                                  "Anti-blister Mohair socks",   False, False),
        ("CEP Run Compression Socks",     "CEP",       1799,  2299, 110, "Anatomical graduated compression 15-20 mmHg — reduces cramping on long efforts.",               "Graduated compression socks", False, True),
        ("Polar Pacer Pro GPS Watch",     "Polar",    19999, 24999, 20, "Precision Prime GPS chip, wrist-based HR, training load and recovery status.",                   "Pro GPS running watch",       False, False),
    ],
    "fitness": [
        ("Boldfit Adjustable Dumbbell Set","Boldfit",  7499,  9999, 20, "Quick-lock selector adjusts from 2kg to 32kg in seconds — replaces 8 pairs.",                   "Adjustable 2 to 32kg pair",   True,  True),
        ("Thentic Resistance Bands 5-Pack","Thentic",   999,  1499, 150, "Latex-free progressive resistance 5–40lbs — 5 colour-coded levels included.",                  "5-level resistance bands",    False, True),
        ("Fittr Premium TPE Yoga Mat 6mm","Fittr",      799,  1199, 200, "Non-slip TPE surface — sweat-wicking, eco-friendly and 6mm for joint support.",                "Non-slip TPE yoga mat",       False, False),
        ("RIMSports 16kg Vinyl Kettlebell","RIMSports", 2499,  3299, 40, "Precision-cast iron with durable vinyl dip — smooth powder-coated swing handle.",               "16kg vinyl kettlebell",       False, True),
        ("Decathlon 20kg Dumbbell Set",   "Decathlon", 3999,  5499, 30, "Cast-iron fixed-weight set: 2x5kg, 2x7.5kg — hexagonal anti-roll design.",                      "20kg cast iron set",          False, False),
        ("Chrome High-Density Foam Roller","Chrome",   1299,  1799, 90, "45cm EPP foam — deep tissue myofascial release for IT bands and calves.",                       "High-density foam roller",    False, False),
        ("Decathlon Ball-Bearing Jump Rope","Decathlon",399,   599, 300, "Speed rope with precision ball-bearing handles — adjustable cable length.",                     "Ball-bearing speed rope",     False, False),
        ("Doorframe Pull-up Bar",         "Generic",   2199,  2999, 55, "Fits 60–100cm doorframes, no drilling required, rated to 150kg.",                               "No-drill pull-up bar",        False, False),
        ("Adidas Pro Weightlifting Gloves","Adidas",     999,  1399, 100, "Padded palm with integrated wrist-wrap — prevents blisters.",                                  "Padded weight gloves",        False, False),
        ("Boldfit 28L Gym Bag",           "Boldfit",   1499,  1999, 75, "Vented shoe compartment, wet pocket, padded laptop sleeve — 28L total.",                        "28L gym bag",                 False, True),
    ],
    "table-tennis": [
        ("Butterfly Timo Boll ALC Blade", "Butterfly", 9999, 12499, 20, "Arylate-Carbon fibre layers deliver fast, crisp touch — world-championship level.",             "ALC carbon blade",            True,  True),
        ("DHS Hurricane 3 Neo Rubber",    "DHS",         999,  1399, 80, "Chinese national team rubber — extra-tacky top sheet, hard sponge for topspin.",               "National team rubber",        False, True),
        ("Stiga Evolution ST Blade",      "Stiga",      3999,  4999, 35, "5-ply all-round blade — consistent dwell time, excellent for mid-distance loops.",               "All-round looper blade",      False, False),
        ("Yasaka Mark V Rubber",          "Yasaka",      899,  1199, 100, "Balanced speed and spin — classic intermediate rubber trusted in clubs worldwide.",             "Classic balanced rubber",     False, False),
        ("Nittaku Premium 3-Star Ball 3pk","Nittaku",    599,   799, 200, "ITTF-approved 40+ poly ball — perfectly round within 0.1mm. Pack of 3.",                       "ITTF 40+ poly balls x3",      False, True),
        ("Decathlon Foldable TT Table",   "Decathlon", 18999, 24999, 10, "Regulation 2.74x1.525m foldable indoor table — 16mm top, rollaway wheels.",                    "Regulation foldable table",   False, False),
        ("Butterfly Petr Korbel TT Shoe", "Butterfly",  4499,  5999, 40, "Hexagonal rubber outsole for multi-directional grip — lightweight at 285g.",                   "Lightweight TT shoe",         False, True),
        ("Nittaku Premium TT Bag",        "Nittaku",    1499,  1999, 60, "Full-length blade sleeve, 3-ball tube holder and accessory pocket.",                            "Full-length TT bag",          False, False),
        ("DHS Clip-On Table Net",         "DHS",         299,   449, 150, "Universal spring-clip net for regulation 15.25cm height — adjustable tension.",                "Clip-on regulation net",      False, False),
        ("Tibhar Evolution MX-P Rubber",  "Tibhar",     1199,  1599, 90, "Tensor technology catapult effect — high-speed elastic rubber loved by loopers.",               "Tensor catapult rubber",      False, False),
    ],
    "basketball": [
        ("Spalding NBA Official Game Ball","Spalding",  4999,  6499, 40, "Full-grain Horween leather — the official indoor game ball of the NBA since 1983.",              "Official NBA leather ball",   True,  True),
        ("Wilson Evolution Indoor Ball",   "Wilson",    3999,  4999, 55, "Cushion-Core carcass — composite leather cover for soft indoor feel.",                           "Indoor composite ball",       False, True),
        ("Nike Kyrie Infinity Low",        "Nike",      8999, 10999, 25, "Lightweight containment system for Kyrie Irving's unpredictable footwork.",                     "Kyrie signature low shoe",    False, False),
        ("Adidas Harden Stepback 4",       "Adidas",    7499,  9499, 30, "Lightweight mesh upper + full-length LIGHTMOTION cushioning for sharp cuts.",                   "Stepback cushioned shoe",     False, True),
        ("Under Armour Curry 11",          "Under Armour",11499,13999, 15,"UA Flow sole eliminates the midsole layer — direct court feel with full cushioning.",           "Curry 11 UA Flow shoe",       True,  False),
        ("Bodyprox Lace-Up Ankle Brace",   "Bodyprox",   799,  1099, 150, "Figure-8 stirrup strap — clinically proven to prevent lateral ankle sprains.",                 "Figure-8 ankle brace",        False, True),
        ("Nike Dri-FIT Elite Crew Socks",  "Nike",       699,   899, 200, "Dri-FIT targeted cushioning in forefoot and heel for basketball impact.",                      "Dri-FIT basketball socks",    False, False),
        ("Adidas Tiro 23 Game Short",      "Adidas",    1799,  2299, 120, "Aeroready mesh — flatlock seams, elastic waistband, regulation length.",                       "Aeroready game short",        False, False),
        ("Spalding Adjustable Hoop Set",   "Spalding",  12999, 16999, 10, "2.4–3.05m adjustable polycarbonate backboard — spring-action rim.",                            "Adjustable backboard",        False, False),
        ("UA Project Rock Gym Bag",        "Under Armour",3499, 4499, 35, "UA Storm fabric — fits full uniform, shoes and accessories.",                                   "UA Storm basketball bag",     False, False),
    ],
    "cycling": [
        ("Bell Stratus MIPS Road Helmet",  "Bell",      6999,  8999, 30, "20 optimised wind tunnels + MIPS brain protection — only 230g.",                                "20-vent MIPS road helmet",    True,  True),
        ("Giro Syntax MIPS Helmet",        "Giro",      7999, 10499, 20, "Roc Loc 5 fit system — 24 vents for maximum airflow and MIPS safety.",                           "Roc Loc 5 MIPS helmet",       False, True),
        ("Rapha Core Cycling Jersey",      "Rapha",     5499,  6999, 45, "Breathable polyester with full-length YKK zip and three rear pockets.",                         "Full-zip club jersey",        False, False),
        ("Shimano RC3 Road Shoes",         "Shimano",   6499,  8299, 35, "BOA IP1 dial closure, carbon-reinforced sole, 3-bolt cleat compatibility.",                      "BOA dial road shoes",         False, True),
        ("Garmin Edge 530 GPS Computer",   "Garmin",   21999, 26999, 12, "Mapping, ClimbPro ascent planner, power guide and smart trainer control.",                       "Mapping cycling computer",    True,  False),
        ("Castelli Velocissimo Bib Short", "Castelli",  8999, 11499, 25, "Free Aero Race 4 chamois pad — 8-panel aerodynamic construction.",                               "Aero race bib shorts",        False, True),
        ("Elite Custom Race Bottle 750ml", "Elite",      699,   899, 200, "Easy-flow cap, grip ribs, squeezable BPA-free body — 750ml.",                                   "Race water bottle 750ml",     False, False),
        ("Castelli Perfetto ROS Jacket",   "Castelli",  7999, 10499, 20, "Repel + stretch softshell — wind and water resistant.",                                          "Wind-rain jacket",            False, False),
        ("Exposure Trace USB-C Rear Light","Exposure",  3499,  4499, 40, "100 lumen rechargeable rear light — 15h runtime from 2.5h charge.",                             "USB-C rechargeable rear light",False, False),
        ("Ortlieb Back-Roller City 40L",   "Ortlieb",   7999, 10499, 18, "IP64 waterproof pannier pair — 40+20L, fits all standard rear racks.",                           "Waterproof 40L panniers",     False, True),
    ],
}

IMAGES = {
    "badminton":    [
        "https://images.unsplash.com/photo-1626224583764-f87db24ac4ea?w=900&q=85",
        "https://images.unsplash.com/photo-1613918431703-aa50889e3be8?w=900&q=85",
        "https://images.unsplash.com/photo-1617343267581-fd30e8196c63?w=900&q=85",
        "https://images.unsplash.com/photo-1599474924187-334a4ae5bd3c?w=900&q=85",
    ],
    "cricket":      [
        "https://images.unsplash.com/photo-1593766788306-28561086a15b?w=900&q=85",
        "https://images.unsplash.com/photo-1540747913346-19212a4dbed5?w=900&q=85",
        "https://images.unsplash.com/photo-1531415074968-036ba1b575da?w=900&q=85",
        "https://images.unsplash.com/photo-1624526267942-ab0ff8a3e972?w=900&q=85",
    ],
    "tennis":       [
        "https://images.unsplash.com/photo-1617083934555-ac4a4f94f498?w=900&q=85",
        "https://images.unsplash.com/photo-1562552476-8ac59b2a2e46?w=900&q=85",
        "https://images.unsplash.com/photo-1554068865-24cecd4e34b8?w=900&q=85",
        "https://images.unsplash.com/photo-1521646369993-b65aba1e7e39?w=900&q=85",
    ],
    "football":     [
        "https://images.unsplash.com/photo-1543326727-cf6c39e8f84c?w=900&q=85",
        "https://images.unsplash.com/photo-1517466787929-bc90951d0974?w=900&q=85",
        "https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=900&q=85",
        "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=900&q=85",
    ],
    "swimming":     [
        "https://images.unsplash.com/photo-1530549387789-4c1017266635?w=900&q=85",
        "https://images.unsplash.com/photo-1560090995-01632a28895b?w=900&q=85",
        "https://images.unsplash.com/photo-1519315901367-f34ff9154487?w=900&q=85",
        "https://images.unsplash.com/photo-1572119865084-43c285814d63?w=900&q=85",
    ],
    "running":      [
        "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=900&q=85",
        "https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=900&q=85",
        "https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=900&q=85",
        "https://images.unsplash.com/photo-1539185441755-769473a23570?w=900&q=85",
    ],
    "fitness":      [
        "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=900&q=85",
        "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=900&q=85",
        "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?w=900&q=85",
        "https://images.unsplash.com/photo-1581009137042-c552e485697a?w=900&q=85",
    ],
    "table-tennis": [
        "https://images.unsplash.com/photo-1611251135345-18c56206b863?w=900&q=85",
        "https://images.unsplash.com/photo-1589952283406-b53a7d1347e8?w=900&q=85",
        "https://images.unsplash.com/photo-1593786001830-9b06ec2acab6?w=900&q=85",
        "https://images.unsplash.com/photo-1554068865-24cecd4e34b8?w=900&q=85",
    ],
    "basketball":   [
        "https://images.unsplash.com/photo-1546519638-68e109498ffc?w=900&q=85",
        "https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=900&q=85",
        "https://images.unsplash.com/photo-1504450758481-7338eba7524a?w=900&q=85",
        "https://images.unsplash.com/photo-1559692048-79a3f837883d?w=900&q=85",
    ],
    "cycling":      [
        "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=900&q=85",
        "https://images.unsplash.com/photo-1571068316344-75bc76f77890?w=900&q=85",
        "https://images.unsplash.com/photo-1541625602330-2277a4c46182?w=900&q=85",
        "https://images.unsplash.com/photo-1507035895480-2b3156c31fc8?w=900&q=85",
    ],
}

SIZE_SPORTS   = {"badminton", "tennis", "cricket", "football", "basketball", "running", "cycling"}
APPAREL_WORDS = {"jersey", "shorts", "short", "tights", "top", "jacket", "apparel", "shirt", "suit"}


# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════

def slugify(text: str) -> str:
    s = text.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def download_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Racketek/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def upload_url(url: str, folder: str) -> str | None:
    for attempt in range(3):
        try:
            print(f"      ↑  {url[:65]}…", end="", flush=True)
            data = download_bytes(url)
            res  = upload_image(data, folder=folder)
            print("  ✓")
            return res["url"]
        except Exception as exc:
            print(f"  ✗ attempt {attempt+1}: {exc}")
            time.sleep(2 ** attempt)
    return None


def make_sku(sport: str, idx: int, name: str) -> str:
    h = hashlib.md5(name.encode()).hexdigest()[:4].upper()
    return f"{sport[:3].upper()}-{idx+1:03d}-{h}"


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def seed():
    configure_cloudinary()
    db = SessionLocal()
    cats_n = prods_n = imgs_n = 0

    try:
        print("\n╔══════════════════════════════════════════════════════════╗")
        print("║         RACKETEK OUTLET  —  SEED DATA SCRIPT             ║")
        print("║   10 sports · 10 sub-cats · 10 products · 2-4 images     ║")
        print("╚══════════════════════════════════════════════════════════╝")

        for si, (sport_slug, sport_name, sport_desc) in enumerate(SPORTS):
            print(f"\n{'─'*62}")
            print(f"  [{si+1}/10]  {sport_name.upper()}")
            print(f"{'─'*62}")

            # ── parent category ──────────────────────────────────────────────
            parent = db.query(Category).filter(Category.slug == sport_slug).first()
            if not parent:
                parent = Category(name=sport_name, slug=sport_slug,
                                  description=sport_desc, is_active=True, sort_order=si)
                db.add(parent)
                db.flush()
                cats_n += 1
                print(f"  ✚ Created parent: {sport_name}")
            else:
                print(f"  ✓ Parent exists:  {sport_name}")

            # ── 10 sub-categories ────────────────────────────────────────────
            sub_list = SUBS.get(sport_slug, [])
            sub_objs: list[Category] = []
            for i, sub_name in enumerate(sub_list):
                sub_slug = f"{sport_slug}-{slugify(sub_name)}"
                sub = db.query(Category).filter(Category.slug == sub_slug).first()
                if not sub:
                    sub = Category(name=sub_name, slug=sub_slug,
                                   description=f"{sub_name} equipment for {sport_name}",
                                   parent_id=parent.id, is_active=True, sort_order=i)
                    db.add(sub)
                    db.flush()
                    cats_n += 1
                sub_objs.append(sub)
            print(f"  ✚ Sub-categories:  {', '.join(sub_list[:5])} …")

            # ── 10 products ───────────────────────────────────────────────────
            sport_imgs = IMAGES.get(sport_slug, [])
            prods_data = PRODUCTS.get(sport_slug, [])

            for pi, row in enumerate(prods_data):
                (pname, brand, price, compare_price, stock,
                 desc, short_desc, is_featured, is_best_seller) = row

                base_slug = slugify(pname)
                slug = base_slug
                if db.query(Product).filter(Product.slug == slug).first():
                    slug = f"{base_slug}-{sport_slug[:3]}"
                if db.query(Product).filter(Product.slug == slug).first():
                    print(f"  — skip (exists): {pname}")
                    continue

                # best-fit sub-category by keyword matching
                name_lower = pname.lower()
                assigned_sub = sub_objs[0]
                for so in sub_objs:
                    kws = so.name.lower().split()
                    if any(kw in name_lower for kw in kws):
                        assigned_sub = so
                        break

                product = Product(
                    name=pname,
                    slug=slug,
                    description=desc,
                    short_description=short_desc,
                    brand=brand,
                    sku=make_sku(sport_slug, pi, pname),
                    price=price,
                    compare_price=compare_price,
                    cost_price=round(price * 0.55, 2),
                    stock=stock,
                    low_stock_threshold=max(3, stock // 10),
                    status=ProductStatus.ACTIVE,
                    is_featured=is_featured,
                    is_best_seller=is_best_seller,
                    category_id=assigned_sub.id,
                    meta_title=f"Buy {pname} Online | RacketOutlet India",
                    meta_description=f"{short_desc} — {brand}. Authentic. Free shipping above ₹1000.",
                )
                db.add(product)
                db.flush()
                print(f"\n  📦 [{pi+1}/10] {pname}")

                # upload 2–4 images
                n_imgs = random.randint(2, min(4, len(sport_imgs)))
                for img_i in range(n_imgs):
                    img_url = sport_imgs[img_i % len(sport_imgs)]
                    cdn = upload_url(img_url, folder=f"racketek/products/{sport_slug}")
                    if cdn:
                        db.add(ProductImage(
                            product_id=product.id, url=cdn,
                            alt_text=pname,
                            is_primary=(img_i == 0),
                            sort_order=img_i,
                        ))
                        imgs_n += 1

                # size variants
                if sport_slug in SIZE_SPORTS and any(w in name_lower for w in ("shoe", "boot", "cleats")):
                    for sz in ["UK 6", "UK 7", "UK 8", "UK 9", "UK 10", "UK 11"]:
                        db.add(ProductVariant(
                            product_id=product.id, name="Size", value=sz,
                            sku=f"{product.sku}-{sz.replace(' ', '')}",
                            price_modifier=0, stock=max(5, stock // 6),
                        ))
                elif any(w in name_lower for w in APPAREL_WORDS):
                    for sz in ["S", "M", "L", "XL", "XXL"]:
                        db.add(ProductVariant(
                            product_id=product.id, name="Size", value=sz,
                            sku=f"{product.sku}-{sz}",
                            price_modifier=0, stock=max(5, stock // 5),
                        ))

                db.flush()
                prods_n += 1
                time.sleep(0.2)

        db.commit()
        print(f"\n\n{'═'*62}")
        print(f"  ✅  SEED COMPLETE")
        print(f"      Categories created : {cats_n:>4}")
        print(f"      Products created   : {prods_n:>4}")
        print(f"      Images uploaded    : {imgs_n:>4}")
        print(f"{'═'*62}\n")

    except Exception:
        db.rollback()
        print("\n❌  SEED FAILED — all changes rolled back")
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed()

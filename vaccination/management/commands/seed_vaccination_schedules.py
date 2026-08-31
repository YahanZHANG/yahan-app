from datetime import date

from django.core.management.base import BaseCommand

from vaccination.models import (
    Country,
    CountryScheduleItem,
    CountryScheduleItemTranslation,
    CountryScheduleVersion,
    VaccineComponent,
    VaccineProduct,
)


# =========================================================
# Official sources
# =========================================================

BAG_2026_URL = (
    "https://www.bag.admin.ch/de/"
    "schweizerischer-impfplan"
)

MHLW_VACCINATION_URL = (
    "https://www.mhlw.go.jp/stf/"
    "seisakunitsuite/bunya/kenkou_iryou/"
    "kenkou/kekkaku-kansenshou/"
    "yobou-sesshu/index.html"
)


# =========================================================
# Switzerland 2026
# =========================================================

SWISS_ITEMS = [

    # ---------------------------------------------------------
    # 2 months
    # ---------------------------------------------------------

    {
        "code": "CH_2M_HEXA",
        "name_en": "DTaP-IPV-Hib-HepB",
        "components": [
            "DIPHTHERIA",
            "TETANUS",
            "PERTUSSIS",
            "POLIO",
            "HIB",
            "HEPATITIS_B",
        ],
        "dose": 1,
        "min_days": 60,
        "max_days": 91,
        "display_age": "2か月",
        "sort_order": 10,
        "names": {
            "ja": "6種混合",
            "en": "DTaP-IPV-Hib-HepB",
            "de": "DTPa-IPV-Hib-HBV",
            "zh-hans": "六联疫苗",
        },
        "notes": {
            "ja": "1回目",
            "en": "Dose 1",
            "de": "1. Dosis",
            "zh-hans": "第1剂",
        },
    },

    {
        "code": "CH_2M_PCV",
        "name_en": "Pneumococcal vaccine",
        "components": [
            "PNEUMOCOCCAL",
        ],
        "dose": 1,
        "min_days": 60,
        "max_days": 91,
        "display_age": "2か月",
        "sort_order": 20,
        "names": {
            "ja": "肺炎球菌",
            "en": "Pneumococcal",
            "de": "Pneumokokken",
            "zh-hans": "肺炎球菌",
        },
        "notes": {
            "ja": "1回目",
            "en": "Dose 1",
            "de": "1. Dosis",
            "zh-hans": "第1剂",
        },
    },

    {
        "code": "CH_2M_ROTA",
        "name_en": "Rotavirus vaccine",
        "components": [
            "ROTAVIRUS",
        ],
        "dose": 1,
        "min_days": 42,
        "max_days": 105,
        "display_age": "2か月",
        "sort_order": 30,
        "names": {
            "ja": "ロタウイルス",
            "en": "Rotavirus",
            "de": "Rotaviren",
            "zh-hans": "轮状病毒",
        },
        "notes": {
            "ja": "1回目",
            "en": "Dose 1",
            "de": "1. Dosis",
            "zh-hans": "第1剂",
        },
    },


    # ---------------------------------------------------------
    # 4 months
    # ---------------------------------------------------------

    {
        "code": "CH_4M_HEXA",
        "name_en": "DTaP-IPV-Hib-HepB",
        "components": [
            "DIPHTHERIA",
            "TETANUS",
            "PERTUSSIS",
            "POLIO",
            "HIB",
            "HEPATITIS_B",
        ],
        "dose": 2,
        "min_days": 120,
        "max_days": 152,
        "display_age": "4か月",
        "sort_order": 40,
        "names": {
            "ja": "6種混合",
            "en": "DTaP-IPV-Hib-HepB",
            "de": "DTPa-IPV-Hib-HBV",
            "zh-hans": "六联疫苗",
        },
        "notes": {
            "ja": "2回目",
            "en": "Dose 2",
            "de": "2. Dosis",
            "zh-hans": "第2剂",
        },
    },

    {
        "code": "CH_4M_PCV",
        "name_en": "Pneumococcal vaccine",
        "components": [
            "PNEUMOCOCCAL",
        ],
        "dose": 2,
        "min_days": 120,
        "max_days": 152,
        "display_age": "4か月",
        "sort_order": 50,
        "names": {
            "ja": "肺炎球菌",
            "en": "Pneumococcal",
            "de": "Pneumokokken",
            "zh-hans": "肺炎球菌",
        },
        "notes": {
            "ja": "2回目",
            "en": "Dose 2",
            "de": "2. Dosis",
            "zh-hans": "第2剂",
        },
    },

    {
        "code": "CH_4M_ROTA",
        "name_en": "Rotavirus vaccine",
        "components": [
            "ROTAVIRUS",
        ],
        "dose": 2,
        "min_days": 120,
        "max_days": 224,
        "display_age": "4か月",
        "sort_order": 60,
        "names": {
            "ja": "ロタウイルス",
            "en": "Rotavirus",
            "de": "Rotaviren",
            "zh-hans": "轮状病毒",
        },
        "notes": {
            "ja": "2回目",
            "en": "Dose 2",
            "de": "2. Dosis",
            "zh-hans": "第2剂",
        },
    },


    # ---------------------------------------------------------
    # 9 months
    # ---------------------------------------------------------

    {
        "code": "CH_9M_MMR",
        "name_en": "MMR",
        "components": [
            "MEASLES",
            "MUMPS",
            "RUBELLA",
        ],
        "dose": 1,
        "min_days": 273,
        "max_days": 334,
        "display_age": "9か月",
        "sort_order": 70,
        "names": {
            "ja": "MMR",
            "en": "MMR",
            "de": "MMR",
            "zh-hans": "麻腮风（MMR）",
        },
        "notes": {
            "ja": "1回目",
            "en": "Dose 1",
            "de": "1. Dosis",
            "zh-hans": "第1剂",
        },
    },

    {
        "code": "CH_9M_VARICELLA",
        "name_en": "Varicella",
        "components": [
            "VARICELLA",
        ],
        "dose": 1,
        "min_days": 273,
        "max_days": 334,
        "display_age": "9か月",
        "sort_order": 80,
        "names": {
            "ja": "水痘",
            "en": "Varicella",
            "de": "Varizellen",
            "zh-hans": "水痘",
        },
        "notes": {
            "ja": "1回目",
            "en": "Dose 1",
            "de": "1. Dosis",
            "zh-hans": "第1剂",
        },
    },


    # ---------------------------------------------------------
    # 12 months
    # ---------------------------------------------------------

    {
        "code": "CH_12M_HEXA",
        "name_en": "DTaP-IPV-Hib-HepB",
        "components": [
            "DIPHTHERIA",
            "TETANUS",
            "PERTUSSIS",
            "POLIO",
            "HIB",
            "HEPATITIS_B",
        ],
        "dose": 3,
        "min_days": 334,
        "max_days": 395,
        "display_age": "12か月",
        "sort_order": 90,
        "names": {
            "ja": "6種混合",
            "en": "DTaP-IPV-Hib-HepB",
            "de": "DTPa-IPV-Hib-HBV",
            "zh-hans": "六联疫苗",
        },
        "notes": {
            "ja": "3回目",
            "en": "Dose 3",
            "de": "3. Dosis",
            "zh-hans": "第3剂",
        },
    },

    {
        "code": "CH_12M_PCV",
        "name_en": "Pneumococcal vaccine",
        "components": [
            "PNEUMOCOCCAL",
        ],
        "dose": 3,
        "min_days": 334,
        "max_days": 395,
        "display_age": "12か月",
        "sort_order": 100,
        "names": {
            "ja": "肺炎球菌",
            "en": "Pneumococcal",
            "de": "Pneumokokken",
            "zh-hans": "肺炎球菌",
        },
        "notes": {
            "ja": "3回目",
            "en": "Dose 3",
            "de": "3. Dosis",
            "zh-hans": "第3剂",
        },
    },

    {
        "code": "CH_12M_MMR",
        "name_en": "MMR",
        "components": [
            "MEASLES",
            "MUMPS",
            "RUBELLA",
        ],
        "dose": 2,
        "min_days": 365,
        "max_days": 456,
        "display_age": "12か月",
        "sort_order": 110,
        "names": {
            "ja": "MMR",
            "en": "MMR",
            "de": "MMR",
            "zh-hans": "麻腮风（MMR）",
        },
        "notes": {
            "ja": "2回目",
            "en": "Dose 2",
            "de": "2. Dosis",
            "zh-hans": "第2剂",
        },
    },

    {
        "code": "CH_12M_VARICELLA",
        "name_en": "Varicella",
        "components": [
            "VARICELLA",
        ],
        "dose": 2,
        "min_days": 365,
        "max_days": 456,
        "display_age": "12か月",
        "sort_order": 120,
        "names": {
            "ja": "水痘",
            "en": "Varicella",
            "de": "Varizellen",
            "zh-hans": "水痘",
        },
        "notes": {
            "ja": "2回目",
            "en": "Dose 2",
            "de": "2. Dosis",
            "zh-hans": "第2剂",
        },
    },
]


# =========================================================
# Japan 2026
# =========================================================

JAPAN_ITEMS = [

    # =========================================================
    # Rotavirus
    # =========================================================

    {
        "code": "JP_ROTA_1",
        "name_en": "Rotavirus",
        "components": [
            "ROTAVIRUS",
        ],
        "dose": 1,

        # 標準的な初回開始:
        # 生後2か月〜出生14週6日後
        "min_days": 60,
        "max_days": 104,

        "interval_min_days": None,
        "interval_max_days": None,
        "interval_from_dose": None,

        "product_name": None,

        "display_age": "ロタウイルス",
        "sort_order": 1,

        "names": {
            "ja": "ロタウイルス",
            "en": "Rotavirus",
            "de": "Rotaviren",
            "zh-hans": "轮状病毒",
        },

        "notes": {
            "ja": "1回目・標準は生後2か月〜出生14週6日後",
            "en": "Dose 1 · usually from 2 months to 14 weeks 6 days",
            "de": "1. Dosis · üblicherweise ab 2 Monaten bis 14 Wochen + 6 Tage",
            "zh-hans": "第1剂・通常在2个月至出生后14周6天",
        },
    },


    # ---------------------------------------------------------
    # Rotarix
    # ---------------------------------------------------------

    {
        "code": "JP_ROTARIX_2",
        "name_en": "Rotavirus",

        "components": [
            "ROTAVIRUS",
        ],

        "dose": 2,

        "min_days": 60,

        # 出生24週0日後
        "max_days": 168,

        "interval_min_days": 27,
        "interval_max_days": None,
        "interval_from_dose": 1,

        "product_name": "Rotarix",

        "display_age": "ロタウイルス",
        "sort_order": 2,

        "names": {
            "ja": "ロタウイルス",
            "en": "Rotavirus",
            "de": "Rotaviren",
            "zh-hans": "轮状病毒",
        },

        "notes": {
            "ja": "Rotarix 2回目・27日以上空け、出生24週0日後まで",
            "en": "Rotarix dose 2 · at least 27 days later, by 24 weeks",
            "de": "Rotarix 2. Dosis · mindestens 27 Tage später, bis 24 Wochen",
            "zh-hans": "Rotarix第2剂・至少间隔27天，并在出生后24周前完成",
        },
    },


    # ---------------------------------------------------------
    # RotaTeq
    # ---------------------------------------------------------

    {
        "code": "JP_ROTATEQ_2",
        "name_en": "Rotavirus",

        "components": [
            "ROTAVIRUS",
        ],

        "dose": 2,

        "min_days": 60,

        # シリーズ全体は出生32週0日後まで
        "max_days": 224,

        "interval_min_days": 27,
        "interval_max_days": None,
        "interval_from_dose": 1,

        "product_name": "RotaTeq",

        "display_age": "ロタウイルス",
        "sort_order": 3,

        "names": {
            "ja": "ロタウイルス",
            "en": "Rotavirus",
            "de": "Rotaviren",
            "zh-hans": "轮状病毒",
        },

        "notes": {
            "ja": "RotaTeq 2回目・1回目から27日以上",
            "en": "RotaTeq dose 2 · at least 27 days after dose 1",
            "de": "RotaTeq 2. Dosis · mindestens 27 Tage nach Dosis 1",
            "zh-hans": "RotaTeq第2剂・距第1剂至少27天",
        },
    },

    {
        "code": "JP_ROTATEQ_3",
        "name_en": "Rotavirus",

        "components": [
            "ROTAVIRUS",
        ],

        "dose": 3,

        "min_days": 60,

        # 出生32週0日後
        "max_days": 224,

        "interval_min_days": 27,
        "interval_max_days": None,
        "interval_from_dose": 2,

        "product_name": "RotaTeq",

        "display_age": "ロタウイルス",
        "sort_order": 4,

        "names": {
            "ja": "ロタウイルス",
            "en": "Rotavirus",
            "de": "Rotaviren",
            "zh-hans": "轮状病毒",
        },

        "notes": {
            "ja": "RotaTeq 3回目・27日以上空け、出生32週0日後まで",
            "en": "RotaTeq dose 3 · at least 27 days later, by 32 weeks",
            "de": "RotaTeq 3. Dosis · mindestens 27 Tage später, bis 32 Wochen",
            "zh-hans": "RotaTeq第3剂・至少间隔27天，并在出生后32周前完成",
        },
    },

    # ---------------------------------------------------------
    # 5種混合 DTaP-IPV-Hib
    # ---------------------------------------------------------

    {
        "code": "JP_PENTA_1",
        "name_en": "DTaP-IPV-Hib",
        "components": [
            "DIPHTHERIA",
            "TETANUS",
            "PERTUSSIS",
            "POLIO",
            "HIB",
        ],
        "dose": 1,
        "min_days": 60,
        "max_days": 213,
        "interval_min_days": None,
        "interval_max_days": None,
        "interval_from_dose": None,
        "display_age": "2〜7か月",
        "sort_order": 10,
        "names": {
            "ja": "5種混合",
            "en": "DTaP-IPV-Hib",
            "de": "DTPa-IPV-Hib",
            "zh-hans": "五联疫苗",
        },
        "notes": {
            "ja": "初回1回目",
            "en": "Primary dose 1",
            "de": "Grundimmunisierung 1",
            "zh-hans": "基础免疫第1剂",
        },
    },

    {
        "code": "JP_PENTA_2",
        "name_en": "DTaP-IPV-Hib",
        "components": [
            "DIPHTHERIA",
            "TETANUS",
            "PERTUSSIS",
            "POLIO",
            "HIB",
        ],
        "dose": 2,
        "min_days": 60,
        "max_days": 365,
        "interval_min_days": 20,
        "interval_max_days": 56,
        "interval_from_dose": 1,
        "display_age": "初回シリーズ",
        "sort_order": 20,
        "names": {
            "ja": "5種混合",
            "en": "DTaP-IPV-Hib",
            "de": "DTPa-IPV-Hib",
            "zh-hans": "五联疫苗",
        },
        "notes": {
            "ja": "初回2回目・1回目から標準20〜56日",
            "en": "Primary dose 2 · usually 20–56 days after dose 1",
            "de": "2. Dosis · üblicherweise 20–56 Tage nach Dosis 1",
            "zh-hans": "基础免疫第2剂・通常距第1剂20～56天",
        },
    },

    {
        "code": "JP_PENTA_3",
        "name_en": "DTaP-IPV-Hib",
        "components": [
            "DIPHTHERIA",
            "TETANUS",
            "PERTUSSIS",
            "POLIO",
            "HIB",
        ],
        "dose": 3,
        "min_days": 60,
        "max_days": 365,
        "interval_min_days": 20,
        "interval_max_days": 56,
        "interval_from_dose": 2,
        "display_age": "初回シリーズ",
        "sort_order": 30,
        "names": {
            "ja": "5種混合",
            "en": "DTaP-IPV-Hib",
            "de": "DTPa-IPV-Hib",
            "zh-hans": "五联疫苗",
        },
        "notes": {
            "ja": "初回3回目・2回目から標準20〜56日",
            "en": "Primary dose 3 · usually 20–56 days after dose 2",
            "de": "3. Dosis · üblicherweise 20–56 Tage nach Dosis 2",
            "zh-hans": "基础免疫第3剂・通常距第2剂20～56天",
        },
    },

    {
        "code": "JP_PENTA_4",
        "name_en": "DTaP-IPV-Hib",
        "components": [
            "DIPHTHERIA",
            "TETANUS",
            "PERTUSSIS",
            "POLIO",
            "HIB",
        ],
        "dose": 4,

        # 接種間隔を主に使って判定するため、
        # 1歳固定にはしない。
        "min_days": 60,
        "max_days": 2737,

        "interval_min_days": 183,
        "interval_max_days": 548,
        "interval_from_dose": 3,

        "display_age": "追加接種",
        "sort_order": 40,
        "names": {
            "ja": "5種混合",
            "en": "DTaP-IPV-Hib",
            "de": "DTPa-IPV-Hib",
            "zh-hans": "五联疫苗",
        },
        "notes": {
            "ja": "追加・初回終了後 標準6〜18か月",
            "en": "Booster · usually 6–18 months after the primary series",
            "de": "Auffrischung · üblicherweise 6–18 Monate später",
            "zh-hans": "加强剂・基础免疫后通常6～18个月",
        },
    },


    # ---------------------------------------------------------
    # Pneumococcal
    # ---------------------------------------------------------

    {
        "code": "JP_PCV_1",
        "name_en": "Pneumococcal vaccine",
        "components": [
            "PNEUMOCOCCAL",
        ],
        "dose": 1,
        "min_days": 60,
        "max_days": 213,
        "interval_min_days": None,
        "interval_max_days": None,
        "interval_from_dose": None,
        "display_age": "2〜7か月",
        "sort_order": 50,
        "names": {
            "ja": "肺炎球菌",
            "en": "Pneumococcal",
            "de": "Pneumokokken",
            "zh-hans": "肺炎球菌",
        },
        "notes": {
            "ja": "初回1回目",
            "en": "Primary dose 1",
            "de": "Grundimmunisierung 1",
            "zh-hans": "基础免疫第1剂",
        },
    },

    {
        "code": "JP_PCV_2",
        "name_en": "Pneumococcal vaccine",
        "components": [
            "PNEUMOCOCCAL",
        ],
        "dose": 2,
        "min_days": 60,
        "max_days": 365,
        "interval_min_days": 27,
        "interval_max_days": None,
        "interval_from_dose": 1,
        "display_age": "初回シリーズ",
        "sort_order": 60,
        "names": {
            "ja": "肺炎球菌",
            "en": "Pneumococcal",
            "de": "Pneumokokken",
            "zh-hans": "肺炎球菌",
        },
        "notes": {
            "ja": "初回2回目・1回目から27日以上",
            "en": "Primary dose 2 · at least 27 days after dose 1",
            "de": "2. Dosis · mindestens 27 Tage nach Dosis 1",
            "zh-hans": "基础免疫第2剂・距第1剂至少27天",
        },
    },

    {
        "code": "JP_PCV_3",
        "name_en": "Pneumococcal vaccine",
        "components": [
            "PNEUMOCOCCAL",
        ],
        "dose": 3,
        "min_days": 60,
        "max_days": 365,
        "interval_min_days": 27,
        "interval_max_days": None,
        "interval_from_dose": 2,
        "display_age": "初回シリーズ",
        "sort_order": 70,
        "names": {
            "ja": "肺炎球菌",
            "en": "Pneumococcal",
            "de": "Pneumokokken",
            "zh-hans": "肺炎球菌",
        },
        "notes": {
            "ja": "初回3回目・2回目から27日以上",
            "en": "Primary dose 3 · at least 27 days after dose 2",
            "de": "3. Dosis · mindestens 27 Tage nach Dosis 2",
            "zh-hans": "基础免疫第3剂・距第2剂至少27天",
        },
    },

    {
        "code": "JP_PCV_4",
        "name_en": "Pneumococcal vaccine",
        "components": [
            "PNEUMOCOCCAL",
        ],
        "dose": 4,
        "min_days": 365,
        "max_days": 456,
        "interval_min_days": 60,
        "interval_max_days": None,
        "interval_from_dose": 3,
        "display_age": "12〜15か月",
        "sort_order": 80,
        "names": {
            "ja": "肺炎球菌",
            "en": "Pneumococcal",
            "de": "Pneumokokken",
            "zh-hans": "肺炎球菌",
        },
        "notes": {
            "ja": "追加・初回終了から60日以上",
            "en": "Booster · at least 60 days after the primary series",
            "de": "Auffrischung · mindestens 60 Tage nach der Grundimmunisierung",
            "zh-hans": "加强剂・基础免疫完成后至少60天",
        },
    },


    # ---------------------------------------------------------
    # Hepatitis B
    # ---------------------------------------------------------

    {
        "code": "JP_HEPB_1",
        "name_en": "Hepatitis B",
        "components": [
            "HEPATITIS_B",
        ],
        "dose": 1,
        "min_days": 60,
        "max_days": 274,
        "interval_min_days": None,
        "interval_max_days": None,
        "interval_from_dose": None,
        "display_age": "2〜9か月",
        "sort_order": 90,
        "names": {
            "ja": "B型肝炎",
            "en": "Hepatitis B",
            "de": "Hepatitis B",
            "zh-hans": "乙型肝炎",
        },
        "notes": {
            "ja": "1回目",
            "en": "Dose 1",
            "de": "1. Dosis",
            "zh-hans": "第1剂",
        },
    },

    {
        "code": "JP_HEPB_2",
        "name_en": "Hepatitis B",
        "components": [
            "HEPATITIS_B",
        ],
        "dose": 2,
        "min_days": 60,
        "max_days": 274,
        "interval_min_days": 27,
        "interval_max_days": None,
        "interval_from_dose": 1,
        "display_age": "2〜9か月",
        "sort_order": 100,
        "names": {
            "ja": "B型肝炎",
            "en": "Hepatitis B",
            "de": "Hepatitis B",
            "zh-hans": "乙型肝炎",
        },
        "notes": {
            "ja": "2回目・1回目から27日以上",
            "en": "Dose 2 · at least 27 days after dose 1",
            "de": "2. Dosis · mindestens 27 Tage nach Dosis 1",
            "zh-hans": "第2剂・距第1剂至少27天",
        },
    },

    {
        "code": "JP_HEPB_3",
        "name_en": "Hepatitis B",
        "components": [
            "HEPATITIS_B",
        ],
        "dose": 3,
        "min_days": 60,
        "max_days": 274,
        "interval_min_days": 139,
        "interval_max_days": None,
        "interval_from_dose": 1,
        "display_age": "2〜9か月",
        "sort_order": 110,
        "names": {
            "ja": "B型肝炎",
            "en": "Hepatitis B",
            "de": "Hepatitis B",
            "zh-hans": "乙型肝炎",
        },
        "notes": {
            "ja": "3回目・1回目から139日以上",
            "en": "Dose 3 · at least 139 days after dose 1",
            "de": "3. Dosis · mindestens 139 Tage nach Dosis 1",
            "zh-hans": "第3剂・距第1剂至少139天",
        },
    },


    # ---------------------------------------------------------
    # BCG
    # ---------------------------------------------------------

    {
        "code": "JP_BCG",
        "name_en": "BCG",
        "components": [
            "BCG",
        ],
        "dose": 1,
        "min_days": 152,
        "max_days": 274,
        "interval_min_days": None,
        "interval_max_days": None,
        "interval_from_dose": None,
        "display_age": "5〜8か月",
        "sort_order": 120,
        "names": {
            "ja": "BCG",
            "en": "BCG",
            "de": "BCG",
            "zh-hans": "卡介苗（BCG）",
        },
        "notes": {
            "ja": "標準5〜8か月に1回",
            "en": "One standard dose at 5–8 months",
            "de": "Eine Standarddosis mit 5–8 Monaten",
            "zh-hans": "通常在5～8个月接种1剂",
        },
    },


    # ---------------------------------------------------------
    # MR
    # ---------------------------------------------------------

    {
        "code": "JP_MR_1",
        "name_en": "Measles-Rubella",
        "components": [
            "MEASLES",
            "RUBELLA",
        ],
        "dose": 1,
        "min_days": 365,
        "max_days": 729,
        "interval_min_days": None,
        "interval_max_days": None,
        "interval_from_dose": None,
        "display_age": "1歳",
        "sort_order": 130,
        "names": {
            "ja": "MR（麻しん・風しん）",
            "en": "MR (Measles-Rubella)",
            "de": "MR (Masern-Röteln)",
            "zh-hans": "麻疹・风疹（MR）",
        },
        "notes": {
            "ja": "第1期・1歳の1年間",
            "en": "Dose 1 · during the second year of life",
            "de": "1. Dosis · im zweiten Lebensjahr",
            "zh-hans": "第1期・1岁期间",
        },
    },

    {
        "code": "JP_MR_2",
        "name_en": "Measles-Rubella",
        "components": [
            "MEASLES",
            "RUBELLA",
        ],
        "dose": 2,
        "min_days": 1825,
        "max_days": 2555,
        "interval_min_days": None,
        "interval_max_days": None,
        "interval_from_dose": None,
        "display_age": "就学前",
        "sort_order": 140,
        "names": {
            "ja": "MR（麻しん・風しん）",
            "en": "MR (Measles-Rubella)",
            "de": "MR (Masern-Röteln)",
            "zh-hans": "麻疹・风疹（MR）",
        },
        "notes": {
            "ja": "第2期・小学校入学前の1年間",
            "en": "Dose 2 · during the year before primary school",
            "de": "2. Dosis · im Jahr vor der Einschulung",
            "zh-hans": "第2期・小学入学前1年",
        },
    },


    # ---------------------------------------------------------
    # Varicella
    # ---------------------------------------------------------

    {
        "code": "JP_VARICELLA_1",
        "name_en": "Varicella",
        "components": [
            "VARICELLA",
        ],
        "dose": 1,
        "min_days": 365,
        "max_days": 456,
        "interval_min_days": None,
        "interval_max_days": None,
        "interval_from_dose": None,
        "display_age": "12〜15か月",
        "sort_order": 150,
        "names": {
            "ja": "水痘",
            "en": "Varicella",
            "de": "Varizellen",
            "zh-hans": "水痘",
        },
        "notes": {
            "ja": "1回目",
            "en": "Dose 1",
            "de": "1. Dosis",
            "zh-hans": "第1剂",
        },
    },

    {
        "code": "JP_VARICELLA_2",
        "name_en": "Varicella",
        "components": [
            "VARICELLA",
        ],
        "dose": 2,
        "min_days": 365,
        "max_days": 1095,
        "interval_min_days": 183,
        "interval_max_days": 365,
        "interval_from_dose": 1,
        "display_age": "水痘 2回目",
        "sort_order": 160,
        "names": {
            "ja": "水痘",
            "en": "Varicella",
            "de": "Varizellen",
            "zh-hans": "水痘",
        },
        "notes": {
            "ja": "標準は1回目から6〜12か月",
            "en": "Usually 6–12 months after dose 1",
            "de": "Üblicherweise 6–12 Monate nach Dosis 1",
            "zh-hans": "通常距第1剂6～12个月",
        },
    },


    # ---------------------------------------------------------
    # Japanese encephalitis
    # ---------------------------------------------------------

    {
        "code": "JP_JE_1",
        "name_en": "Japanese encephalitis",
        "components": [
            "JAPANESE_ENCEPHALITIS",
        ],
        "dose": 1,
        "min_days": 1095,
        "max_days": 1460,
        "interval_min_days": None,
        "interval_max_days": None,
        "interval_from_dose": None,
        "display_age": "3〜4歳",
        "sort_order": 170,
        "names": {
            "ja": "日本脳炎",
            "en": "Japanese encephalitis",
            "de": "Japanische Enzephalitis",
            "zh-hans": "日本脑炎",
        },
        "notes": {
            "ja": "第1期 初回1回目",
            "en": "Primary series dose 1",
            "de": "Grundimmunisierung 1",
            "zh-hans": "第1期基础免疫第1剂",
        },
    },

    {
        "code": "JP_JE_2",
        "name_en": "Japanese encephalitis",
        "components": [
            "JAPANESE_ENCEPHALITIS",
        ],
        "dose": 2,
        "min_days": 1095,
        "max_days": 1460,
        "interval_min_days": 6,
        "interval_max_days": 28,
        "interval_from_dose": 1,
        "display_age": "3〜4歳",
        "sort_order": 180,
        "names": {
            "ja": "日本脳炎",
            "en": "Japanese encephalitis",
            "de": "Japanische Enzephalitis",
            "zh-hans": "日本脑炎",
        },
        "notes": {
            "ja": "初回2回目・1回目から6〜28日",
            "en": "Primary dose 2 · 6–28 days after dose 1",
            "de": "2. Dosis · 6–28 Tage nach Dosis 1",
            "zh-hans": "基础免疫第2剂・距第1剂6～28天",
        },
    },

    {
        "code": "JP_JE_3",
        "name_en": "Japanese encephalitis",
        "components": [
            "JAPANESE_ENCEPHALITIS",
        ],
        "dose": 3,
        "min_days": 1460,
        "max_days": 1825,
        "interval_min_days": None,
        "interval_max_days": None,
        "interval_from_dose": None,
        "display_age": "4歳頃",
        "sort_order": 190,
        "names": {
            "ja": "日本脳炎",
            "en": "Japanese encephalitis",
            "de": "Japanische Enzephalitis",
            "zh-hans": "日本脑炎",
        },
        "notes": {
            "ja": "第1期追加・初回終了からおおむね1年",
            "en": "Booster · around 1 year after the primary series",
            "de": "Auffrischung · etwa 1 Jahr nach der Grundimmunisierung",
            "zh-hans": "第1期加强剂・基础免疫完成后约1年",
        },
    },

    {
        "code": "JP_JE_4",
        "name_en": "Japanese encephalitis",
        "components": [
            "JAPANESE_ENCEPHALITIS",
        ],
        "dose": 4,
        "min_days": 3285,
        "max_days": 3650,
        "interval_min_days": None,
        "interval_max_days": None,
        "interval_from_dose": None,
        "display_age": "9〜10歳",
        "sort_order": 200,
        "names": {
            "ja": "日本脳炎",
            "en": "Japanese encephalitis",
            "de": "Japanische Enzephalitis",
            "zh-hans": "日本脑炎",
        },
        "notes": {
            "ja": "第2期",
            "en": "Second-stage dose",
            "de": "2. Impfphase",
            "zh-hans": "第2期",
        },
    },
]


# =========================================================
# Command
# =========================================================

class Command(BaseCommand):
    help = "Seed official country vaccination schedules."

    def handle(self, *args, **options):

        self.seed_switzerland()
        self.seed_japan()

        self.stdout.write(
            self.style.SUCCESS(
                "Vaccination schedules seeded successfully."
            )
        )


    # =====================================================
    # Switzerland
    # =====================================================

    def seed_switzerland(self):

        country = Country.objects.get(
            code="CH"
        )

        schedule, _ = (
            CountryScheduleVersion.objects
            .update_or_create(
                country=country,
                title="Swiss Vaccination Plan 2026",
                defaults={
                    "valid_from": date(
                        2026,
                        1,
                        1,
                    ),
                    "valid_until": date(
                        2026,
                        12,
                        31,
                    ),
                    "source_name": (
                        "Bundesamt für Gesundheit "
                        "— Schweizerischer Impfplan 2026"
                    ),
                    "source_url": BAG_2026_URL,
                    "last_verified_at": date(
                        2026,
                        8,
                        31,
                    ),
                },
            )
        )


        # -------------------------------------------------
        # 古くなった項目を削除
        # -------------------------------------------------

        current_codes = {
            data["code"]
            for data in SWISS_ITEMS
        }

        schedule.items.exclude(
            code__in=current_codes
        ).delete()


        # -------------------------------------------------
        # Create / update
        # -------------------------------------------------

        for data in SWISS_ITEMS:

            item, _ = (
                CountryScheduleItem.objects
                .update_or_create(
                    schedule=schedule,
                    code=data["code"],
                    defaults={
                        "name_en": data[
                            "name_en"
                        ],

                        "applies_to_product": None,

                        "recommended_age_min_days": (
                            data["min_days"]
                        ),

                        "recommended_age_max_days": (
                            data["max_days"]
                        ),

                        "recommended_interval_min_days": None,

                        "recommended_interval_max_days": None,

                        "recommended_interval_from_dose_number": None,

                        "display_age": data[
                            "display_age"
                        ],

                        "dose_number": data[
                            "dose"
                        ],

                        "sort_order": data[
                            "sort_order"
                        ],
                    },
                )
            )


            components = (
                VaccineComponent.objects
                .filter(
                    code__in=data[
                        "components"
                    ]
                )
            )

            found = set(
                components.values_list(
                    "code",
                    flat=True,
                )
            )

            missing = (
                set(
                    data["components"]
                )
                - found
            )

            if missing:
                raise ValueError(
                    "Missing Swiss components: "
                    + ", ".join(
                        sorted(missing)
                    )
                )

            item.required_components.set(
                components
            )


            for language_code, name in (
                data["names"].items()
            ):

                note = (
                    data
                    .get(
                        "notes",
                        {},
                    )
                    .get(
                        language_code,
                        "",
                    )
                )

                (
                    CountryScheduleItemTranslation
                    .objects
                    .update_or_create(
                        schedule_item=item,
                        language_code=(
                            language_code
                        ),
                        defaults={
                            "name": name,
                            "note": note,
                        },
                    )
                )


        self.stdout.write(
            "Switzerland 2026: "
            f"{schedule.items.count()} items"
        )


    # =====================================================
    # Japan
    # =====================================================

    def seed_japan(self):

        country = Country.objects.get(
            code="JP"
        )

        schedule, _ = (
            CountryScheduleVersion.objects
            .update_or_create(
                country=country,
                title=(
                    "Japan Routine Vaccination "
                    "Schedule 2026"
                ),
                defaults={
                    "valid_from": date(
                        2026,
                        1,
                        1,
                    ),
                    "valid_until": date(
                        2026,
                        12,
                        31,
                    ),
                    "source_name": (
                        "厚生労働省 "
                        "— 予防接種・ワクチン情報"
                    ),
                    "source_url": (
                        MHLW_VACCINATION_URL
                    ),
                    "last_verified_at": date(
                        2026,
                        8,
                        31,
                    ),
                },
            )
        )


        # -------------------------------------------------
        # 古くなった項目を削除
        # -------------------------------------------------

        current_codes = {
            data["code"]
            for data in JAPAN_ITEMS
        }

        schedule.items.exclude(
            code__in=current_codes
        ).delete()


        # -------------------------------------------------
        # Create / update
        # -------------------------------------------------

        for data in JAPAN_ITEMS:

            applicable_product = None

            product_name = data.get(
                "product_name"
            )

            if product_name:

                applicable_product = (
                    VaccineProduct.objects.get(
                        preparation__code="ROTAVIRUS",
                        product_name=product_name,
                    )
                )

            item, _ = (
                CountryScheduleItem.objects
                .update_or_create(
                    schedule=schedule,
                    code=data["code"],
                    defaults={
                        "name_en": data[
                            "name_en"
                        ],

                        "applies_to_product": (
                            applicable_product
                        ),

                        "recommended_age_min_days": (
                            data["min_days"]
                        ),

                        "recommended_age_max_days": (
                            data["max_days"]
                        ),

                        "recommended_interval_min_days": (
                            data[
                                "interval_min_days"
                            ]
                        ),

                        "recommended_interval_max_days": (
                            data[
                                "interval_max_days"
                            ]
                        ),

                        "recommended_interval_from_dose_number": (
                            data[
                                "interval_from_dose"
                            ]
                        ),

                        "display_age": data[
                            "display_age"
                        ],

                        "dose_number": data[
                            "dose"
                        ],

                        "sort_order": data[
                            "sort_order"
                        ],
                    },
                )
            )


            components = (
                VaccineComponent.objects
                .filter(
                    code__in=data[
                        "components"
                    ]
                )
            )

            found = set(
                components.values_list(
                    "code",
                    flat=True,
                )
            )

            missing = (
                set(
                    data["components"]
                )
                - found
            )

            if missing:
                raise ValueError(
                    "Missing Japan components: "
                    + ", ".join(
                        sorted(missing)
                    )
                )

            item.required_components.set(
                components
            )


            for language_code, name in (
                data["names"].items()
            ):

                note = (
                    data
                    .get(
                        "notes",
                        {},
                    )
                    .get(
                        language_code,
                        "",
                    )
                )

                (
                    CountryScheduleItemTranslation
                    .objects
                    .update_or_create(
                        schedule_item=item,
                        language_code=(
                            language_code
                        ),
                        defaults={
                            "name": name,
                            "note": note,
                        },
                    )
                )


        self.stdout.write(
            "Japan 2026: "
            f"{schedule.items.count()} items"
        )
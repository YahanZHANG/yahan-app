from django.core.management.base import BaseCommand

from vaccination.models import (
    Country,
    CountryTranslation,
    VaccineComponent,
    VaccineComponentTranslation,
    VaccinePreparation,
    VaccinePreparationTranslation,
    VaccineProduct,
)


LANGUAGES = [
    "ja",
    "en",
    "de",
    "zh-hans",
]


COUNTRIES = [
    {
        "code": "CH",
        "name_en": "Switzerland",
        "translations": {
            "ja": "スイス",
            "en": "Switzerland",
            "de": "Schweiz",
            "zh-hans": "瑞士",
        },
    },
    {
        "code": "JP",
        "name_en": "Japan",
        "translations": {
            "ja": "日本",
            "en": "Japan",
            "de": "Japan",
            "zh-hans": "日本",
        },
    },
    {
        "code": "CN",
        "name_en": "China",
        "translations": {
            "ja": "中国",
            "en": "China",
            "de": "China",
            "zh-hans": "中国",
        },
    },
    {
        "code": "DE",
        "name_en": "Germany",
        "translations": {
            "ja": "ドイツ",
            "en": "Germany",
            "de": "Deutschland",
            "zh-hans": "德国",
        },
    },
]


COMPONENTS = [
    {
        "code": "BCG",
        "name_en": "Tuberculosis",
        "translations": {
            "ja": "結核（BCG）",
            "en": "Tuberculosis (BCG)",
            "de": "Tuberkulose (BCG)",
            "zh-hans": "结核病（BCG）",
        },
    },
    {
        "code": "HEPATITIS_B",
        "name_en": "Hepatitis B",
        "translations": {
            "ja": "B型肝炎",
            "en": "Hepatitis B",
            "de": "Hepatitis B",
            "zh-hans": "乙型肝炎",
        },
    },
    {
        "code": "DIPHTHERIA",
        "name_en": "Diphtheria",
        "translations": {
            "ja": "ジフテリア",
            "en": "Diphtheria",
            "de": "Diphtherie",
            "zh-hans": "白喉",
        },
    },
    {
        "code": "TETANUS",
        "name_en": "Tetanus",
        "translations": {
            "ja": "破傷風",
            "en": "Tetanus",
            "de": "Tetanus",
            "zh-hans": "破伤风",
        },
    },
    {
        "code": "PERTUSSIS",
        "name_en": "Pertussis",
        "translations": {
            "ja": "百日咳",
            "en": "Pertussis",
            "de": "Pertussis",
            "zh-hans": "百日咳",
        },
    },
    {
        "code": "POLIO",
        "name_en": "Polio",
        "translations": {
            "ja": "ポリオ",
            "en": "Polio",
            "de": "Poliomyelitis",
            "zh-hans": "脊髓灰质炎",
        },
    },
    {
        "code": "HIB",
        "name_en": "Haemophilus influenzae type b",
        "translations": {
            "ja": "Hib感染症",
            "en": "Haemophilus influenzae type b (Hib)",
            "de": "Haemophilus influenzae Typ b (Hib)",
            "zh-hans": "b型流感嗜血杆菌（Hib）",
        },
    },
    {
        "code": "PNEUMOCOCCAL",
        "name_en": "Pneumococcal disease",
        "translations": {
            "ja": "肺炎球菌感染症",
            "en": "Pneumococcal disease",
            "de": "Pneumokokken-Erkrankung",
            "zh-hans": "肺炎球菌感染症",
        },
    },
    {
        "code": "ROTAVIRUS",
        "name_en": "Rotavirus",
        "translations": {
            "ja": "ロタウイルス",
            "en": "Rotavirus",
            "de": "Rotavirus",
            "zh-hans": "轮状病毒",
        },
    },
    {
        "code": "MEASLES",
        "name_en": "Measles",
        "translations": {
            "ja": "麻疹",
            "en": "Measles",
            "de": "Masern",
            "zh-hans": "麻疹",
        },
    },
    {
        "code": "MUMPS",
        "name_en": "Mumps",
        "translations": {
            "ja": "おたふくかぜ",
            "en": "Mumps",
            "de": "Mumps",
            "zh-hans": "流行性腮腺炎",
        },
    },
    {
        "code": "RUBELLA",
        "name_en": "Rubella",
        "translations": {
            "ja": "風疹",
            "en": "Rubella",
            "de": "Röteln",
            "zh-hans": "风疹",
        },
    },
    {
        "code": "VARICELLA",
        "name_en": "Varicella",
        "translations": {
            "ja": "水痘",
            "en": "Varicella",
            "de": "Varizellen",
            "zh-hans": "水痘",
        },
    },
    {
        "code": "JAPANESE_ENCEPHALITIS",
        "name_en": "Japanese encephalitis",
        "translations": {
            "ja": "日本脳炎",
            "en": "Japanese encephalitis",
            "de": "Japanische Enzephalitis",
            "zh-hans": "流行性乙型脑炎",
        },
    },
    {
        "code": "HEPATITIS_A",
        "name_en": "Hepatitis A",
        "translations": {
            "ja": "A型肝炎",
            "en": "Hepatitis A",
            "de": "Hepatitis A",
            "zh-hans": "甲型肝炎",
        },
    },
    {
        "code": "MENINGOCOCCAL",
        "name_en": "Meningococcal disease",
        "translations": {
            "ja": "髄膜炎菌感染症",
            "en": "Meningococcal disease",
            "de": "Meningokokken-Erkrankung",
            "zh-hans": "脑膜炎球菌感染症",
        },
    },
    {
        "code": "INFLUENZA",
        "name_en": "Influenza",
        "translations": {
            "ja": "インフルエンザ",
            "en": "Influenza",
            "de": "Influenza",
            "zh-hans": "流感",
        },
    },
    {
        "code": "HPV",
        "name_en": "Human papillomavirus",
        "translations": {
            "ja": "ヒトパピローマウイルス（HPV）",
            "en": "Human papillomavirus (HPV)",
            "de": "Humane Papillomaviren (HPV)",
            "zh-hans": "人乳头瘤病毒（HPV）",
        },
    },
    {
        "code": "YELLOW_FEVER",
        "name_en": "Yellow fever",
        "translations": {
            "ja": "黄熱",
            "en": "Yellow fever",
            "de": "Gelbfieber",
            "zh-hans": "黄热病",
        },
    },
    {
        "code": "RABIES",
        "name_en": "Rabies",
        "translations": {
            "ja": "狂犬病",
            "en": "Rabies",
            "de": "Tollwut",
            "zh-hans": "狂犬病",
        },
    },
    {
        "code": "TYPHOID",
        "name_en": "Typhoid fever",
        "translations": {
            "ja": "腸チフス",
            "en": "Typhoid fever",
            "de": "Typhus",
            "zh-hans": "伤寒",
        },
    },
]


PREPARATIONS = [
    {
        "code": "BCG",
        "name_en": "BCG vaccine",
        "components": ["BCG"],
        "translations": {
            "ja": "BCGワクチン",
            "en": "BCG vaccine",
            "de": "BCG-Impfstoff",
            "zh-hans": "卡介苗（BCG）",
        },
    },
    {
        "code": "HEPB",
        "name_en": "Hepatitis B vaccine",
        "components": ["HEPATITIS_B"],
        "translations": {
            "ja": "B型肝炎ワクチン",
            "en": "Hepatitis B vaccine",
            "de": "Hepatitis-B-Impfstoff",
            "zh-hans": "乙型肝炎疫苗",
        },
    },
    {
        "code": "DTAP_IPV",
        "name_en": "DTaP-IPV vaccine",
        "components": [
            "DIPHTHERIA",
            "TETANUS",
            "PERTUSSIS",
            "POLIO",
        ],
        "translations": {
            "ja": "4種混合（DTP-IPV）",
            "en": "DTaP-IPV vaccine",
            "de": "DTaP-IPV-Impfstoff",
            "zh-hans": "白喉・破伤风・百日咳・脊髓灰质炎联合疫苗",
        },
    },
    {
        "code": "DTAP_IPV_HIB",
        "name_en": "DTaP-IPV-Hib vaccine",
        "components": [
            "DIPHTHERIA",
            "TETANUS",
            "PERTUSSIS",
            "POLIO",
            "HIB",
        ],
        "translations": {
            "ja": "5種混合（DTP-IPV-Hib）",
            "en": "DTaP-IPV-Hib vaccine",
            "de": "DTaP-IPV-Hib-Impfstoff",
            "zh-hans": "五联疫苗（DTaP-IPV-Hib）",
        },
    },
    {
        "code": "DTAP_IPV_HIB_HEPB",
        "name_en": "DTaP-IPV-Hib-HepB vaccine",
        "components": [
            "DIPHTHERIA",
            "TETANUS",
            "PERTUSSIS",
            "POLIO",
            "HIB",
            "HEPATITIS_B",
        ],
        "translations": {
            "ja": "6種混合（DTP-IPV-Hib-HepB）",
            "en": "DTaP-IPV-Hib-HepB vaccine",
            "de": "DTaP-IPV-Hib-HepB-Impfstoff",
            "zh-hans": "六联疫苗（DTaP-IPV-Hib-HepB）",
        },
    },
    {
        "code": "HIB",
        "name_en": "Hib vaccine",
        "components": ["HIB"],
        "translations": {
            "ja": "Hibワクチン",
            "en": "Hib vaccine",
            "de": "Hib-Impfstoff",
            "zh-hans": "Hib疫苗",
        },
    },
    {
        "code": "IPV",
        "name_en": "Inactivated polio vaccine",
        "components": ["POLIO"],
        "translations": {
            "ja": "不活化ポリオワクチン（IPV）",
            "en": "Inactivated polio vaccine (IPV)",
            "de": "Inaktivierter Polio-Impfstoff (IPV)",
            "zh-hans": "灭活脊髓灰质炎疫苗（IPV）",
        },
    },
    {
        "code": "PNEUMOCOCCAL",
        "name_en": "Pneumococcal vaccine",
        "components": ["PNEUMOCOCCAL"],
        "translations": {
            "ja": "肺炎球菌ワクチン",
            "en": "Pneumococcal vaccine",
            "de": "Pneumokokken-Impfstoff",
            "zh-hans": "肺炎球菌疫苗",
        },
    },
    {
        "code": "ROTAVIRUS",
        "name_en": "Rotavirus vaccine",
        "components": ["ROTAVIRUS"],
        "translations": {
            "ja": "ロタウイルスワクチン",
            "en": "Rotavirus vaccine",
            "de": "Rotavirus-Impfstoff",
            "zh-hans": "轮状病毒疫苗",
        },
    },
    {
        "code": "MMR",
        "name_en": "MMR vaccine",
        "components": [
            "MEASLES",
            "MUMPS",
            "RUBELLA",
        ],
        "translations": {
            "ja": "MMRワクチン",
            "en": "MMR vaccine",
            "de": "MMR-Impfstoff",
            "zh-hans": "麻疹・腮腺炎・风疹联合疫苗（MMR）",
        },
    },
    {
        "code": "MR",
        "name_en": "Measles-rubella vaccine",
        "components": [
            "MEASLES",
            "RUBELLA",
        ],
        "translations": {
            "ja": "MRワクチン",
            "en": "Measles-rubella vaccine",
            "de": "Masern-Röteln-Impfstoff",
            "zh-hans": "麻疹・风疹联合疫苗（MR）",
        },
    },
    {
        "code": "MMRV",
        "name_en": "MMRV vaccine",
        "components": [
            "MEASLES",
            "MUMPS",
            "RUBELLA",
            "VARICELLA",
        ],
        "translations": {
            "ja": "MMRVワクチン",
            "en": "MMRV vaccine",
            "de": "MMRV-Impfstoff",
            "zh-hans": "麻疹・腮腺炎・风疹・水痘联合疫苗（MMRV）",
        },
    },
    {
        "code": "VARICELLA",
        "name_en": "Varicella vaccine",
        "components": ["VARICELLA"],
        "translations": {
            "ja": "水痘ワクチン",
            "en": "Varicella vaccine",
            "de": "Varizellen-Impfstoff",
            "zh-hans": "水痘疫苗",
        },
    },
    {
        "code": "JAPANESE_ENCEPHALITIS",
        "name_en": "Japanese encephalitis vaccine",
        "components": ["JAPANESE_ENCEPHALITIS"],
        "translations": {
            "ja": "日本脳炎ワクチン",
            "en": "Japanese encephalitis vaccine",
            "de": "Impfstoff gegen Japanische Enzephalitis",
            "zh-hans": "流行性乙型脑炎疫苗",
        },
    },
    {
        "code": "HEPA",
        "name_en": "Hepatitis A vaccine",
        "components": ["HEPATITIS_A"],
        "translations": {
            "ja": "A型肝炎ワクチン",
            "en": "Hepatitis A vaccine",
            "de": "Hepatitis-A-Impfstoff",
            "zh-hans": "甲型肝炎疫苗",
        },
    },
    {
        "code": "INFLUENZA",
        "name_en": "Influenza vaccine",
        "components": ["INFLUENZA"],
        "translations": {
            "ja": "インフルエンザワクチン",
            "en": "Influenza vaccine",
            "de": "Influenza-Impfstoff",
            "zh-hans": "流感疫苗",
        },
    },
    {
        "code": "HPV",
        "name_en": "HPV vaccine",
        "components": ["HPV"],
        "translations": {
            "ja": "HPVワクチン",
            "en": "HPV vaccine",
            "de": "HPV-Impfstoff",
            "zh-hans": "HPV疫苗",
        },
    },
    {
        "code": "MENINGOCOCCAL",
        "name_en": "Meningococcal vaccine",
        "components": ["MENINGOCOCCAL"],
        "translations": {
            "ja": "髄膜炎菌ワクチン",
            "en": "Meningococcal vaccine",
            "de": "Meningokokken-Impfstoff",
            "zh-hans": "脑膜炎球菌疫苗",
        },
    },
    {
        "code": "YELLOW_FEVER",
        "name_en": "Yellow fever vaccine",
        "components": ["YELLOW_FEVER"],
        "translations": {
            "ja": "黄熱ワクチン",
            "en": "Yellow fever vaccine",
            "de": "Gelbfieber-Impfstoff",
            "zh-hans": "黄热病疫苗",
        },
    },
    {
        "code": "RABIES",
        "name_en": "Rabies vaccine",
        "components": ["RABIES"],
        "translations": {
            "ja": "狂犬病ワクチン",
            "en": "Rabies vaccine",
            "de": "Tollwut-Impfstoff",
            "zh-hans": "狂犬病疫苗",
        },
    },
    {
        "code": "TYPHOID",
        "name_en": "Typhoid vaccine",
        "components": ["TYPHOID"],
        "translations": {
            "ja": "腸チフスワクチン",
            "en": "Typhoid vaccine",
            "de": "Typhus-Impfstoff",
            "zh-hans": "伤寒疫苗",
        },
    },
]


class Command(BaseCommand):
    help = "Create initial vaccination master data."

    def handle(self, *args, **options):
        self.seed_countries()
        self.seed_components()
        self.seed_preparations()

        self.stdout.write(
            self.style.SUCCESS(
                "Vaccination master data seeded successfully."
            )
        )

        # =====================================================
        # Vaccine products
        # =====================================================

        rotavirus_preparation = (
            VaccinePreparation.objects.get(
                code="ROTAVIRUS"
            )
        )

        VaccineProduct.objects.update_or_create(
            preparation=rotavirus_preparation,
            product_name="Rotarix",
            defaults={
                "manufacturer": "GlaxoSmithKline",
            },
        )

        VaccineProduct.objects.update_or_create(
            preparation=rotavirus_preparation,
            product_name="RotaTeq",
            defaults={
                "manufacturer": "MSD",
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Rotavirus products seeded."
            )
        )

    def seed_countries(self):
        for data in COUNTRIES:
            country, _ = Country.objects.update_or_create(
                code=data["code"],
                defaults={
                    "name_en": data["name_en"],
                },
            )

            for language_code, name in data["translations"].items():
                CountryTranslation.objects.update_or_create(
                    country=country,
                    language_code=language_code,
                    defaults={
                        "name": name,
                    },
                )

        self.stdout.write(
            f"Countries: {Country.objects.count()}"
        )

    def seed_components(self):
        for data in COMPONENTS:
            component, _ = VaccineComponent.objects.update_or_create(
                code=data["code"],
                defaults={
                    "name_en": data["name_en"],
                },
            )

            for language_code, name in data["translations"].items():
                VaccineComponentTranslation.objects.update_or_create(
                    component=component,
                    language_code=language_code,
                    defaults={
                        "name": name,
                    },
                )

        self.stdout.write(
            f"Vaccine components: {VaccineComponent.objects.count()}"
        )

    def seed_preparations(self):
        for data in PREPARATIONS:
            preparation, _ = VaccinePreparation.objects.update_or_create(
                code=data["code"],
                defaults={
                    "name_en": data["name_en"],
                },
            )

            components = VaccineComponent.objects.filter(
                code__in=data["components"]
            )

            found_codes = set(
                components.values_list(
                    "code",
                    flat=True,
                )
            )

            missing_codes = (
                set(data["components"]) - found_codes
            )

            if missing_codes:
                raise ValueError(
                    "Missing vaccine components: "
                    + ", ".join(sorted(missing_codes))
                )

            preparation.components.set(components)

            for language_code, name in data["translations"].items():
                VaccinePreparationTranslation.objects.update_or_create(
                    preparation=preparation,
                    language_code=language_code,
                    defaults={
                        "name": name,
                    },
                )

        self.stdout.write(
            f"Vaccine preparations: {VaccinePreparation.objects.count()}"
        )
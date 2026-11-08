"""「あなたに合わせる」: four questions that tailor HOME.

Answers are kept per browser on OutingsPreference (no login needed):
areas people go to, what they are interested in, how much German/French
they read, whether they go out with children (and their ages) and which
days they have off.
"""

from datetime import timedelta

from django.utils import timezone

from .models import OutingsPreference
from .regions import AREAS, REGION_CODES, clean_regions

AGE_GROUPS = [
    ("0", "0〜2歳", 0, 2),
    ("3", "3〜5歳", 3, 5),
    ("6", "6〜9歳", 6, 9),
    ("10", "10歳〜", 10, 18),
]

AREA_KEYS = [key for key, _, _ in AREAS]


def get_profile(visitor_id):
    return OutingsPreference.objects.filter(visitor_id=visitor_id).first()


def save_answers(preference, data):
    """Store the answers from the HOME card or the My page form."""
    preference.areas = [a for a in dict.fromkeys(data.getlist("areas")) if a in AREA_KEYS]
    german = data.get("german", "")
    preference.german = german if german in OutingsPreference.German.values else ""
    kids = data.get("kids", "")
    preference.with_kids = {"yes": True, "no": False}.get(kids)
    ages = [k for k, *_ in AGE_GROUPS]
    preference.kid_ages = [a for a in dict.fromkeys(data.getlist("ages")) if a in ages] if preference.with_kids else []
    days = data.get("days_off", "")
    preference.days_off = days if days in OutingsPreference.DaysOff.values else ""
    from .interests import clean
    preference.interests = clean(data.getlist("interests"))
    if "hide_went" in data:
        preference.hide_went = data.get("hide_went") == "1"
    preference.setup = OutingsPreference.Setup.DONE
    # The event list starts on these areas, like the old favourite regions.
    cantons = [code for key, _, codes in AREAS if key in preference.areas for code in codes if code in REGION_CODES]
    preference.favorite_regions = clean_regions(cantons)
    preference.personalization_enabled = True
    preference.save()


def age_range(preference):
    """(lowest, highest) age over the chosen groups, or None."""
    groups = [g for g in AGE_GROUPS if preference and g[0] in (preference.kid_ages or [])]
    if not groups:
        return None
    return min(g[2] for g in groups), max(g[3] for g in groups)


def area_cantons(preference):
    keys = set(preference.areas or []) if preference else set()
    return {code for key, _, codes in AREAS if key in keys for code in codes}


def spot_score(spot, preference):
    """Higher first: in the visitor's areas, right age, easy on language."""
    if not preference:
        return 0
    score = 0
    if spot.canton in area_cantons(preference):
        score += 2
    ages = age_range(preference)
    if ages and (spot.age_min is None or spot.age_min <= ages[1]) and (spot.age_max is None or spot.age_max >= ages[0]):
        score += 2
    if preference.german == "none" and spot.language in ("none", "little"):
        score += 1
    return score


def days_off(now, preference):
    """The days HOME plans for: this weekend, or the next weekdays."""
    today = timezone.localdate(now)
    if preference and preference.days_off == OutingsPreference.DaysOff.WEEKDAY:
        start = today if today.weekday() < 5 else today + timedelta(days=7 - today.weekday())
        return [start + timedelta(days=i) for i in range(5 - start.weekday())]
    from .services import weather
    return weather.weekend_days(now)


def wants_kids(preference):
    """None when unknown, so the app stays family-first by default."""
    return preference.with_kids if preference else None

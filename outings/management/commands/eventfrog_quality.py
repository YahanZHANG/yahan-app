"""Conservative, zero-API-cost Eventfrog relevance/language gate.

PASS -> eligible for translation, HOLD -> keep without translating, SKIP -> do not translate.
The gate does not certify event factual accuracy or language accessibility.
"""
import re
import unicodedata


def norm(s):
    return unicodedata.normalize('NFKC', str(s or '')).casefold()


def anyhit(text, phrases):
    return any(p in text for p in phrases)


# Evaluate titles first: descriptions contain many incidental keywords.
ACTIVE_TITLE = (
    'atelier', 'workshop', 'basteln', 'bastel', 'malen', 'kreativ', 'töpfer',
    'keramik', 'kunst für kinder', 'fossilien', 'experiment', 'entdecken',
    'mitmach', 'familienführung', 'familienatelier', 'kinderführung',
    'familienworkshop', 'children', 'kids', 'kindermuseum', 'ferienpass',
    'herbstferien', 'natur entdecken', 'spielplatz', 'zirkus', 'circus',
    'japanisch', 'japan', 'japanese', 'sushi', 'origami', 'manga', 'anime',
    'kimono', 'bonsai', 'japanreise', 'japon', 'japonais',
    'ausstellung', 'exhibition', 'exposition', 'museum', 'vernissage',
    'festival', 'fest', 'markt', 'messe', 'open day', 'offene tür',
    'tag der offenen tür', 'konzert', 'concert', 'cinema', 'kino',
    'theater', 'spectacle', 'exkursion', 'führung', 'visite', 'wanderung',
    'führung', 'kinder', 'familie', 'family', 'enfants', 'famille',
)
VISUAL_TITLE = ('ausstellung', 'museum', 'exhibition', 'exposition', 'vernissage',
                'kunst', 'galerie', 'atelier', 'bastel', 'malen', 'keramik',
                'fossilien', 'experiment', 'zirkus', 'circus', 'festival',
                'markt', 'concert', 'konzert')

# Strong evidence for heavy language participation; only applied to title, or explicit requirements.
LANGUAGE_HEAVY_TITLE = (
    'lesegruppe', 'lesekreis', 'literaturkreis', 'schreibwerkstatt',
    'schreibkurs', 'dialektkurs', 'mundart', 'alte schriften',
    'kurrentschrift', 'deutschprüfung', 'französischprüfung', 'sprachprüfung',
    'philosophischer salon', 'philosophiegespräch', 'diskussionsrunde',
    'debatte', 'podiumsdiskussion', 'vortragsreihe', 'fachvortrag',
    'wissenschaftlicher vortrag', 'literaturlesung', 'buchbesprechung',
    'literaturgespräch', 'lecture littéraire', 'club de lecture',
    'atelier d’écriture', 'conférence spécialisée', 'table ronde',
    'discussion philosophique',
)
REQUIREMENTS = (
    'deutschkenntnisse b2', 'deutschkenntnisse c1', 'deutschkenntnisse c2',
    'französischkenntnisse b2', 'französischkenntnisse c1',
    'niveau b2', 'niveau c1', 'niveau c2', 'fließend deutsch',
    'fliessend deutsch', 'gute deutschkenntnisse erforderlich',
    'gute französischkenntnisse erforderlich', 'sprachkenntnisse vorausgesetzt',
    'erfordert gute deutschkenntnisse', 'german proficiency required',
    'advanced german required', 'advanced french required',
)
# Story/listening-heavy events do not always require advanced proficiency.
STORY_TITLE = ('bilderbuch', 'geschichtli', 'gschichtli', 'vorlesen', 'lesung',
               'märchenstunde', 'erzähl', 'storytime', 'contes', 'lecture',
               'bibliotheksgeschichten', 'buchkino')

LOW_VALUE_TITLE = (
    'business networking', 'investment seminar', 'immobilienberatung',
    'vertriebsseminar', 'recruiting', 'sales webinar', 'crypto trading',
    'marketing masterclass', 'network marketing', 'multi-level-marketing',
    'steueroptimierung für unternehmer',
)


def evaluate(row):
    title = norm(row.get('title'))
    description = norm(row.get('description'))[:4000]
    topics = norm(row.get('matched_topics'))
    score = int(row.get('score') or 0)
    if anyhit(title, LOW_VALUE_TITLE):
        return 'SKIP', '商業的・専門的な催しで一般的な日本語住民向けではない'
    if anyhit(title, LANGUAGE_HEAVY_TITLE) or anyhit(description, REQUIREMENTS):
        return 'SKIP', '高度な言語能力・専門的な読解や討論が必要な可能性が高い'
    if anyhit(title, STORY_TITLE):
        # Could be valuable for bilingual families; keep for future assessment.
        return 'HOLD', '読み聞かせ・朗読中心。参加言語が明確になるまでAI翻訳を保留'
    visual = anyhit(title, VISUAL_TITLE)
    positive = anyhit(title, ACTIVE_TITLE)
    if not positive:
        return 'HOLD', 'タイトルから活動内容と日本語利用者への価値を確定できない'
    if anyhit(title, ('japan', 'japanisch', 'japanese', 'japon', 'origami', 'manga', 'anime', 'sushi', 'kimono')):
        return 'PASS', 'タイトルに日本・日本文化の要素が明示されている'
    if visual:
        return 'PASS', '鑑賞・体験中心で言語依存が比較的少ない候補'
    if anyhit(title, ('kinder', 'familie', 'family', 'enfants', 'famille', 'kids', 'ferienpass')):
        if anyhit(title, ('kurs', 'training', 'schule', 'unterricht')):
            return 'HOLD', '習い事・継続講座の可能性。言語・対象条件の確認が必要'
        return 'PASS', '家族・子ども向けの活動がタイトルに明示されている'
    return 'HOLD', '魅力はあり得るが言語負担が不確実'

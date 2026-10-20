"""
お店の住所から緯度・経度を調べる。

スイス連邦地理情報局 (swisstopo) の検索 API を使う。無料・キー不要。
https://api3.geo.admin.ch/services/sdiservices.html#search
"""

import json
import logging
import re

from urllib.parse import urlencode
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)

SEARCH_URL = "https://api3.geo.admin.ch/rest/services/api/SearchServer"


def clean_address(address):
    # 「(Hinterhof)」「（2階）」などの補足は検索のじゃまになるので外す
    return re.sub(r"[（(][^）)]*[）)]", "", address).strip()


def lookup(address, timeout=5):
    """
    住所 → (緯度, 経度)。見つからない・つながらないときは None。
    """

    query = urlencode(
        {
            "searchText": clean_address(address),
            "type": "locations",
            "origins": "address",
            "sr": "4326",
            "limit": "1",
        }
    )

    request = Request(
        f"{SEARCH_URL}?{query}",
        headers={"User-Agent": "Yapp washoku (store map)"},
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except Exception as error:
        logger.warning("住所の検索に失敗しました: %s (%s)", address, error)
        return None

    results = data.get("results") or []

    if not results:
        return None

    attrs = results[0].get("attrs", {})

    if "lat" not in attrs or "lon" not in attrs:
        return None

    return attrs["lat"], attrs["lon"]


def geocode_store(store, save=True):
    """
    お店の位置を調べて保存する。見つかれば True。
    """

    found = lookup(store.address)

    if not found:
        return False

    store.latitude, store.longitude = found

    if save:
        store.save(update_fields=["latitude", "longitude"])

    return True


def geocode_missing_stores():
    """
    位置がまだ分からないお店をまとめて調べる。見つかった件数を返す。
    """

    from .models import Store

    count = 0

    for store in Store.objects.filter(latitude__isnull=True):
        if geocode_store(store):
            count += 1

    return count

from datetime import date, timedelta
from django.db.models import Q
from .models import VaccinationRecordComponent


def sync_record_components(record):
    """
    1回の接種記録から、その製剤に含まれる成分を作成する。

    例:
    MMR
      -> Measles
      -> Mumps
      -> Rubella
    """

    component_ids = set(
        record.preparation.components.values_list(
            "id",
            flat=True,
        )
    )

    existing = {
        item.component_id: item
        for item in record.record_components.all()
    }

    # 足りない成分を追加
    for component_id in component_ids:
        if component_id not in existing:
            VaccinationRecordComponent.objects.create(
                record=record,
                component_id=component_id,
            )

    # 製剤を変更した場合に不要になった成分を削除
    record.record_components.exclude(
        component_id__in=component_ids
    ).delete()

    recalculate_component_dose_numbers(
        record.child,
        component_ids,
    )


def recalculate_component_dose_numbers(
    child,
    component_ids=None,
):
    """
    子どもの接種履歴を日付順に並べて、
    成分ごとの1回目、2回目、3回目...を自動計算する。

    過去の接種記録を後から追加しても、
    全履歴を再計算するので順番が崩れない。
    """

    queryset = (
        VaccinationRecordComponent.objects
        .filter(record__child=child)
        .select_related(
            "record",
            "component",
        )
        .order_by(
            "component_id",
            "record__vaccination_date",
            "record__id",
        )
    )

    if component_ids:
        queryset = queryset.filter(
            component_id__in=component_ids
        )

    counts = {}

    for item in queryset:
        component_id = item.component_id

        counts[component_id] = (
            counts.get(component_id, 0) + 1
        )

        dose_number = counts[component_id]

        if item.dose_number != dose_number:
            item.dose_number = dose_number
            item.save(
                update_fields=["dose_number"]
            )


def get_schedule_item_status(
    child,
    item,
):
    """
    スケジュール項目の状態を返す。

    done
        接種記録あり

    next
        現在が標準的な接種時期

    future
        まだ標準的な時期より前

    check
        標準期間を過ぎている、
        または接種記録の確認が必要

    hidden
        製品条件などにより、
        この子には表示しない項目
    """

    today = date.today()

    age_days = (
        today
        - child.date_of_birth
    ).days

    required_components = list(
        item.required_components.all()
    )

    if not required_components:
        return "check"


    # =========================================================
    # 製品別シリーズ
    #
    # 例:
    #
    # Rotarixを1回目に使用
    # → Rotarix用2回目だけ表示
    #
    # RotaTeqを1回目に使用
    # → RotaTeq用2回目・3回目を表示
    # =========================================================

    applicable_product = (
        item.applies_to_product
    )

    if applicable_product:

        for component in required_components:

            first_dose = (
                VaccinationRecordComponent.objects
                .filter(
                    record__child=child,
                    component=component,
                    dose_number=1,
                )
                .select_related(
                    "record",
                    "record__product",
                )
                .order_by(
                    "record__vaccination_date",
                    "record__id",
                )
                .first()
            )

            # まだ1回目がないなら、
            # 製品別の2回目・3回目は表示しない。
            if first_dose is None:
                return "hidden"

            first_record = (
                first_dose.record
            )

            product_matches = (
                first_record.product_id
                == applicable_product.id
            )

            # 古い記録などでproduct FKがない場合は
            # product_nameでも確認する。
            if (
                not product_matches
                and first_record.product_name
            ):
                product_matches = (
                    first_record.product_name
                    .strip()
                    .casefold()
                    ==
                    applicable_product.product_name
                    .strip()
                    .casefold()
                )

            if not product_matches:
                return "hidden"


    # =========================================================
    # この回数をすでに接種済みか
    # =========================================================

    completed = True

    for component in required_components:

        queryset = (
            VaccinationRecordComponent.objects
            .filter(
                record__child=child,
                component=component,
            )
        )

        if item.dose_number:
            queryset = queryset.filter(
                dose_number=item.dose_number
            )

        # 製品指定項目なら、
        # 接種済み判定にも製品を使う。
        if applicable_product:
            queryset = queryset.filter(
                Q(
                    record__product=(
                        applicable_product
                    )
                )
                |
                Q(
                    record__product_name__iexact=(
                        applicable_product
                        .product_name
                    )
                )
            )

        if not queryset.exists():
            completed = False
            break

    if completed:
        return "done"


    # =========================================================
    # 最低年齢
    # =========================================================

    if (
        age_days
        < item.recommended_age_min_days
    ):
        return "future"


    # =========================================================
    # 接種間隔ルール
    # =========================================================

    has_interval_rule = (
        item.recommended_interval_min_days
        is not None
        or
        item.recommended_interval_max_days
        is not None
    )

    if (
        has_interval_rule
        and item.dose_number
        and item.dose_number > 1
    ):

        anchor_dose_number = (
            item
            .recommended_interval_from_dose_number
        )

        if anchor_dose_number is None:
            anchor_dose_number = (
                item.dose_number - 1
            )

        anchor_dates = []

        for component in required_components:

            anchor_queryset = (
                VaccinationRecordComponent.objects
                .filter(
                    record__child=child,
                    component=component,
                    dose_number=(
                        anchor_dose_number
                    ),
                )
            )

            if applicable_product:
                anchor_queryset = (
                    anchor_queryset.filter(
                        Q(
                            record__product=(
                                applicable_product
                            )
                        )
                        |
                        Q(
                            record__product_name__iexact=(
                                applicable_product
                                .product_name
                            )
                        )
                    )
                )

            anchor_record = (
                anchor_queryset
                .select_related(
                    "record"
                )
                .order_by(
                    "-record__vaccination_date",
                    "-record__id",
                )
                .first()
            )

            if anchor_record is None:

                # RotaTeqの3回目などは、
                # 2回目が済むまで表示しない。
                if applicable_product:
                    return "hidden"

                return "check"

            anchor_dates.append(
                anchor_record
                .record
                .vaccination_date
            )


        # -----------------------------------------------------
        # 最短間隔
        # -----------------------------------------------------

        min_interval = (
            item.recommended_interval_min_days
            or 0
        )

        earliest_date = max(
            anchor_date
            + timedelta(
                days=min_interval
            )
            for anchor_date
            in anchor_dates
        )

        if today < earliest_date:
            return "future"


        # -----------------------------------------------------
        # 最長間隔
        # -----------------------------------------------------

        if (
            item.recommended_interval_max_days
            is not None
        ):

            latest_date = min(
                anchor_date
                + timedelta(
                    days=(
                        item
                        .recommended_interval_max_days
                    )
                )
                for anchor_date
                in anchor_dates
            )

            if today > latest_date:
                return "check"


        # -----------------------------------------------------
        # 年齢上限
        # -----------------------------------------------------

        if (
            item.recommended_age_max_days
            is not None
            and age_days
            > item.recommended_age_max_days
        ):
            return "check"

        return "next"


    # =========================================================
    # 通常の年齢判定
    # =========================================================

    if (
        item.recommended_age_max_days
        is None
        or age_days
        <= item.recommended_age_max_days
    ):
        return "next"

    return "check"
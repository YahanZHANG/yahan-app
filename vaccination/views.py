from datetime import date
from .i18n import get_ui, t

from django.conf import settings as django_settings
from django.contrib.auth.decorators import login_required
from django.db import models
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone

from .forms import (
    ChildForm,
    VaccinationRecordForm,
    VaccinationSettingsForm,
)
from .models import (
    Child,
    CountryScheduleVersion,
    HealthcareProvider,
    VaccinationRecord,
    VaccinationRecordComponent,
    VaccinationSettings,
    VaccineComponent,
)

from .services import (
    get_schedule_item_status,
    sync_record_components,
)


def get_vaccination_settings(user):
    settings_obj, _ = (
        VaccinationSettings.objects
        .get_or_create(
            user=user,
        )
    )

    return settings_obj


def get_current_child(user):
    settings_obj = get_vaccination_settings(
        user
    )

    if settings_obj.active_child_id:

        child = (
            Child.objects
            .filter(
                owner=user,
                pk=settings_obj.active_child_id,
            )
            .first()
        )

        if child:
            return child

    child = (
        Child.objects
        .filter(owner=user)
        .order_by(
            "date_of_birth",
            "id",
        )
        .first()
    )

    if child:
        settings_obj.active_child = child
        settings_obj.save(
            update_fields=[
                "active_child"
            ]
        )

    return child


@login_required
def home(request):
    settings_obj = get_vaccination_settings(
        request.user
    )

    child = get_current_child(
        request.user
    )

    if child is None:
        return redirect(
            "vaccination:child_create"
        )

    current_country = (
        settings_obj.current_country
        or child.default_country
    )

    language_code = (
        settings_obj.ui_language
        or "ja"
    )

    current_country_name = None

    if current_country:
        current_country_name = (
            current_country.get_name(
                language_code
            )
        )

    recent_records = (
        VaccinationRecord.objects
        .filter(child=child)
        .select_related(
            "preparation",
            "country",
        )
        .order_by(
            "-vaccination_date",
            "-id",
        )[:2]
    )

    recent_rows = []

    for record in recent_records:
        recent_rows.append(
            {
                "record": record,
                "name": (
                    record.preparation.get_name(
                        language_code
                    )
                ),
            }
        )

    return render(
        request,
        "vaccination/home.html",
        {
            "child": child,
            "settings_obj": settings_obj,
            "current_country": current_country,
            "current_country_name": current_country_name,
            "recent_rows": recent_rows,
        },
    )

@login_required
def child_create(request):
    settings_obj = (
        get_vaccination_settings(
            request.user
        )
    )

    language_code = (
        settings_obj.ui_language
        or "ja"
    )

    if request.method == "POST":

        form = ChildForm(
            request.POST,
        )

        if form.is_valid():

            child = form.save(
                commit=False
            )

            child.owner = (
                request.user
            )

            child.save()

            # ---------------------------------------------
            # 新しく追加した子を選択状態にする
            # ---------------------------------------------

            settings_obj.active_child = child

            update_fields = [
                "active_child"
            ]

            # 国がまだ設定されていない場合
            if (
                settings_obj.current_country
                is None
                and child.default_country
            ):
                settings_obj.current_country = (
                    child.default_country
                )

                update_fields.append(
                    "current_country"
                )

            settings_obj.save(
                update_fields=update_fields
            )

            return redirect(
                "vaccination:home"
            )

    else:

        form = ChildForm()

    return render(
        request,
        "vaccination/child_form.html",
        {
            "form": form,
            "language_code": language_code,
        },
    )


@login_required
def children(request):
    settings_obj = (
        get_vaccination_settings(
            request.user
        )
    )

    child_list = (
        Child.objects
        .filter(
            owner=request.user
        )
        .select_related(
            "birth_country",
            "default_country",
        )
        .order_by(
            "date_of_birth",
            "id",
        )
    )

    return render(
        request,
        "vaccination/children.html",
        {
            "children": child_list,
            "active_child": (
                settings_obj.active_child
            ),
        },
    )

@login_required
def child_switch(
    request,
    pk,
):
    child = get_object_or_404(
        Child,
        pk=pk,
        owner=request.user,
    )

    settings_obj = (
        get_vaccination_settings(
            request.user
        )
    )

    settings_obj.active_child = child

    settings_obj.save(
        update_fields=[
            "active_child"
        ]
    )

    return redirect(
        "vaccination:home"
    )

@login_required
def record_create(request):
    settings_obj = get_vaccination_settings(
        request.user
    )

    child = get_current_child(
        request.user
    )

    if child is None:
        return redirect(
            "vaccination:child_create"
        )

    language_code = (
        settings_obj.ui_language
        or "ja"
    )

    default_country = (
        settings_obj.current_country
        or child.default_country
    )

    if request.method == "POST":
        form = VaccinationRecordForm(
            request.POST,
            user=request.user,
            language_code=language_code,
        )

        if form.is_valid():
            record = form.save(
                commit=False
            )

            record.child = child

            record.reaction_codes = (
                form.cleaned_data.get(
                    "reactions",
                    [],
                )
            )

            new_provider_name = (
                form.cleaned_data.get(
                    "new_provider_name",
                    ""
                ).strip()
            )

            new_provider_city = (
                form.cleaned_data.get(
                    "new_provider_city",
                    ""
                ).strip()
            )

            if new_provider_name:
                provider = (
                    HealthcareProvider.objects
                    .filter(
                        owner=request.user,
                        name__iexact=new_provider_name,
                    )
                    .first()
                )

                if provider is None:
                    provider = (
                        HealthcareProvider.objects
                        .create(
                            owner=request.user,
                            name=new_provider_name,
                            city=new_provider_city,
                            country=record.country,
                        )
                    )

                record.healthcare_provider = (
                    provider
                )

            record.save()

            sync_record_components(
                record
            )

            if record.healthcare_provider:
                provider = (
                    record.healthcare_provider
                )

                provider.last_used_at = (
                    timezone.now()
                )

                provider.save(
                    update_fields=[
                        "last_used_at"
                    ]
                )

            return redirect(
                "vaccination:home"
            )

    else:
        form = VaccinationRecordForm(
            user=request.user,
            language_code=language_code,
            initial={
                "vaccination_date": date.today(),
                "country": default_country,
            },
        )

    return render(
        request,
        "vaccination/record_form.html",
        {
            "form": form,
            "child": child,
        },
    )


@login_required
def records(request):
    settings_obj = get_vaccination_settings(
        request.user
    )

    child = get_current_child(
        request.user
    )

    if child is None:
        return redirect(
            "vaccination:child_create"
        )

    language_code = (
        settings_obj.ui_language
        or "ja"
    )

    view_mode = request.GET.get(
        "view",
        "component",
    )

    # --------------------------------------------------
    # 接種日順
    # --------------------------------------------------

    vaccination_records = (
        VaccinationRecord.objects
        .filter(child=child)
        .select_related(
            "preparation",
            "country",
            "healthcare_provider",
        )
        .prefetch_related(
            "preparation__translations",
            "country__translations",
        )
        .order_by(
            "-vaccination_date",
            "-id",
        )
    )

    history_rows = []

    for record in vaccination_records:

        country_name = None

        if record.country:
            country_name = record.country.get_name(
                language_code
            )

        history_rows.append(
            {
                "record": record,
                "name": (
                    record.preparation.get_name(
                        language_code
                    )
                ),
                "country_name": country_name,
            }
        )

    # --------------------------------------------------
    # ワクチン成分別
    # --------------------------------------------------

    component_records = (
        VaccinationRecordComponent.objects
        .filter(
            record__child=child
        )
        .select_related(
            "component",
            "record",
        )
        .prefetch_related(
            "component__translations",
        )
        .order_by(
            "component__name_en",
            "-record__vaccination_date",
        )
    )

    grouped_components = {}

    for item in component_records:

        component = item.component

        if component.id not in grouped_components:

            grouped_components[component.id] = {
                "component": component,
                "name": component.get_name(
                    language_code
                ),
                "count": 0,
                "latest_date": None,
                "latest_dose_number": None,
            }

        row = grouped_components[
            component.id
        ]

        row["count"] += 1

        if (
            row["latest_date"] is None
            or item.record.vaccination_date
            > row["latest_date"]
        ):
            row["latest_date"] = (
                item.record.vaccination_date
            )

            row["latest_dose_number"] = (
                item.dose_number
            )

    component_rows = sorted(
        grouped_components.values(),
        key=lambda row: row["name"],
    )

    return render(
        request,
        "vaccination/records.html",
        {
            "child": child,
            "view_mode": view_mode,
            "history_rows": history_rows,
            "component_rows": component_rows,
        },
    )

@login_required
def record_detail(request, pk):
    settings_obj = get_vaccination_settings(
        request.user
    )

    language_code = (
        settings_obj.ui_language
        or "ja"
    )

    record = get_object_or_404(
        VaccinationRecord.objects
        .select_related(
            "child",
            "preparation",
            "country",
            "healthcare_provider",
            "product",
        )
        .prefetch_related(
            "record_components__component",
            "record_components__component__translations",
        ),
        pk=pk,
        child__owner=request.user,
    )

    preparation_name = (
        record.preparation.get_name(
            language_code
        )
    )

    country_name = None

    if record.country:
        country_name = (
            record.country.get_name(
                language_code
            )
        )

    component_rows = []

    for item in (
        record.record_components
        .select_related("component")
        .all()
    ):
        component_rows.append(
            {
                "name": (
                    item.component.get_name(
                        language_code
                    )
                ),
                "dose_number": (
                    item.dose_number
                ),
            }
        )

    reaction_labels = {
        "fever": t(
            "reaction_fever",
            language_code,
        ),
        "swelling": t(
            "reaction_swelling",
            language_code,
        ),
        "redness": t(
            "reaction_redness",
            language_code,
        ),
        "pain": t(
            "reaction_pain",
            language_code,
        ),
        "rash": t(
            "reaction_rash",
            language_code,
        ),
        "vomiting": t(
            "reaction_vomiting",
            language_code,
        ),
        "diarrhea": t(
            "reaction_diarrhea",
            language_code,
        ),
        "sleepiness": t(
            "reaction_sleepiness",
            language_code,
        ),
        "irritability": t(
            "reaction_irritability",
            language_code,
        ),
    }

    reactions = []

    for code in record.reaction_codes:
        reactions.append(
            reaction_labels.get(
                code,
                code,
            )
        )

    return render(
        request,
        "vaccination/record_detail.html",
        {
            "record": record,
            "preparation_name": preparation_name,
            "country_name": country_name,
            "component_rows": component_rows,
            "reactions": reactions,
        },
    )

@login_required
def component_detail(request, pk):
    settings_obj = get_vaccination_settings(
        request.user
    )

    language_code = (
        settings_obj.ui_language
        or "ja"
    )

    component = get_object_or_404(
        VaccineComponent.objects
        .filter(
            vaccination_record_components__record__child__owner=request.user
        )
        .distinct(),
        pk=pk,
    )

    component_name = component.get_name(
        language_code
    )

    component_records = (
        VaccinationRecordComponent.objects
        .filter(
            component=component,
            record__child__owner=request.user,
        )
        .select_related(
            "record",
            "record__preparation",
            "record__country",
            "record__healthcare_provider",
        )
        .prefetch_related(
            "record__preparation__translations",
            "record__country__translations",
        )
        .order_by(
            "-record__vaccination_date",
            "-record__id",
        )
    )

    rows = []

    for item in component_records:
        record = item.record

        country_name = None

        if record.country:
            country_name = record.country.get_name(
                language_code
            )

        rows.append(
            {
                "item": item,
                "record": record,
                "preparation_name": (
                    record.preparation.get_name(
                        language_code
                    )
                ),
                "country_name": country_name,
            }
        )

    return render(
        request,
        "vaccination/component_detail.html",
        {
            "component": component,
            "component_name": component_name,
            "rows": rows,
        },
    )


@login_required
def schedule(request):
    settings_obj = get_vaccination_settings(
        request.user
    )

    child = get_current_child(
        request.user
    )

    if child is None:
        return redirect(
            "vaccination:child_create"
        )

    language_code = (
        settings_obj.ui_language
        or "ja"
    )

    # ---------------------------------------------------------
    # スケジュール表示の基準国
    # ---------------------------------------------------------

    country = (
        settings_obj.current_country
        or child.default_country
    )

    country_name = None
    schedule_version = None
    schedule_groups = []

    # ---------------------------------------------------------
    # 国のスケジュールを取得
    # ---------------------------------------------------------

    if country:
        country_name = country.get_name(
            language_code
        )

        # 現在は、その国で登録されている
        # 最新のスケジュールを使用する。
        #
        # 例:
        # Switzerland -> Swiss Vaccination Plan 2026
        schedule_version = (
            CountryScheduleVersion.objects
            .filter(
                country=country,
            )
            .order_by(
                "-valid_from"
            )
            .first()
        )

    # ---------------------------------------------------------
    # スケジュール項目を作成
    # ---------------------------------------------------------

    if schedule_version:

        group_map = {}

        items = (
            schedule_version.items
            .prefetch_related(
                "required_components",
                "translations",
            )
            .order_by(
                "recommended_age_min_days",
                "sort_order",
            )
        )

        for item in items:

            # -------------------------------------------------
            # 済 / 今の時期 / 将来 / 記録確認
            #
            # 判定ロジックは services.py にまとめる。
            # 日本のような接種間隔ルールにも対応。
            # -------------------------------------------------

            status = get_schedule_item_status(
                child,
                item,
            )

            if status == "hidden":
                continue

            # -------------------------------------------------
            # スケジュール項目名を現在の言語に翻訳
            # -------------------------------------------------

            translation = (
                item.translations
                .filter(
                    language_code=language_code
                )
                .first()
            )

            if translation:
                item_name = translation.name
                item_note = translation.note
            else:
                item_name = item.name_en
                item_note = item.note

            # -------------------------------------------------
            # テンプレートへ渡す1行分
            # -------------------------------------------------

            row = {
                "item": item,
                "name": item_name,
                "note": item_note,
                "status": status,
            }

            # -------------------------------------------------
            # 年齢ごとにグループ化
            #
            # 例:
            # 2か月
            #   6種混合
            #   肺炎球菌
            #   ロタ
            #
            # 4か月
            #   ...
            # -------------------------------------------------

            group_key = (
                item.display_age
                or "Other"
            )

            if group_key not in group_map:
                group_map[group_key] = {
                    "label": group_key,
                    "rows": [],
                }

            group_map[
                group_key
            ]["rows"].append(
                row
            )

        schedule_groups = list(
            group_map.values()
        )

    # ---------------------------------------------------------
    # Template
    # ---------------------------------------------------------

    return render(
        request,
        "vaccination/schedule.html",
        {
            "child": child,
            "country": country,
            "country_name": country_name,
            "schedule_version": schedule_version,
            "schedule_groups": schedule_groups,
        },
    )


@login_required
def doctor(request):
    settings_obj = get_vaccination_settings(
        request.user
    )

    child = get_current_child(
        request.user
    )

    if child is None:
        return redirect(
            "vaccination:child_create"
        )

    doctor_language = (
        settings_obj.doctor_language
        or "en"
    )

    show_english = (
        settings_obj.doctor_show_english
        and doctor_language != "en"
    )

    doctor_ui = get_ui(
        doctor_language
    )

    # ---------------------------------------------------------
    # Current country
    # ---------------------------------------------------------

    current_country = (
        settings_obj.current_country
        or child.default_country
    )

    current_country_name = None
    current_country_name_en = None

    if current_country:

        current_country_name = (
            current_country.get_name(
                doctor_language
            )
        )

        if show_english:
            current_country_name_en = (
                current_country.get_name(
                    "en"
                )
            )

    # ---------------------------------------------------------
    # All vaccination components
    # ---------------------------------------------------------

    component_records = (
        VaccinationRecordComponent.objects
        .filter(
            record__child=child
        )
        .select_related(
            "component",
            "record",
            "record__preparation",
            "record__country",
            "record__healthcare_provider",
        )
        .prefetch_related(
            "component__translations",
            "record__preparation__translations",
            "record__country__translations",
        )
        .order_by(
            "record__vaccination_date",
            "record__id",
        )
    )

    # ---------------------------------------------------------
    # Group by vaccine component
    # ---------------------------------------------------------

    group_map = {}

    for item in component_records:

        component = item.component
        record = item.record

        if component.id not in group_map:

            component_name = (
                component.get_name(
                    doctor_language
                )
            )

            component_name_en = None

            if show_english:
                component_name_en = (
                    component.get_name(
                        "en"
                    )
                )

            group_map[
                component.id
            ] = {
                "component": component,
                "name": component_name,
                "name_en": component_name_en,
                "rows": [],
            }

        preparation_name = (
            record.preparation.get_name(
                doctor_language
            )
        )

        preparation_name_en = None

        if show_english:
            preparation_name_en = (
                record.preparation.get_name(
                    "en"
                )
            )

        country_name = None
        country_name_en = None

        if record.country:

            country_name = (
                record.country.get_name(
                    doctor_language
                )
            )

            if show_english:
                country_name_en = (
                    record.country.get_name(
                        "en"
                    )
                )

        group_map[
            component.id
        ]["rows"].append(
            {
                "dose_number": (
                    item.dose_number
                ),
                "date": (
                    record.vaccination_date
                ),
                "preparation_name": (
                    preparation_name
                ),
                "preparation_name_en": (
                    preparation_name_en
                ),
                "country_name": (
                    country_name
                ),
                "country_name_en": (
                    country_name_en
                ),
                "record": record,
            }
        )

    component_groups = list(
        group_map.values()
    )

    component_groups.sort(
        key=lambda group: (
            group["name"].lower()
        )
    )

    return render(
        request,
        "vaccination/doctor.html",
        {
            "child": child,
            "settings_obj": settings_obj,
            "doctor_language": doctor_language,
            "doctor_ui": doctor_ui,
            "show_english": show_english,
            "current_country_name": (
                current_country_name
            ),
            "current_country_name_en": (
                current_country_name_en
            ),
            "component_groups": (
                component_groups
            ),
        },
    )

@login_required
def settings_view(request):
    settings_obj = get_vaccination_settings(
        request.user
    )

    child = get_current_child(
        request.user
    )

    language_code = (
        settings_obj.ui_language
        or "ja"
    )

    if request.method == "POST":

        form = VaccinationSettingsForm(
            request.POST,
            instance=settings_obj,
            language_code=language_code,
        )

        if form.is_valid():

            saved_settings = form.save()

            # Django本体の言語設定にも反映する。
            response = redirect(
                "vaccination:settings"
            )

            response.set_cookie(
                django_settings.LANGUAGE_COOKIE_NAME,
                saved_settings.ui_language,
                max_age=60 * 60 * 24 * 365,
                samesite="Lax",
            )

            return response

    else:

        form = VaccinationSettingsForm(
            instance=settings_obj,
            language_code=language_code,
        )

    return render(
        request,
        "vaccination/settings.html",
        {
            "form": form,
            "child": child,
            "settings_obj": settings_obj,
        },
    )
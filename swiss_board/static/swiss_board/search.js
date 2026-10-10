/* =========================================================
   Swiss Board — Search Page
   ========================================================= */

document.addEventListener("DOMContentLoaded", function () {

    // -----------------------------------------------------
    // Elements
    // -----------------------------------------------------

    const categorySelect = document.getElementById(
        "sb-category"
    );

    const subcategorySelect = document.getElementById(
        "sb-subcategory"
    );

    const dataElement = document.getElementById(
        "sb-subcategory-data"
    );

    if (
        !categorySelect ||
        !subcategorySelect ||
        !dataElement
    ) {
        return;
    }

    // -----------------------------------------------------
    // Category data
    // -----------------------------------------------------

    const subcategoriesByCategory = JSON.parse(
        dataElement.textContent
    );

    const initialSubcategory =
        subcategorySelect.dataset.selected ||
        subcategorySelect.value ||
        "";

    // -----------------------------------------------------
    // Build subcategory options
    // -----------------------------------------------------

    function updateSubcategories(selectedValue = "") {

        const category = categorySelect.value;

        const subcategories =
            subcategoriesByCategory[category] || [];

        // Remove previous options
        subcategorySelect.replaceChildren();

        // Default option
        const defaultOption = document.createElement(
            "option"
        );

        defaultOption.value = "";

        const isPostForm = Boolean(
            document.getElementById("sb-create-form")
        );

        defaultOption.textContent = category
            ? (
                isPostForm
                    ? "選択してください（任意）"
                    : "すべてのサブカテゴリー"
            )
            : "先にカテゴリーを選択";

        subcategorySelect.appendChild(
            defaultOption
        );

        // Subcategory options
        subcategories.forEach(function (subcategory) {

            const option = document.createElement(
                "option"
            );

            option.value = subcategory;
            option.textContent = subcategory;

            subcategorySelect.appendChild(
                option
            );

        });

        // Enable only when a category is selected
        subcategorySelect.disabled = !category;

        // Restore selected subcategory when valid
        if (
            category &&
            subcategories.includes(selectedValue)
        ) {
            subcategorySelect.value = selectedValue;
        } else {
            subcategorySelect.value = "";
        }

    }

    // -----------------------------------------------------
    // Initial state
    // -----------------------------------------------------

    updateSubcategories(
        initialSubcategory
    );

    // -----------------------------------------------------
    // Category changed
    // -----------------------------------------------------

    categorySelect.addEventListener(
        "change",
        function () {

            // Clear old subcategory when category changes
            updateSubcategories("");

        }
    );

});
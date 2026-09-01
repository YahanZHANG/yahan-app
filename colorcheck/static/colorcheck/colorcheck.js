"use strict";


document.addEventListener("DOMContentLoaded", () => {

    /* =====================================================
       Elements
    ===================================================== */

    const video = document.getElementById("camera-video");
    const canvas = document.getElementById("camera-canvas");

    const placeholder = document.getElementById("camera-placeholder");

    const startButton = document.getElementById("start-camera-button");
    const detectButton = document.getElementById("detect-color-button");
    const stopButton = document.getElementById("stop-camera-button");

    const cameraMessage = document.getElementById("camera-message");

    const levelButtons = document.querySelectorAll(".color-level-button");
    const levelDescription = document.getElementById("level-description");

    const result = document.getElementById("color-result");
    const resultSample = document.getElementById("result-color-sample");

    const resultNameJa = document.getElementById("result-name-ja");
    const resultNameEn = document.getElementById("result-name-en");

    const resultRgb = document.getElementById("result-rgb");
    const resultHex = document.getElementById("result-hex");
    const resultLevelNote = document.getElementById("result-level-note");


    /* =====================================================
       State
    ===================================================== */

    let stream = null;

    let selectedLevel = 1;

    let lastDetectedColor = null;


    /* =====================================================
       Level descriptions
    ===================================================== */

    const levelDescriptions = {
        1: "赤・緑・その他の3つに分類する",
        2: "一般的な色名で判定する",
        3: "明るさや色の寄り方まで詳しく表示する",
    };


    /* =====================================================
       Camera
    ===================================================== */

    async function startCamera() {

        clearCameraMessage();

        if (
            !navigator.mediaDevices ||
            !navigator.mediaDevices.getUserMedia
        ) {
            showCameraError(
                "このブラウザではカメラを利用できない。"
            );
            return;
        }


        stopCameraStream();


        const constraints = {
            audio: false,

            video: {
                facingMode: {
                    ideal: "environment",
                },

                width: {
                    ideal: 1920,
                },

                height: {
                    ideal: 1080,
                },
            },
        };


        try {

            stream = await navigator.mediaDevices.getUserMedia(
                constraints
            );


            video.srcObject = stream;


            await video.play();


            placeholder.hidden = true;

            startButton.hidden = true;
            stopButton.hidden = false;

            detectButton.disabled = false;


            cameraMessage.textContent =
                "中央の照準を調べたい色に合わせて、「この色を判定」を押す。";


        } catch (error) {

            console.error(error);

            showCameraError(
                getCameraErrorMessage(error)
            );
        }
    }


    function stopCamera() {

        stopCameraStream();

        video.srcObject = null;

        placeholder.hidden = false;

        startButton.hidden = false;
        stopButton.hidden = true;

        detectButton.disabled = true;

        cameraMessage.textContent = "";
    }


    function stopCameraStream() {

        if (!stream) {
            return;
        }


        stream
            .getTracks()
            .forEach((track) => {
                track.stop();
            });


        stream = null;
    }


    function getCameraErrorMessage(error) {

        switch (error.name) {

            case "NotAllowedError":
                return "カメラへのアクセスが許可されていない。ブラウザの設定からカメラを許可してほしい。";

            case "NotFoundError":
                return "利用できるカメラが見つからなかった。";

            case "NotReadableError":
                return "カメラを利用できない。他のアプリがカメラを使用している可能性がある。";

            case "OverconstrainedError":
                return "この端末では指定したカメラ設定を利用できない。";

            default:
                return "カメラを起動できなかった。";
        }
    }


    function showCameraError(message) {

        cameraMessage.textContent = message;
        cameraMessage.classList.add("is-error");
    }


    function clearCameraMessage() {

        cameraMessage.textContent = "";
        cameraMessage.classList.remove("is-error");
    }


    /* =====================================================
       Detect center color
    ===================================================== */

    function detectColor() {

        clearCameraMessage();


        if (
            !video.videoWidth ||
            !video.videoHeight
        ) {
            showCameraError(
                "カメラ映像の準備ができていない。"
            );
            return;
        }


        /*
         * 中央付近を1ピクセルだけではなく、
         * 正方形で取得する。
         *
         * 48 × 48 pixels
         */
        const sampleSize = Math.min(
            48,
            video.videoWidth,
            video.videoHeight
        );


        canvas.width = sampleSize;
        canvas.height = sampleSize;


        const context = canvas.getContext(
            "2d",
            {
                willReadFrequently: true,
            }
        );


        const sourceX =
            (video.videoWidth - sampleSize) / 2;

        const sourceY =
            (video.videoHeight - sampleSize) / 2;


        context.drawImage(
            video,

            sourceX,
            sourceY,
            sampleSize,
            sampleSize,

            0,
            0,
            sampleSize,
            sampleSize
        );


        const imageData = context.getImageData(
            0,
            0,
            sampleSize,
            sampleSize
        );


        const color = getRepresentativeColor(
            imageData.data
        );


        lastDetectedColor = color;


        updateResult(color);
    }


    /*
     * 平均値ではなく中央値を採用する。
     *
     * 光の反射や1〜2ピクセルのノイズの影響を
     * 少し受けにくくするため。
     */
    function getRepresentativeColor(pixelData) {

        const redValues = [];
        const greenValues = [];
        const blueValues = [];


        /*
         * 全ピクセルを使う必要はないため、
         * 4ピクセルおきに取得して軽量化する。
         */
        for (
            let i = 0;
            i < pixelData.length;
            i += 16
        ) {

            const alpha = pixelData[i + 3];


            if (alpha < 200) {
                continue;
            }


            redValues.push(pixelData[i]);
            greenValues.push(pixelData[i + 1]);
            blueValues.push(pixelData[i + 2]);
        }


        return {
            r: median(redValues),
            g: median(greenValues),
            b: median(blueValues),
        };
    }


    function median(values) {

        if (!values.length) {
            return 0;
        }


        const sorted = [...values].sort(
            (a, b) => a - b
        );


        const middle = Math.floor(
            sorted.length / 2
        );


        if (sorted.length % 2 === 0) {

            return Math.round(
                (
                    sorted[middle - 1] +
                    sorted[middle]
                ) / 2
            );
        }


        return sorted[middle];
    }


    /* =====================================================
       Result
    ===================================================== */

    function updateResult(color) {

        const colorName = getColorName(
            color,
            selectedLevel
        );


        const hex = rgbToHex(
            color.r,
            color.g,
            color.b
        );


        resultNameJa.textContent = colorName.ja;
        resultNameEn.textContent = colorName.en;

        resultRgb.textContent =
            `${color.r}, ${color.g}, ${color.b}`;

        resultHex.textContent = hex;

        resultSample.style.backgroundColor = hex;


        resultLevelNote.textContent =
            getResultLevelNote(selectedLevel);


        result.hidden = false;
    }


    function getResultLevelNote(level) {

        if (level === 1) {
            return "Level 1：赤・緑を識別するための簡易分類";
        }


        if (level === 2) {
            return "Level 2：一般的な色名による分類";
        }


        return "Level 3：色相・明るさ・彩度を組み合わせた詳細分類";
    }


    /* =====================================================
       Color name router
    ===================================================== */

    function getColorName(color, level) {

        const hsl = rgbToHsl(
            color.r,
            color.g,
            color.b
        );


        if (level === 1) {
            return getLevel1ColorName(hsl);
        }


        if (level === 2) {
            return getLevel2ColorName(hsl);
        }


        return getLevel3ColorName(hsl);
    }


    /* =====================================================
       LEVEL 1
       Red / Green / Other
    ===================================================== */

    function getLevel1ColorName(hsl) {

        const {
            h,
            s,
            l,
        } = hsl;


        /*
         * 白・黒・グレーなど、
         * 色味が極端に少ない場合は「その他」。
         */
        if (
            s < 18 ||
            l < 8 ||
            l > 94
        ) {
            return {
                ja: "その他",
                en: "Other",
            };
        }


        /*
         * 赤系
         *
         * 赤、ピンク、赤紫、
         * 暗い赤などを含める。
         */
        if (
            h >= 330 ||
            h < 25
        ) {
            return {
                ja: "赤",
                en: "Red",
            };
        }


        /*
         * 緑系
         *
         * 黄緑〜青緑まである程度広めに取る。
         */
        if (
            h >= 70 &&
            h < 175
        ) {
            return {
                ja: "緑",
                en: "Green",
            };
        }


        return {
            ja: "その他",
            en: "Other",
        };
    }


    /* =====================================================
       LEVEL 2
       Standard color names
    ===================================================== */

    function getLevel2ColorName(hsl) {

        const {
            h,
            s,
            l,
        } = hsl;


        /*
         * Neutral colors
         */

        if (l <= 10) {
            return {
                ja: "黒",
                en: "Black",
            };
        }


        if (
            s <= 10 &&
            l >= 90
        ) {
            return {
                ja: "白",
                en: "White",
            };
        }


        if (s <= 13) {
            return {
                ja: "灰色",
                en: "Gray",
            };
        }


        /*
         * Beige / brown
         */

        if (
            h >= 20 &&
            h < 55 &&
            s < 55 &&
            l >= 68
        ) {
            return {
                ja: "ベージュ",
                en: "Beige",
            };
        }


        if (
            h >= 15 &&
            h < 50 &&
            l < 48
        ) {
            return {
                ja: "茶色",
                en: "Brown",
            };
        }


        /*
         * Chromatic colors
         */

        if (
            h >= 345 ||
            h < 12
        ) {

            if (l >= 72) {
                return {
                    ja: "ピンク",
                    en: "Pink",
                };
            }


            return {
                ja: "赤",
                en: "Red",
            };
        }


        if (
            h >= 12 &&
            h < 38
        ) {
            return {
                ja: "オレンジ",
                en: "Orange",
            };
        }


        if (
            h >= 38 &&
            h < 65
        ) {
            return {
                ja: "黄色",
                en: "Yellow",
            };
        }


        if (
            h >= 65 &&
            h < 100
        ) {
            return {
                ja: "黄緑",
                en: "Yellow Green",
            };
        }


        if (
            h >= 100 &&
            h < 155
        ) {
            return {
                ja: "緑",
                en: "Green",
            };
        }


        if (
            h >= 155 &&
            h < 190
        ) {
            return {
                ja: "青緑",
                en: "Teal",
            };
        }


        if (
            h >= 190 &&
            h < 215
        ) {

            if (l >= 65) {
                return {
                    ja: "水色",
                    en: "Light Blue",
                };
            }


            return {
                ja: "青",
                en: "Blue",
            };
        }


        if (
            h >= 215 &&
            h < 255
        ) {
            return {
                ja: "青",
                en: "Blue",
            };
        }


        if (
            h >= 255 &&
            h < 290
        ) {
            return {
                ja: "紫",
                en: "Purple",
            };
        }


        if (
            h >= 290 &&
            h < 345
        ) {

            if (l >= 65) {
                return {
                    ja: "ピンク",
                    en: "Pink",
                };
            }


            return {
                ja: "紫",
                en: "Purple",
            };
        }


        return {
            ja: "その他",
            en: "Other",
        };
    }


    /* =====================================================
       LEVEL 3
       Detailed natural-language names
    ===================================================== */

    function getLevel3ColorName(hsl) {

        const {
            h,
            s,
            l,
        } = hsl;


        /*
         * Neutral colors
         */

        if (l <= 7) {
            return {
                ja: "ほぼ黒",
                en: "Almost Black",
            };
        }


        if (
            s <= 7 &&
            l >= 94
        ) {
            return {
                ja: "ほぼ白",
                en: "Almost White",
            };
        }


        if (s <= 10) {

            if (l >= 72) {
                return {
                    ja: "明るい灰色",
                    en: "Light Gray",
                };
            }


            if (l <= 32) {
                return {
                    ja: "暗い灰色",
                    en: "Dark Gray",
                };
            }


            return {
                ja: "灰色",
                en: "Gray",
            };
        }


        const baseColor =
            getDetailedBaseColor(h);


        const lightness =
            getLightnessDescription(l);


        const saturation =
            getSaturationDescription(s);


        const jaParts = [];
        const enParts = [];


        if (saturation.ja) {
            jaParts.push(saturation.ja);
        }


        if (lightness.ja) {
            jaParts.push(lightness.ja);
        }


        jaParts.push(baseColor.ja);


        if (saturation.en) {
            enParts.push(saturation.en);
        }


        if (lightness.en) {
            enParts.push(lightness.en);
        }


        enParts.push(baseColor.en);


        return {
            ja: jaParts.join(""),
            en: enParts.join(" "),
        };
    }


    function getDetailedBaseColor(h) {

        /*
         * Level 3では境界部分に
         * 「〜に近い」「〜がかった」を入れる。
         */

        if (
            h >= 350 ||
            h < 8
        ) {
            return {
                ja: "赤",
                en: "Red",
            };
        }


        if (h < 20) {
            return {
                ja: "オレンジに近い赤",
                en: "Orange Red",
            };
        }


        if (h < 35) {
            return {
                ja: "赤に近いオレンジ",
                en: "Red Orange",
            };
        }


        if (h < 48) {
            return {
                ja: "黄色に近いオレンジ",
                en: "Yellow Orange",
            };
        }


        if (h < 62) {
            return {
                ja: "黄色",
                en: "Yellow",
            };
        }


        if (h < 82) {
            return {
                ja: "黄色に近い黄緑",
                en: "Yellowish Green",
            };
        }


        if (h < 105) {
            return {
                ja: "黄緑",
                en: "Yellow Green",
            };
        }


        if (h < 145) {
            return {
                ja: "緑",
                en: "Green",
            };
        }


        if (h < 170) {
            return {
                ja: "青に近い緑",
                en: "Bluish Green",
            };
        }


        if (h < 190) {
            return {
                ja: "青緑",
                en: "Teal",
            };
        }


        if (h < 210) {
            return {
                ja: "緑に近い青",
                en: "Greenish Blue",
            };
        }


        if (h < 245) {
            return {
                ja: "青",
                en: "Blue",
            };
        }


        if (h < 265) {
            return {
                ja: "紫に近い青",
                en: "Purplish Blue",
            };
        }


        if (h < 285) {
            return {
                ja: "青に近い紫",
                en: "Bluish Purple",
            };
        }


        if (h < 310) {
            return {
                ja: "紫",
                en: "Purple",
            };
        }


        if (h < 330) {
            return {
                ja: "赤に近い紫",
                en: "Reddish Purple",
            };
        }


        if (h < 350) {
            return {
                ja: "紫に近い赤",
                en: "Purplish Red",
            };
        }


        return {
            ja: "赤",
            en: "Red",
        };
    }


    function getLightnessDescription(lightness) {

        if (lightness >= 85) {
            return {
                ja: "とても薄い",
                en: "Very Light",
            };
        }


        if (lightness >= 70) {
            return {
                ja: "明るい",
                en: "Light",
            };
        }


        if (lightness <= 22) {
            return {
                ja: "とても暗い",
                en: "Very Dark",
            };
        }


        if (lightness <= 38) {
            return {
                ja: "暗い",
                en: "Dark",
            };
        }


        return {
            ja: "",
            en: "",
        };
    }


    function getSaturationDescription(saturation) {

        if (saturation <= 20) {
            return {
                ja: "灰色がかった",
                en: "Grayish",
            };
        }


        if (saturation <= 38) {
            return {
                ja: "落ち着いた",
                en: "Muted",
            };
        }


        if (saturation >= 82) {
            return {
                ja: "鮮やかな",
                en: "Vivid",
            };
        }


        return {
            ja: "",
            en: "",
        };
    }


    /* =====================================================
       RGB -> HSL
    ===================================================== */

    function rgbToHsl(r, g, b) {

        r /= 255;
        g /= 255;
        b /= 255;


        const max = Math.max(r, g, b);
        const min = Math.min(r, g, b);

        const delta = max - min;


        let h = 0;
        let s = 0;

        const l =
            (max + min) / 2;


        if (delta !== 0) {

            if (max === r) {

                h =
                    60 *
                    (
                        (
                            (g - b) /
                            delta
                        ) % 6
                    );

            } else if (max === g) {

                h =
                    60 *
                    (
                        (
                            (b - r) /
                            delta
                        ) + 2
                    );

            } else {

                h =
                    60 *
                    (
                        (
                            (r - g) /
                            delta
                        ) + 4
                    );
            }


            s =
                delta /
                (
                    1 -
                    Math.abs(
                        (2 * l) - 1
                    )
                );
        }


        if (h < 0) {
            h += 360;
        }


        return {
            h,
            s: s * 100,
            l: l * 100,
        };
    }


    /* =====================================================
       RGB -> HEX
    ===================================================== */

    function rgbToHex(r, g, b) {

        return (
            "#" +
            componentToHex(r) +
            componentToHex(g) +
            componentToHex(b)
        ).toUpperCase();
    }


    function componentToHex(value) {

        return value
            .toString(16)
            .padStart(2, "0");
    }


    /* =====================================================
       Level selector
    ===================================================== */

    levelButtons.forEach((button) => {

        button.addEventListener(
            "click",
            () => {

                selectedLevel = Number(
                    button.dataset.level
                );


                levelButtons.forEach(
                    (item) => {

                        const isSelected =
                            item === button;


                        item.classList.toggle(
                            "is-active",
                            isSelected
                        );


                        item.setAttribute(
                            "aria-pressed",
                            String(isSelected)
                        );
                    }
                );


                levelDescription.textContent =
                    levelDescriptions[selectedLevel];


                /*
                 * すでに色を取得済みなら、
                 * カメラを撮り直さず
                 * 色名だけ更新する。
                 */
                if (lastDetectedColor) {
                    updateResult(
                        lastDetectedColor
                    );
                }
            }
        );
    });


    /* =====================================================
       Events
    ===================================================== */

    startButton.addEventListener(
        "click",
        startCamera
    );


    stopButton.addEventListener(
        "click",
        stopCamera
    );


    detectButton.addEventListener(
        "click",
        detectColor
    );


    /*
     * ページ移動時にカメラを停止する。
     */
    window.addEventListener(
        "pagehide",
        stopCameraStream
    );
});
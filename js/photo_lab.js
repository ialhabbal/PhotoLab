/**
 * photo_lab.js
 *
 * ComfyUI frontend extension for the PhotoLab node.
 *
 * Features
 * --------
 *  - ↺ Reset to Defaults
 *  - Collapsible sections for Global Effects, Lighting Match, and Face Skin Effects
 *  - Built-in Global and Face preset buttons (within collapsible sections)
 *  - User presets saved to localStorage — persist across sessions
 *    · Each user preset has its own Apply button + a separate ✕ Delete button
 *    · Active preset is highlighted with a ● marker
 */

import { app } from "/scripts/app.js";

// ─── Default widget values ────────────────────────────────────────────────────
const WIDGET_DEFAULTS = {
    quality:                 70,
    passes:                  1,
    pixelate_strength:       0,
    grain_strength:          5,
    vignette_strength:       0,
    color_grade:             "Faded",
    color_grade_strength:    50,
    saturation:              70,
    blur_type:               "None",
    blur_strength:           0,
    lighting_match_mode:     "Disabled",
    lighting_match_strength: 1.0,
    mask_mode:               "Face Only",
    pores_strength:          0,
    blemishes_strength:      0,
    acne_strength:           0,
    freckles_strength:       0,
    skin_texture_strength:   0,
    sss_strength:            0,
    peach_fuzz_strength:     0,
    skin_redness_strength:   0,
    sebum_shine_strength:    0,
    skin_seed:               0,
    pores_opacity:           100,
    blemishes_opacity:       100,
    acne_opacity:            100,
    freckles_opacity:        100,
    skin_texture_opacity:    100,
};

// ─── Built-in presets ─────────────────────────────────────────────────────────
const GLOBAL_PRESETS = [
    {
        label: "📷 Film Snapshot",
        desc:  "Faded warm tones, grain, soft vignette — classic point-and-shoot feel.",
        values: { quality:65, passes:2, grain_strength:18, vignette_strength:22,
                  color_grade:"Warm", color_grade_strength:55, saturation:80,
                  blur_type:"None", blur_strength:0 },
    },
    {
        label: "🎞 Darkroom B&W",
        desc:  "Desaturated, high-contrast with heavy grain — analogue darkroom aesthetic.",
        values: { quality:80, passes:1, grain_strength:30, vignette_strength:35,
                  color_grade:"Faded", color_grade_strength:70, saturation:0,
                  blur_type:"None", blur_strength:0 },
    },
    {
        label: "❄️ Cool Editorial",
        desc:  "Crisp cool tones, minimal grain — modern editorial / fashion look.",
        values: { quality:90, passes:1, grain_strength:6, vignette_strength:10,
                  color_grade:"Cool", color_grade_strength:45, saturation:88,
                  blur_type:"None", blur_strength:0 },
    },
    {
        label: "🟤 Sepia Vintage",
        desc:  "Full sepia with soft vignette and light compression artifacts.",
        values: { quality:65, passes:2, grain_strength:14, vignette_strength:28,
                  color_grade:"Sepia", color_grade_strength:90, saturation:60,
                  blur_type:"None", blur_strength:0 },
    },
    {
        label: "🌅 Golden Hour",
        desc:  "Rich warm saturation boost — sunset / golden hour atmosphere.",
        values: { quality:85, passes:1, grain_strength:8, vignette_strength:18,
                  color_grade:"Warm", color_grade_strength:75, saturation:120,
                  blur_type:"None", blur_strength:0 },
    },
    {
        label: "📼 Lo-Fi Degraded",
        desc:  "Aggressive compression + pixelation + grain — VHS / lo-fi look.",
        values: { quality:30, passes:4, pixelate_strength:12, grain_strength:35,
                  vignette_strength:40, color_grade:"Faded", color_grade_strength:60,
                  saturation:65, blur_type:"None", blur_strength:0 },
    },
    {
        label: "🌫 Dreamy Soft Focus",
        desc:  "Soft-focus blur with faded lift — hazy, ethereal portrait look.",
        values: { quality:82, passes:1, grain_strength:10, vignette_strength:20,
                  color_grade:"Faded", color_grade_strength:40, saturation:75,
                  blur_type:"Soft Focus", blur_strength:28 },
    },
];

const FACE_PRESETS = [
    {
        label: "✨ Natural Skin",
        desc:  "Subtle texture and SSS — realistic, non-plastic skin.",
        values: { mask_mode:"Face Only", skin_texture_strength:25, skin_texture_opacity:85,
                  pores_strength:20, pores_opacity:70, sss_strength:12,
                  skin_redness_strength:8, peach_fuzz_strength:10 },
    },
    {
        label: "🔬 High-Detail Skin",
        desc:  "Macro-level pores, texture, fuzz — great for close-up hero shots.",
        values: { mask_mode:"Face Only", skin_texture_strength:45, skin_texture_opacity:100,
                  pores_strength:55, pores_opacity:90, sss_strength:20,
                  skin_redness_strength:15, peach_fuzz_strength:30, sebum_shine_strength:18 },
    },
    {
        label: "🌸 Freckled & Rosy",
        desc:  "Light freckles with rosy cheeks — fair to medium skin types.",
        values: { mask_mode:"Face Only", freckles_strength:35, freckles_opacity:80,
                  skin_redness_strength:28, sss_strength:14,
                  skin_texture_strength:18, skin_texture_opacity:75, peach_fuzz_strength:12 },
    },
    {
        label: "🩸 Acne Breakout",
        desc:  "Moderate acne with blemishes — realistic skin condition portrayal.",
        values: { mask_mode:"Face Only", acne_strength:40, acne_opacity:90,
                  blemishes_strength:30, blemishes_opacity:75, skin_redness_strength:35,
                  pores_strength:30, pores_opacity:80, skin_texture_strength:20 },
    },
    {
        label: "🌟 Oily T-Zone",
        desc:  "Sebum shine on forehead, nose and chin — natural oily-skin sheen.",
        values: { mask_mode:"Face Only", sebum_shine_strength:40, skin_redness_strength:12,
                  sss_strength:18, pores_strength:25, pores_opacity:65, skin_texture_strength:22 },
    },
    {
        label: "👴 Aged Complexion",
        desc:  "Heavy texture, blemishes and visible pores — mature / aged skin.",
        values: { mask_mode:"Face Only", skin_texture_strength:60, skin_texture_opacity:100,
                  pores_strength:65, pores_opacity:100, blemishes_strength:45,
                  blemishes_opacity:80, skin_redness_strength:30, sss_strength:10, peach_fuzz_strength:8 },
    },
];

// ─── localStorage key ─────────────────────────────────────────────────────────
const LS_KEY = "PhotoLab_userPresets_v1";

function loadUserPresets()  { try { return JSON.parse(localStorage.getItem(LS_KEY) || "[]"); } catch { return []; } }
function saveUserPresets(a) { localStorage.setItem(LS_KEY, JSON.stringify(a)); }

// ─── Apply / capture helpers ──────────────────────────────────────────────────

function applyPreset(node, values) {
    for (const w of node.widgets) {
        if (Object.prototype.hasOwnProperty.call(values, w.name)) {
            w.value = values[w.name];
            w.callback?.(values[w.name], app.canvas, node);
        }
    }
    app.graph.setDirtyCanvas(true, true);
}

function captureValues(node) {
    const out = {};
    for (const w of node.widgets) {
        if (w.type !== "button") out[w.name] = w.value;
    }
    return out;
}

// ─── Active-preset highlight state ────────────────────────────────────────────

let _activePresetWidget = null;
let _activePresetLabel  = "";

function activatePreset(node, btnWidget, originalLabel, values) {
    if (_activePresetWidget && _activePresetWidget !== btnWidget) {
        _activePresetWidget.name = _activePresetLabel;
    }
    _activePresetWidget = btnWidget;
    _activePresetLabel  = originalLabel;
    btnWidget.name = `● ${originalLabel}`;

    applyPreset(node, values);
    app.graph.setDirtyCanvas(true, true);
}

function clearActiveHighlight() {
    if (_activePresetWidget) {
        _activePresetWidget.name = _activePresetLabel;
        _activePresetWidget = null;
        _activePresetLabel  = "";
    }
}

// ─── Collapsible Section Builder ──────────────────────────────────────────────
//
// Adds a collapsible section to the node with one button widget per preset.
// The toggle header button hides/shows the row buttons by setting w.hidden.
//
// @param tag       string  — unique identifier used to tag widgets
// @param title     string  — section header text
// @param presets   array   — [{label, desc, values}]
// @param startOpen bool   — whether section starts open or closed
//
// Returns an array of the added button widgets (not the header).

function addCollapsibleSection(node, tag, title, presets, startOpen) {
    let open = startOpen;

    const header = node.addWidget("button",
        `${open ? "▼" : "▶"} ${title}`, null,
        () => {
            open = !open;
            header.name = `${open ? "▼" : "▶"} ${title}`;
            for (const w of node.widgets) {
                if (w._plSectionTag === tag) w.hidden = !open;
            }
            node.setSize(node.computeSize());
            app.graph.setDirtyCanvas(true, true);
        },
        { serialize: false }
    );
    header._plHeader = true;

    const btns = [];
    for (const p of presets) {
        const btn = node.addWidget("button", p.label, null,
            () => activatePreset(node, btn, p.label, p.values),
            { serialize: false, tooltip: p.desc || "" }
        );
        btn._plSectionTag = tag;
        btn.hidden = !open;
        btns.push(btn);
    }
    return btns;
}

function addCollapsibleWidgetSection(node, tag, title, widgetNames, startOpen) {
    let open = startOpen;
    const matched = [];

    for (const w of node.widgets) {
        if (w.type === "button") continue;
        if (widgetNames.includes(w.name)) {
            w._plSectionTag = tag;
            w._plSectionHeader = false;
            w.hidden = !open;
            matched.push(w);
        }
    }

    if (matched.length === 0) return;

    const header = node.addWidget("button",
        `${open ? "▼" : "▶"} ${title}`, null,
        () => {
            open = !open;
            header.name = `${open ? "▼" : "▶"} ${title}`;
            for (const w of node.widgets) {
                if (w._plSectionTag === tag && !w._plSectionHeader) w.hidden = !open;
            }
            node.setSize(node.computeSize());
            app.graph.setDirtyCanvas(true, true);
        },
        { serialize: false }
    );
    header._plSectionTag = tag;
    header._plSectionHeader = true;

    const headerIndex = node.widgets.indexOf(header);
    const firstMatchIndex = node.widgets.indexOf(matched[0]);
    if (firstMatchIndex >= 0 && headerIndex >= 0) {
        node.widgets.splice(headerIndex, 1);
        node.widgets.splice(firstMatchIndex, 0, header);
    }
}

// ─── Extension ────────────────────────────────────────────────────────────────

app.registerExtension({
    name: "PhotoLab.PresetsV4",

    async nodeCreated(node) {
        if (node.comfyClass !== "PhotoLab" && node.type !== "PhotoLab") return;

        // Guard against double-adding on workflow load/deserialisation
        if (node._plWidgetsAdded) return;
        node._plWidgetsAdded = true;

        // ── Reset to defaults button ─────────────────────────────────────────────
        node.addWidget("button", "↺ Reset to Defaults", null, () => {
            clearActiveHighlight();
            for (const w of node.widgets) {
                const def = WIDGET_DEFAULTS[w.name];
                if (def !== undefined) { 
                    w.value = def; 
                    w.callback?.(def, app.canvas, node); 
                }
            }
            app.graph.setDirtyCanvas(true, true);
        }, { serialize: false });

        node.addWidget("button", "Presets", null, null, { serialize: false });

        addCollapsibleWidgetSection(node, "global_inputs", "Aesthetic", [
            "quality",
            "passes",
            "pixelate_strength",
            "grain_strength",
            "vignette_strength",
        ], true);

        addCollapsibleWidgetSection(node, "color_inputs", "Color", [
            "color_grade",
            "color_grade_strength",
            "saturation",
        ], true);

        addCollapsibleWidgetSection(node, "blur_inputs", "Blur", [
            "blur_type",
            "blur_strength",
        ], true);

        addCollapsibleWidgetSection(node, "lighting_inputs", "Lighting", [
            "lighting_match_mode",
            "lighting_match_strength",
        ], true);

        addCollapsibleWidgetSection(node, "mask_inputs", "Mask", [
            "mask_mode",
            "pores_strength",
            "blemishes_strength",
            "acne_strength",
            "freckles_strength",
            "skin_texture_strength",
            "sss_strength",
            "peach_fuzz_strength",
            "skin_redness_strength",
            "sebum_shine_strength",
            "skin_seed",
            "pores_opacity",
            "blemishes_opacity",
            "acne_opacity",
            "freckles_opacity",
            "skin_texture_opacity",
        ], true);

        // ── Section 1: Global Photo Effects (starts OPEN) ────────────────────────
        addCollapsibleSection(node, "global", "Global Photo Effects", GLOBAL_PRESETS, true);

        // ── Section 2: Lighting Match (starts CLOSED) ───────────────────────────
        const lightingPresets = [
            {
                label: "🎯 Histogram L-Channel",
                desc: "Best all-rounder — matches luminance distribution only.",
                values: { lighting_match_mode: "Histogram (L-channel)" }
            },
            {
                label: "⚡ Reinhard Transfer",
                desc: "Fast mean/std transfer — good for subtle corrections.",
                values: { lighting_match_mode: "Reinhard Transfer" }
            },
            {
                label: "🎨 Full LAB Histogram",
                desc: "Matches all LAB channels including color tone.",
                values: { lighting_match_mode: "Full LAB Histogram" }
            }
        ];
        addCollapsibleSection(node, "lighting", "Lighting Match", lightingPresets, false);

        // ── Section 3: Face Skin Effects (starts CLOSED) ────────────────────────
        addCollapsibleSection(node, "face", "Face Skin Effects", FACE_PRESETS, false);

        // ── User presets section ─────────────────────────────────────────────────
        function rebuildUser() {
            node.widgets = node.widgets.filter(w => !w._plUser);

            const all = loadUserPresets();

            let open = true;
            const header = node.addWidget("button",
                `${open ? "▼" : "▶"} My Presets (${all.length})`, null,
                () => {
                    open = !open;
                    header.name = `${open ? "▼" : "▶"} My Presets (${all.length})`;
                    for (const w of node.widgets) {
                        if (w._plUser && !w._plUserHeader) w.hidden = !open;
                    }
                    node.setSize(node.computeSize());
                    app.graph.setDirtyCanvas(true, true);
                },
                { serialize: false }
            );
            header._plUser       = true;
            header._plUserHeader = true;

            const saveBtn = node.addWidget("button", "＋ Save Current as Preset", null,
                () => {
                    const name = prompt(
                        "Name your preset:",
                        `My Preset ${loadUserPresets().length + 1}`
                    );
                    if (!name) return;
                    const fresh = loadUserPresets();
                    fresh.push({ label: `★ ${name}`, desc: "User preset", values: captureValues(node) });
                    saveUserPresets(fresh);
                    rebuildUser();
                },
                { serialize: false }
            );
            saveBtn._plUser = true;

            for (let i = 0; i < all.length; i++) {
                const p = all[i];

                const applyBtn = node.addWidget("button", p.label, null,
                    () => activatePreset(node, applyBtn, p.label, p.values),
                    { serialize: false, tooltip: "Click to apply this preset" }
                );
                applyBtn._plUser = true;

                const delBtn = node.addWidget("button", `  ✕ Delete "${p.label}"`, null,
                    () => {
                        if (_activePresetWidget === applyBtn) clearActiveHighlight();
                        const fresh = loadUserPresets();
                        fresh.splice(i, 1);
                        saveUserPresets(fresh);
                        rebuildUser();
                    },
                    { serialize: false, tooltip: "Delete this preset" }
                );
                delBtn._plUser = true;
            }

            node.setSize(node.computeSize());
            app.graph.setDirtyCanvas(true, true);
        }

        rebuildUser();
    },
});
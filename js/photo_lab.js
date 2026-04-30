/**
 * photo_lab.js
 *
 * ComfyUI frontend extension for the PhotoLab node.
 * Adds a "↺ Reset to Defaults" button widget inside the node.
 */

import { app } from "/scripts/app.js";

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

app.registerExtension({
    name: "PhotoLab.ResetDefaults",

    async nodeCreated(node) {
        if (node.comfyClass !== "PhotoLab" && node.type !== "PhotoLab") return;

        node.addWidget(
            "button",
            "↺ Reset to Defaults",
            null,
            () => {
                for (const widget of node.widgets) {
                    const def = WIDGET_DEFAULTS[widget.name];
                    if (def === undefined) continue;
                    widget.value = def;
                    widget.callback?.(def, app.canvas, node);
                }
                app.graph.setDirtyCanvas(true, true);
            },
            { serialize: false }
        );

        node.setSize(node.computeSize());
    },
});

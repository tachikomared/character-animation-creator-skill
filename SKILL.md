---
name: game-character-sprites
description: Create game-ready fixed-cell pixel-art character spritesheets from text concepts, reference images, or existing character art. Use when Codex needs to design, generate, clean up, validate, and package 2D game characters with native 32x32, 64x64, or 128x128 cells; 4-way or 8-way directions; idle, walk/run, jump, attack, archer, caster, or other animation strips; transparent GIF/WebP previews; and per-direction targeted regeneration.
---

# Game Character Sprites

## Overview

Use this skill to make game-ready fixed-cell pixel-art character animations. If the user names cell sizes, those sizes are the required output scope. If no size is named, default to `64x64`.

Never expand or reduce scope silently. If the user asks for "attack and walk only," make only those actions. If they ask for GIFs, deliver GIF/WebP previews, not just atlas PNGs. If directions are not specified and the user asks for a full game character movement pack, default to full 8-way directions; for a quick sample, test, or one-direction request, use only one direction and label it.

Minimum workspace outputs:

```text
run/
  run-manifest.json
  source/<original-imagegen-output>.png
  <cell>/
    generated/<action>-<direction>.png
    frames/<action>-<direction>/<index>.png
    final/<action>-sheet-clean.png
    final/<action>-metadata.json
    qa/<action>-validation.json
    qa/<action>-contact-sheet.png
    qa/visual-review.json
    qa/previews/*-transparent-x4.webp
    qa/previews/*-transparent-x4.gif
    qa/previews/*-checker-x4.gif
```

## Scope

Supported cell sizes: `32`, `64`, `128`.

## Size Contract

Requested sizes are a hard deliverable. If the user asks for `32x32 64x64 128x128`, create a native output set for each size:

```text
run/32/...
run/64/...
run/128/...
```

Do not collapse a multi-size request into a single `64x64` master plus resized variants unless the user explicitly says scaled variants are acceptable. If you must provide scaled variants as a fallback, label them as `scaled-32` or `upscaled-128`, state that they are not native assets, and do not describe them as authored/native sheets.

Do not ask imagegen for a combined `32/64/128` contact sheet as the normal workflow. Combined multi-size contact sheets make the model treat the sizes as layout elements inside one picture, not as separate pixel-art budgets. For native assets, generate each requested size as its own imagegen row strip at that size budget.

Multi-size sprites must follow a strict resolution hierarchy:

- Primary level is locked at `32x32`: silhouette, proportions, pose timing, and main color blocks.
- Secondary level starts at `64x64`: internal lines, larger facial/clothing details, and readable secondary forms inside the locked primary shape.
- Tertiary level starts at `128x128`: micro-highlights, small folds, surface pixels, and tiny accents inside the locked primary and secondary structure.
- Larger sizes must behave conceptually like a nearest-neighbor expansion of the 32px design with extra information added inside the same shapes.
- Larger sizes must not change the primary silhouette, limb lengths, body proportions, pose sequence, or main palette blocks.

For native multi-size jobs, run the workflow as a hierarchy, not as three unrelated drawings:

```text
generate the 32px strip directly as a 32px-budget pixel-art row
visually accept the 32px primary silhouette, pose timing, and main color blocks
generate the 64px strip directly as a 64px-budget row, using the accepted 32px strip as the primary-structure reference
generate the 128px strip directly as a 128px-budget row, using the accepted 32px and 64px strips as structure references
assemble each size with --cell <cell>
clean each size with --cell <cell>
validate each size with --cell <cell>
run hierarchy QA by making thumbnail comparisons only; do not create assets by downsampling
export previews for each size
```

Cell-size guidance:

- `32x32`: simplify details, exaggerate silhouette, use fewer colors, avoid tiny face/accessory details that will blur.
- `64x64`: balanced default for game prototypes and readable chibi characters.
- `128x128`: native redraw with more pixel detail and smoother secondary motion, not a nearest-neighbor upscale from 64.

Blocked acceptance: if the user requested multiple sizes and the final response only includes 64px authored sheets plus scaled 32/128 variants, the task is incomplete unless the user approved that tradeoff.

Also block acceptance when 32/64/128 are three inconsistent drawings. Native larger sizes may add detail, but they must downsample back to the same 32px primary silhouette and main color layout.

Default directions:

```text
south, south-east, east, north-east, north, north-west, west, south-west
```

Only create directions requested by the user. For full 8-way exports, use the order above.

## Single Direction Jobs

Requests containing "one direction", "single direction", "just one direction", "1 direction", or "test one direction" mean:

```text
rows: 1
directions: <requested direction, or south/front if the reference is front-facing>
```

Do not expand single-direction jobs into 4-way or 8-way sheets. If the user provides a front-facing reference and does not name the direction, use `south` and say that the test uses the reference-facing/front direction.

For one-direction multi-size tests, expected outputs look like:

```text
run/32/final/walk-sheet-clean.png   # 192x32 for 6 frames
run/64/final/walk-sheet-clean.png   # 384x64 for 6 frames
run/128/final/walk-sheet-clean.png  # 768x128 for 6 frames
```

Default frames:

```text
idle:   4 frames, optionally padded to 6 cells
walk:   6 frames
attack: 6 frames
```

## Agent Workflow

1. Establish the requested scope: cell size or sizes, actions, directions, frame count, weapon/class, and must-keep reference details. Treat explicit sizes as mandatory outputs.
2. Ground the character from the user reference. If the image tool cannot consume the file path, use the attached image from chat context; if no visual grounding is available, stop and say the reference could not be used instead of inventing a loose text-only character.
3. Create `run/run-manifest.json` before generation. Record the reference source, identity details, requested scope, and planned generation method.
4. Build one strong canonical base sprite first for the smallest requested size, usually `32x32`, so the primary design is locked before adding detail.
5. Generate one action-direction-size strip at a time, e.g. `32/walk-south`, then `64/walk-south`, then `128/walk-south`.
6. For multi-size jobs, each requested size must have its own imagegen output file. Do not use one imagegen contact sheet as the source for multiple native sizes.
7. Record every generated strip in `run/run-manifest.json` with `method: "imagegen"`, cell size, action, direction, imagegen output path, source path, and prompt path.
8. Assemble strips with `scripts/assemble_action_sheet.py`.
9. Clean with `scripts/pixel_snap.py` using chroma-key cleanup.
10. Validate geometry, residue, and motion with `scripts/validate_sheet.py` and `scripts/audit_sprite_motion.py`.
11. For multi-size jobs, validate resolution hierarchy with `scripts/validate_resolution_hierarchy.py`.
12. Export previews with `scripts/export_animation_previews.py`.
13. Visually inspect every contact sheet and at least one GIF/WebP per direction group, then write `qa/visual-review.json`. Do not rely on validation JSON alone for art quality.
14. Validate provenance and visual acceptance with `scripts/validate_run_manifest.py`.
15. Regenerate only weak directions or frames. Do not redo strong rows.

Do not generate a complete 8-direction sheet in one image prompt. One-shot sheets often create near-duplicate walk frames, direction drift, missing directions, and inconsistent characters.

For web/ChatGPT agents, keep the workflow CLI and file based. Write artifacts to the workspace, call the platform's file export/share tool when available, then return downloadable links to the final atlas, metadata, contact sheet, validation JSON, and preview GIF/WebP files. Plain `/workspace/...` text paths are not enough if the UI needs exported files.

Do not show raw generated chroma-key strips as final results. Raw strips are intermediate QA only. Final visual previews must be cleaned transparent WebP/GIF or checkerboard GIF/contact sheets.

When using a chat attachment as reference, record an identity note in the run folder listing the exact details preserved from the image. Do not write "falling back to a prompt" unless the image is truly unavailable. The visible chat image is valid grounding for identity notes even when it is not available as a normal filesystem path.

## Imagegen File Handoff

Imagegen output must become a local file before the skill can finish. In Codex Desktop, generated images are saved under:

```text
D:\CodexHome\generated_images\<thread-id>\<image-id>.png
```

Copy the selected imagegen result into `run/source/` and leave the original in place. If the platform cannot expose the generated image as a file, stop and say the image was generated but cannot be processed into sprite files. Do not claim the sprite pack is complete.

Normal native workflow:

```text
imagegen -> run/source/32-walk-south.png -> run/32/generated/walk-south.png
imagegen -> run/source/64-walk-south.png -> run/64/generated/walk-south.png
imagegen -> run/source/128-walk-south.png -> run/128/generated/walk-south.png
```

Each source image must be generated specifically for that cell budget. For example, the `32` imagegen prompt should ask for one row of six `32x32` frames only. The `64` prompt should ask for one row of six `64x64` frames only. The `128` prompt should ask for one row of six `128x128` frames only.

Emergency fallback only: if imagegen already returned one multi-size contact sheet, `scripts/import_imagegen_contact_sheet.py` may be used to rescue it for diagnosis. That output must be marked as `imported_contact_sheet: true` in the manifest and must not be called a native multi-size pass unless the user explicitly accepts that fallback.

```bash
python "<skill>/scripts/import_imagegen_contact_sheet.py" \
  --input path/to/imagegen-output.png \
  --run-dir path/to/run \
  --action walk \
  --direction south \
  --sizes 32,64,128 \
  --columns 6 \
  --key-color "#00ff00" \
  --copy-source
```

This creates:

```text
run/32/generated/walk-south.png
run/64/generated/walk-south.png
run/128/generated/walk-south.png
run/source/<imagegen-output>.png
run/imagegen-import-report.json
```

Then continue with assembly, cleanup, validation, previews, manifest validation, and visual review.

## Reference And Provenance Gate

A run is not a valid art test unless the visual source strips came from `$imagegen` using the user's reference. Text-only identity notes are not enough.

Required manifest:

```json
{
  "reference": {
    "source_type": "chat_attachment",
    "source": "attached image #1 or path/to/reference.png",
    "used_for_generation": true,
    "identity_notes": [
      "green bird/penguin body",
      "red and white cap",
      "white unicorn float",
      "rainbow tail",
      "sandals"
    ]
  },
  "scope": {
    "sizes": [32, 64, 128],
    "actions": ["walk"],
    "directions": ["south"],
    "frames": 6
  },
  "generation": {
    "method": "imagegen",
    "imagegen_output_path": "run/source/32-walk-south.png",
    "procedural": false,
    "text_only": false,
    "imported_contact_sheet": false
  },
  "strips": [
    {
      "cell": 32,
      "action": "walk",
      "direction": "south",
      "method": "imagegen",
      "imagegen_output_path": "run/source/32-walk-south.png",
      "source_path": "run/32/generated/walk-south.png",
      "prompt_path": "run/32/prompts/walk-south.txt"
    }
  ],
  "visual_review": {
    "path": "run/32/qa/visual-review.json"
  }
}
```

Blocked acceptance:

- `generation.method` is `procedural`, `python_draw`, `script`, `text_only`, or anything other than `imagegen`
- `generation.imagegen_output_path` is missing or not a real local file
- one imagegen output is reused as the source for multiple requested native sizes without explicit fallback approval
- `generation.imported_contact_sheet` is true and the final response calls the output native
- `reference.used_for_generation` is not true
- generated strips were made by local drawing code
- the final response calls a procedural smoke test a real image/reference test
- visual review says the sprite does not match the reference, direction, or requested action

Local code may create tiny fixtures only for script unit tests. Those outputs must be labeled `pipeline-only`, must not be shipped as art, and must not be used to claim the skill can generate the requested character.

## Subagents

If the user explicitly asks for subagents or parallel agents, split work by action or direction:

- Worker A: base sprite and identity notes
- Workers B/C/D: independent direction strips with disjoint output paths
- QA worker: validation/contact-sheet review and weak-row list

Workers should edit only their assigned files and must not overwrite other workers' outputs. The main agent integrates rows, runs validation, and regenerates weak directions only.

## Direction Lock

Prompt and reject directions using these rules:

- `south`: front-facing, face/body toward camera
- `north`: back-facing, back of head/body visible
- `east`: side-facing screen-right
- `west`: side-facing screen-left
- diagonals visibly split neighboring directions
- reject rows where every frame drifts screen-right
- reject rows where feet move but torso/head direction stays unchanged

When directions are wrong, regenerate only the weak direction with explicit wording such as "back-facing north, no front face visible" or "side-facing left, walking west."

## Generation Rules

Use `$imagegen` for visual generation. Do not hand-draw missing animation frames with local code. Scripts may crop, assemble, quantize, snap, validate, and preview already-generated art.

Base sprite prompt:

```text
<cell>x<cell> pixel-art game sprite, single character, transparent or flat chroma-key background.
Readable silhouette, hard pixel edges, limited palette, no UI, no text, no frame border.
Preserve: <identity details>.
```

Row strip prompt:

```text
<cell>x<cell> pixel-art game sprite animation strip.
One horizontal row of exactly <N> separated frames.
Action: <action>. Direction: <direction>.
Flat pure solid chroma-key background <key color>, no gradient, no rounded panel, no shadows, no floor, no UI, no text, no frame numbers.
Preserve the canonical character identity exactly.
Hard pixel-art edges, saturated readable colors, clear green/magenta space between frames.
```

Prefer `#00ff00` chroma-key. Use `#ff00ff` if the character or VFX uses green.

Reject and regenerate strips with gradient backgrounds, rounded colored cards, missing frame separation, cropped body/weapon, or any text/labels. Do not try to rescue badly structured strips with equal slicing.

## Walk Quality

Do not make walk by generating a whole walk sheet at once. Generate per direction as separate 6-frame strips.

Use this pose structure:

```text
contact, down, passing, up, contact, passing
```

Lock these animation rules before generation:

- head bob: 1-2 px
- hips shift: 1 px
- opposite arm/leg swing
- cape/hair lag one frame behind torso
- weapon hand stays controlled
- chibi/small sprites need exaggerated motion to read

If the walk looks like near-duplicate standing poses, regenerate that direction with stronger prompts: "large readable step silhouettes, alternating feet, clear contact/down/passing/up poses."

## Jump Quality

For jump, use 6 frames:

```text
crouch, launch, rise, apex, fall, land/recover
```

The body should move vertically inside the cell while staying within margins. Legs must visibly compress on crouch/land. Hair, cape, ears, tail, or clothing should lag slightly. Reject jump rows where the character only changes arm pose while feet stay fixed.

## Attack Quality

For melee attacks, show anticipation, swing/contact, and recovery. Weapon arcs must stay attached to the weapon and inside the cell.

For archer attacks, animate draw, hold/aim, release, recoil, and recovery. The projectile should be a separate VFX unless the user asks for it inside the frame. Bow hand should stay controlled and direction-accurate.

If an attack looks cut off, inspect edge pixels and bbox. Regenerate only that row with "full body and weapon inside every frame, no crop, centered with 2-4 px margin."

## Chroma Key And Cleanup

Remove chroma key in two passes:

1. Edge-connected flood removal: delete only key pixels connected to the image border.
2. Final residue cleanup: after frame fitting, remove only near-exact key pixels.

Never globally delete all green-ish pixels. Many sprites use green for magic, poison, cyber glows, eyes, or clothing.

Recommended cleanup:

```bash
python "<skill>/scripts/pixel_snap.py" \
  --input path/to/source.png \
  --output path/to/clean.png \
  --cell <cell> \
  --palette 96 \
  --alpha-threshold 12 \
  --chroma-key "#00ff00" \
  --edge-flood-threshold 105 \
  --residue-threshold 72
```

Use palette `96-128` for attack/VFX, `32-64` for simple idle/walk. Use `--pixelate-scale 2` only when generated art is too smooth.

Optional TachiSnap stage: if `TachiSnap` is available, use it after chroma removal and before final preview when generated pixel grids are uneven. TachiSnap is a client-side Rust/WASM pixel snapper with k-means++ CIELAB palette quantization, flood/global background removal, GIF/sheet animation support, bulk folder processing, JSON reports, and nearest-neighbor upscale. Do not let it change atlas geometry; run it per strip or frame, then reassemble with the skill scripts.

Example agent-safe TachiSnap usage:

```bash
tachi-snap bulk ./input-ai-pixel-art ./output-clean \
  --recursive \
  --k 16 \
  --pixel-size 0 \
  --upscale 4 \
  --remove-bg \
  --bg-mode flood \
  --json
```

## Assembly

Assemble separate strips into one action atlas:

```bash
python "<skill>/scripts/assemble_action_sheet.py" \
  --input-dir path/to/generated \
  --output path/to/final/walk-sheet.png \
  --action walk \
  --cell <cell> \
  --columns 6 \
  --frames-dir path/to/frames \
  --key-color "#00ff00"
```

Then run cleanup on the assembled atlas or frames.

Use the bundled assembler before writing ad hoc slicing code. Equal-width slicing is only acceptable when the generated strip has exactly uniform frame slots and still passes residue, edge, and motion QA. If a custom fallback script is necessary, save it in the run folder and keep the same outputs as the bundled scripts.

## Validation

Validate before final response:

```bash
python "<skill>/scripts/validate_sheet.py" \
  --input path/to/final/walk-sheet-clean.png \
  --rows <rows> \
  --columns 6 \
  --cell <cell> \
  --row-names <comma-separated-requested-directions> \
  --chroma-key "#00ff00" \
  --fail-on-warnings \
  --json-out path/to/qa/walk-validation.json \
  --contact-sheet path/to/qa/walk-contact-sheet.png
```

Run `scripts/audit_sprite_motion.py` for every walk, run, and jump sheet. Also run it when the user complains about bad walk, missing directions, weak motion, chroma residue, or frame mixing. Treat warnings as a regeneration list, not as a reason to redo everything.

Validate run provenance and the manual visual gate:

```bash
python "<skill>/scripts/validate_run_manifest.py" \
  --manifest path/to/run/run-manifest.json \
  --required-sizes 32,64,128 \
  --required-actions walk \
  --required-directions south \
  --require-visual-review
```

Validate multi-size hierarchy as QA only. This command makes thumbnail comparisons to catch structure drift. It must never be used to create the 32px, 64px, or 128px assets:

```bash
python "<skill>/scripts/validate_resolution_hierarchy.py" \
  --base32 path/to/run/32/final/walk-sheet-clean.png \
  --sheet64 path/to/run/64/final/walk-sheet-clean.png \
  --sheet128 path/to/run/128/final/walk-sheet-clean.png \
  --rows <rows> \
  --columns 6 \
  --json-out path/to/run/qa/resolution-hierarchy.json \
  --fail-on-warnings
```

Visual review file:

```json
{
  "accepted": false,
  "reviewer_notes": "Reject until this is manually inspected.",
  "checks": {
    "reference_identity": "fail",
    "direction": "fail",
    "animation_readable": "fail",
    "frame_separation": "fail",
    "not_procedural": "fail"
  }
}
```

Only set `accepted: true` when the contact sheet and preview animation actually resemble the user reference and satisfy the requested action/direction.

Block acceptance when:

- atlas dimensions are wrong
- required frames are empty
- sprites touch cell edges unexpectedly
- chroma-key residue remains
- transparent GIF frames accumulate or smear
- walk frames are near-duplicates
- rows drift to the wrong direction
- attack effects are detached, oversized, or clipped
- run manifest does not prove imagegen/reference provenance
- visual review is missing or not accepted
- multi-size output fails the resolution hierarchy QA gate

Validation passing only proves geometry/pixel hygiene. It does not prove the animation is good. The agent must inspect the contact sheet and previews before claiming the pack is "solid," "clean," or "ready."

## Preview Export

Prefer animated WebP for transparent previews. GIF is compatibility output.

```bash
python "<skill>/scripts/export_animation_previews.py" \
  --atlas path/to/final/walk-sheet-clean.png \
  --rows <rows> \
  --columns 6 \
  --cell <cell> \
  --row-names <comma-separated-requested-directions> \
  --prefix walk \
  --out-dir path/to/qa/previews \
  --scale 4
```

GIF rules:

- global palette
- palette index `0` reserved for transparency
- `disposal=2`
- no dithering
- no optimizer that changes disposal to `1`

Always send preview links when the user asks for GIFs.

For `128x128`, distinguish native redraw from upscale. If the user asks for native 128, generate native 128 strips. A nearest-neighbor 2x version of 64px art is an upscale pack, not a native 128 asset.

For `32x32`, distinguish native simplification from downscale. If the user asks for native 32, generate or redraw simplified 32px strips. A nearest-neighbor half-size version of 64px art is a downscaled variant, not a native 32 asset.

## Targeted Regeneration

When the user says "better but some directions are missing" or "regenerate weak directions," do this:

1. Inspect contact sheet and preview animations.
2. List weak rows by action and direction.
3. Regenerate only those strips using the canonical base and failed row as context.
4. Reassemble, clean, validate, preview.

Do not overwrite strong generated strips unless the user explicitly asks for a full redo.

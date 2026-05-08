# Fixed-Cell Character Sheet Spec

Supported cell sizes: `32x32`, `64x64`, `128x128`.

Default cell size when the user does not name a size: `64x64`.

If the user names multiple sizes, each named size is a required native output. Do not satisfy `32x32 64x64 128x128` by authoring only a 64px sheet and resizing it unless the user explicitly accepts scaled variants.

Native multi-size means separate generation per cell budget. Do not ask for one image containing all sizes as the normal workflow.

Default directions:

```text
south
south-east
east
north-east
north
north-west
west
south-west
```

Default actions:

```text
idle: 4 frames, optionally padded to 6 cells
walk: 6 frames
attack: 6 frames
```

For `8 rows x 6 columns`, atlas dimensions are:

```text
32px cells:  192x256
64px cells:  384x512
128px cells: 768x1024
```

Prompt constraints:

- no text, UI, labels, numbers, frame borders, or guide lines
- no shadows, floor marks, dust trails, or motion blur
- no detached VFX unless exported as a separate VFX sheet
- character must remain fully inside each cell
- use readable silhouette over high detail
- use 16-48 colors for simple sprites, 96-128 for VFX-heavy attack sheets

Workflow constraint:

Generate base sprite first, then separate action-direction strips. Do not prompt a full multi-row atlas unless the user explicitly accepts lower consistency.

Reference provenance constraint:

- Real art tests must use image generation grounded in the user's reference image.
- Text-only notes about a visible image are not enough.
- Local procedural/code-drawn sprites are only allowed for script unit tests and must be labeled `pipeline-only`.
- A run cannot be accepted without `run-manifest.json` and `qa/visual-review.json`.
- Imagegen output must be available as a local file and copied into `run/source/`.
- Multi-size imagegen contact sheets are diagnostic fallback only. Native delivery requires separate imagegen outputs for each requested cell size.

Native size constraint:

- Native `32x32` locks the primary design: silhouette, proportions, pose timing, and main color blocks.
- Native `64x64` adds secondary details inside the locked 32px primary structure.
- Native `128x128` adds tertiary details inside the locked 32px/64px structure.
- Resized outputs must be named `scaled` or `upscaled/downscaled` and described as variants, not native sheets.
- 64px and 128px sheets must pass thumbnail/hierarchy QA against the 32px primary structure; they must not be unrelated redraws.

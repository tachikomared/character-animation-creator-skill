#!/usr/bin/env python3
"""Validate sprite run provenance, requested scope, and visual acceptance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


BAD_METHOD_WORDS = (
    "procedural",
    "python",
    "draw",
    "script",
    "code",
    "text_only",
    "text-only",
    "text only",
)
ALLOWED_REFERENCE_TYPES = {"chat_attachment", "file", "image_url"}
MANDATORY_VISUAL_CHECKS = {
    "reference_identity",
    "direction",
    "animation_readable",
    "frame_separation",
    "not_procedural",
}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise SystemExit(f"missing file: {path}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from None


def split_csv(raw: str, cast=str) -> list[Any]:
    values = []
    for part in raw.split(","):
        value = part.strip()
        if value:
            values.append(cast(value))
    return values


def method_is_imagegen(value: Any) -> bool:
    method = str(value or "").strip().lower()
    if "imagegen" not in method:
        return False
    return not any(word in method for word in BAD_METHOD_WORDS)


def resolve_run_path(manifest_path: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    base = manifest_path.parent
    if candidate.parts and candidate.parts[0] == "run":
        return base.parent / candidate
    return base / candidate


def check_visual_review(manifest_path: Path, manifest: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    visual = manifest.get("visual_review")
    visual_path_value = visual.get("path") if isinstance(visual, dict) else "qa/visual-review.json"
    visual_path = resolve_run_path(manifest_path, visual_path_value)
    if visual_path is None:
        errors.append("visual_review.path is missing")
        return
    if not visual_path.exists():
        errors.append(f"visual review file missing: {visual_path}")
        return

    review = load_json(visual_path)
    if not isinstance(review, dict):
        errors.append("visual review must be a JSON object")
        return
    if review.get("accepted") is not True:
        errors.append("visual review is not accepted")

    checks = review.get("checks")
    if not isinstance(checks, dict):
        errors.append("visual review checks object is missing")
        return

    missing = sorted(MANDATORY_VISUAL_CHECKS.difference(checks))
    if missing:
        errors.append(f"visual review missing checks: {', '.join(missing)}")
    for name, value in checks.items():
        passed = value is True or str(value).strip().lower() == "pass"
        if not passed:
            errors.append(f"visual review check failed: {name}={value}")

    if not review.get("reviewer_notes"):
        warnings.append("visual review has no reviewer_notes")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--required-sizes", default="")
    parser.add_argument("--required-actions", default="")
    parser.add_argument("--required-directions", default="")
    parser.add_argument("--require-visual-review", action="store_true")
    parser.add_argument("--allow-procedural", action="store_true")
    parser.add_argument("--json-out")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise SystemExit("manifest must be a JSON object")

    errors: list[str] = []
    warnings: list[str] = []
    required_sizes = split_csv(args.required_sizes, int)
    required_actions = split_csv(args.required_actions)
    required_directions = split_csv(args.required_directions)

    reference = manifest.get("reference")
    if not isinstance(reference, dict):
        errors.append("reference object is missing")
    else:
        source_type = reference.get("source_type")
        if source_type not in ALLOWED_REFERENCE_TYPES:
            errors.append(f"reference.source_type must be one of {sorted(ALLOWED_REFERENCE_TYPES)}")
        if not reference.get("source"):
            errors.append("reference.source is missing")
        if reference.get("used_for_generation") is not True:
            errors.append("reference.used_for_generation must be true")
        notes = reference.get("identity_notes")
        if not isinstance(notes, list) or not notes:
            errors.append("reference.identity_notes must be a non-empty list")

    scope = manifest.get("scope")
    if not isinstance(scope, dict):
        errors.append("scope object is missing")
        scope = {}
    sizes = [int(value) for value in scope.get("sizes", [])] if isinstance(scope.get("sizes"), list) else []
    actions = [str(value) for value in scope.get("actions", [])] if isinstance(scope.get("actions"), list) else []
    directions = [str(value) for value in scope.get("directions", [])] if isinstance(scope.get("directions"), list) else []

    for size in required_sizes:
        if size not in sizes:
            errors.append(f"required size missing from scope: {size}")
    for action in required_actions:
        if action not in actions:
            errors.append(f"required action missing from scope: {action}")
    for direction in required_directions:
        if direction not in directions:
            errors.append(f"required direction missing from scope: {direction}")

    generation = manifest.get("generation")
    if not isinstance(generation, dict):
        errors.append("generation object is missing")
    else:
        if not method_is_imagegen(generation.get("method")) and not args.allow_procedural:
            errors.append(f"generation.method must be imagegen, got {generation.get('method')!r}")
        if generation.get("procedural") is True and not args.allow_procedural:
            errors.append("generation.procedural must not be true")
        if generation.get("text_only") is True:
            errors.append("generation.text_only must not be true")
        imported_contact_sheet = generation.get("imported_contact_sheet") is True
        if method_is_imagegen(generation.get("method")):
            imagegen_output = generation.get("imagegen_output_path") or generation.get("source_image_path")
            imagegen_output_path = resolve_run_path(manifest_path, imagegen_output)
            if imagegen_output_path is None:
                errors.append("generation.imagegen_output_path is required for imagegen runs")
            elif not imagegen_output_path.exists():
                errors.append(f"generation.imagegen_output_path does not exist: {imagegen_output_path}")

    strips = manifest.get("strips")
    if not isinstance(strips, list) or not strips:
        errors.append("strips must be a non-empty list")
        strips = []

    strip_map: dict[tuple[int, str, str], dict[str, Any]] = {}
    source_usage: dict[str, set[int]] = {}
    for index, strip in enumerate(strips):
        if not isinstance(strip, dict):
            errors.append(f"strip {index} is not an object")
            continue
        try:
            key = (int(strip.get("cell")), str(strip.get("action")), str(strip.get("direction")))
        except (TypeError, ValueError):
            errors.append(f"strip {index} has invalid cell/action/direction")
            continue
        strip_map[key] = strip
        if not method_is_imagegen(strip.get("method")) and not args.allow_procedural:
            errors.append(f"strip {key} method must be imagegen, got {strip.get('method')!r}")
        source_path = resolve_run_path(manifest_path, strip.get("source_path"))
        if source_path is None:
            errors.append(f"strip {key} source_path is missing")
        elif not source_path.exists():
            errors.append(f"strip {key} source_path does not exist: {source_path}")
        imported_from = strip.get("imported_from")
        if imported_from:
            imported_from_path = resolve_run_path(manifest_path, imported_from)
            if imported_from_path is None or not imported_from_path.exists():
                errors.append(f"strip {key} imported_from does not exist: {imported_from}")
        strip_imagegen_output = strip.get("imagegen_output_path") or strip.get("imported_from") or strip.get("source_path")
        strip_imagegen_path = resolve_run_path(manifest_path, strip_imagegen_output)
        if strip_imagegen_path is None:
            errors.append(f"strip {key} imagegen_output_path is missing")
        elif not strip_imagegen_path.exists():
            errors.append(f"strip {key} imagegen_output_path does not exist: {strip_imagegen_path}")
        else:
            source_usage.setdefault(str(strip_imagegen_path).lower(), set()).add(key[0])
        prompt_path = resolve_run_path(manifest_path, strip.get("prompt_path"))
        if prompt_path is None:
            warnings.append(f"strip {key} prompt_path is missing")
        elif not prompt_path.exists():
            warnings.append(f"strip {key} prompt_path does not exist: {prompt_path}")

    for size in required_sizes or sizes:
        for action in required_actions or actions:
            for direction in required_directions or directions:
                key = (size, action, direction)
                if key not in strip_map:
                    errors.append(f"required strip missing: cell={size} action={action} direction={direction}")

    if not (isinstance(generation, dict) and generation.get("imported_contact_sheet") is True):
        for source, used_sizes in source_usage.items():
            if len(used_sizes) > 1:
                errors.append(
                    "one imagegen output is reused for multiple native sizes "
                    f"({sorted(used_sizes)}): {source}"
                )

    if args.require_visual_review:
        check_visual_review(manifest_path, manifest, errors, warnings)

    report = {
        "ok": not errors,
        "manifest": str(manifest_path),
        "errors": errors,
        "warnings": warnings,
    }
    if args.json_out:
        out = Path(args.json_out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

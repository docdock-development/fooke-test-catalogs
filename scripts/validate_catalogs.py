#!/usr/bin/env python3
"""Validate every versioned catalogue before it is published."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


CATALOG_VERSION_PATTERN = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d+$")
CLIENT_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class CatalogValidationError(ValueError):
    """A catalogue violates its publication contract."""


def _object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CatalogValidationError(f"{location} must be a JSON object")
    return value


def _array(value: Any, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise CatalogValidationError(f"{location} must be a JSON array")
    return value


def _non_empty_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogValidationError(f"{location} must be a non-empty string")
    return value


def _required(mapping: dict[str, Any], field: str, location: str) -> Any:
    if field not in mapping:
        raise CatalogValidationError(f"{location}.{field} is required")
    return mapping[field]


def _json(path: Path) -> dict[str, Any]:
    try:
        return _object(json.loads(path.read_text(encoding="utf-8")), str(path))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CatalogValidationError(f"cannot read valid JSON from {path}: {error}") from error


def _timestamp(value: Any, location: str) -> datetime:
    text = _non_empty_string(value, location)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise CatalogValidationError(f"{location} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise CatalogValidationError(f"{location} must include a timezone")
    return parsed


def _uuid_v7(value: Any, location: str) -> str:
    text = _non_empty_string(value, location)
    try:
        parsed = uuid.UUID(text)
    except ValueError as error:
        raise CatalogValidationError(f"{location} must be a UUID") from error
    if parsed.version != 7:
        raise CatalogValidationError(f"{location} must be UUIDv7")
    if str(parsed) != text.lower():
        raise CatalogValidationError(f"{location} must use canonical lowercase UUID notation")
    return text


def _resource(root: Path, relative: Any, location: str) -> Path:
    value = _non_empty_string(relative, location)
    parts = value.split("/")
    if (
        value.startswith("/")
        or "\\" in value
        or "://" in value
        or "?" in value
        or "#" in value
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise CatalogValidationError(f"{location} must be a safe relative resource path")

    resolved_root = root.resolve()
    resolved = (root / value).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise CatalogValidationError(f"{location} resolves outside {root}")
    if not resolved.is_file():
        raise CatalogValidationError(f"{location} does not resolve to a file: {value}")
    return resolved


def _validate_allergens(data: dict[str, Any], manifest: dict[str, Any], location: str) -> None:
    default_locale = _non_empty_string(
        _required(data, "default_locale", location), f"{location}.default_locale"
    )
    allergens = _array(_required(data, "allergens", location), f"{location}.allergens")
    count = _required(manifest, "allergen_count", "manifest")
    if not isinstance(count, int) or isinstance(count, bool) or count != len(allergens):
        raise CatalogValidationError(
            f"manifest.allergen_count must equal the {len(allergens)} allergen entries"
        )

    entries: dict[str, dict[str, Any]] = {}
    codes: set[str] = set()
    components: dict[str, list[str]] = {}

    for index, raw_entry in enumerate(allergens):
        entry_location = f"{location}.allergens[{index}]"
        entry = _object(raw_entry, entry_location)
        for field in (
            "meta",
            "code",
            "liquid",
            "igg",
            "mix",
            "recombinant",
            "approval_state",
            "component_allergen_ids",
            "translations",
        ):
            _required(entry, field, entry_location)

        meta = _object(entry["meta"], f"{entry_location}.meta")
        for field in ("id", "created_at", "updated_at", "deleted_at"):
            _required(meta, field, f"{entry_location}.meta")
        allergen_id = _uuid_v7(meta["id"], f"{entry_location}.meta.id")
        if allergen_id in entries:
            raise CatalogValidationError(f"duplicate allergen UUIDv7 {allergen_id}")

        created_at = _timestamp(meta["created_at"], f"{entry_location}.meta.created_at")
        updated_at = _timestamp(meta["updated_at"], f"{entry_location}.meta.updated_at")
        if updated_at < created_at:
            raise CatalogValidationError(f"{entry_location}.meta.updated_at precedes created_at")
        if meta["deleted_at"] is not None:
            deleted_at = _timestamp(meta["deleted_at"], f"{entry_location}.meta.deleted_at")
            if deleted_at < created_at:
                raise CatalogValidationError(
                    f"{entry_location}.meta.deleted_at precedes created_at"
                )

        code = _non_empty_string(entry["code"], f"{entry_location}.code")
        normalized_code = code.upper()
        if normalized_code in codes:
            raise CatalogValidationError(f"duplicate allergen code {code}")
        codes.add(normalized_code)

        for field in ("liquid", "igg", "mix", "recombinant"):
            if not isinstance(entry[field], bool):
                raise CatalogValidationError(f"{entry_location}.{field} must be boolean")
        expected_recombinant = normalized_code.startswith(("R", "N"))
        if entry["recombinant"] is not expected_recombinant:
            raise CatalogValidationError(
                f"{entry_location}.recombinant must be {str(expected_recombinant).lower()} "
                f"for code {code}"
            )

        if entry["approval_state"] not in {"approved", "not_approved"}:
            raise CatalogValidationError(
                f"{entry_location}.approval_state must be approved or not_approved"
            )

        component_values = _array(
            entry["component_allergen_ids"], f"{entry_location}.component_allergen_ids"
        )
        component_ids = [
            _uuid_v7(value, f"{entry_location}.component_allergen_ids[{component_index}]")
            for component_index, value in enumerate(component_values)
        ]
        if len(component_ids) != len(set(component_ids)):
            raise CatalogValidationError(f"{entry_location} contains duplicate components")
        if allergen_id in component_ids:
            raise CatalogValidationError(f"{entry_location} references itself")
        if entry["mix"] and not component_ids:
            raise CatalogValidationError(f"{entry_location} is a mixture without components")
        if not entry["mix"] and component_ids:
            raise CatalogValidationError(f"{entry_location} is not a mixture but has components")

        translations = _object(entry["translations"], f"{entry_location}.translations")
        if default_locale not in translations:
            raise CatalogValidationError(
                f"{entry_location}.translations lacks default locale {default_locale}"
            )
        for locale, raw_translation in translations.items():
            translation = _object(raw_translation, f"{entry_location}.translations.{locale}")
            _non_empty_string(
                _required(translation, "label", f"{entry_location}.translations.{locale}"),
                f"{entry_location}.translations.{locale}.label",
            )

        entries[allergen_id] = entry
        components[allergen_id] = component_ids

    for allergen_id, component_ids in components.items():
        for component_id in component_ids:
            if component_id not in entries:
                raise CatalogValidationError(
                    f"allergen {allergen_id} references missing component {component_id}"
                )
            if (
                entries[allergen_id]["approval_state"] == "approved"
                and entries[component_id]["approval_state"] != "approved"
            ):
                raise CatalogValidationError(
                    f"approved mixture {allergen_id} references non-approved component "
                    f"{component_id}"
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(allergen_id: str) -> None:
        if allergen_id in visiting:
            raise CatalogValidationError(f"mixture reference cycle reaches {allergen_id}")
        if allergen_id in visited:
            return
        visiting.add(allergen_id)
        for component_id in components[allergen_id]:
            visit(component_id)
        visiting.remove(allergen_id)
        visited.add(allergen_id)

    for allergen_id in entries:
        visit(allergen_id)


def _validate_catalog(catalog_root: Path) -> None:
    index_path = catalog_root / "index.json"
    index = _json(index_path)
    catalog_id = _non_empty_string(_required(index, "catalog_id", str(index_path)), "catalog_id")
    if catalog_id != catalog_root.name:
        raise CatalogValidationError(
            f"{index_path}: catalog_id {catalog_id!r} must match directory {catalog_root.name!r}"
        )

    latest_version = _non_empty_string(
        _required(index, "latest_version", str(index_path)), "latest_version"
    )
    versions = _array(_required(index, "versions", str(index_path)), "versions")
    if not versions:
        raise CatalogValidationError(f"{index_path}: versions must not be empty")

    version_names: set[str] = set()
    manifest_paths: set[Path] = set()
    for entry_index, raw_version in enumerate(versions):
        location = f"{index_path}.versions[{entry_index}]"
        version = _object(raw_version, location)
        for field in (
            "catalog_version",
            "schema_version",
            "minimum_client_version",
            "manifest_url",
        ):
            _required(version, field, location)

        version_name = _non_empty_string(version["catalog_version"], f"{location}.catalog_version")
        if not CATALOG_VERSION_PATTERN.fullmatch(version_name):
            raise CatalogValidationError(f"{location}.catalog_version has an invalid format")
        if version_name in version_names:
            raise CatalogValidationError(f"{index_path}: duplicate version {version_name}")
        version_names.add(version_name)

        schema_version = version["schema_version"]
        if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version < 1:
            raise CatalogValidationError(f"{location}.schema_version must be a positive integer")
        minimum_client_version = _non_empty_string(
            version["minimum_client_version"], f"{location}.minimum_client_version"
        )
        if not CLIENT_VERSION_PATTERN.fullmatch(minimum_client_version):
            raise CatalogValidationError(f"{location}.minimum_client_version is invalid")

        manifest_path = _resource(catalog_root, version["manifest_url"], f"{location}.manifest_url")
        if manifest_path in manifest_paths:
            raise CatalogValidationError(f"{index_path}: duplicate manifest path {manifest_path}")
        manifest_paths.add(manifest_path)
        manifest = _json(manifest_path)

        for field in (
            "catalog_id",
            "catalog_version",
            "schema_version",
            "generated_at",
            "minimum_client_version",
            "download_url",
            "sha256",
            "file_size",
        ):
            _required(manifest, field, str(manifest_path))
        for field, expected in (
            ("catalog_id", catalog_id),
            ("catalog_version", version_name),
            ("schema_version", schema_version),
            ("minimum_client_version", minimum_client_version),
        ):
            if manifest[field] != expected:
                raise CatalogValidationError(
                    f"{manifest_path}: {field} must match its index entry"
                )
        _timestamp(manifest["generated_at"], f"{manifest_path}.generated_at")

        data_path = _resource(manifest_path.parent, manifest["download_url"], f"{manifest_path}.download_url")
        if not data_path.is_relative_to(catalog_root.resolve()):
            raise CatalogValidationError(f"{manifest_path}.download_url leaves the catalogue root")
        data_bytes = data_path.read_bytes()
        expected_hash = _non_empty_string(manifest["sha256"], f"{manifest_path}.sha256")
        if not SHA256_PATTERN.fullmatch(expected_hash):
            raise CatalogValidationError(f"{manifest_path}.sha256 must be lowercase SHA-256")
        actual_hash = hashlib.sha256(data_bytes).hexdigest()
        if actual_hash != expected_hash:
            raise CatalogValidationError(
                f"{data_path}: SHA-256 {actual_hash} does not match manifest {expected_hash}"
            )
        file_size = manifest["file_size"]
        if not isinstance(file_size, int) or isinstance(file_size, bool) or file_size < 0:
            raise CatalogValidationError(f"{manifest_path}.file_size must be a non-negative integer")
        if file_size != len(data_bytes):
            raise CatalogValidationError(
                f"{data_path}: size {len(data_bytes)} does not match manifest {file_size}"
            )

        data = _json(data_path)
        if catalog_id == "allergens":
            _validate_allergens(data, manifest, str(data_path))

    if latest_version not in version_names:
        raise CatalogValidationError(
            f"{index_path}: latest_version {latest_version!r} is not listed in versions"
        )


def validate_repository(repository_root: Path) -> list[str]:
    catalogs_root = repository_root / "public" / "catalogs"
    if not catalogs_root.is_dir():
        raise CatalogValidationError(f"catalogue root does not exist: {catalogs_root}")
    catalog_roots = sorted(path for path in catalogs_root.iterdir() if path.is_dir())
    if not catalog_roots:
        raise CatalogValidationError(f"no catalogues found below {catalogs_root}")
    for catalog_root in catalog_roots:
        _validate_catalog(catalog_root)
    return [catalog_root.name for catalog_root in catalog_roots]


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    try:
        catalog_ids = validate_repository(repository_root)
    except CatalogValidationError as error:
        print(f"Catalogue validation failed: {error}", file=sys.stderr)
        return 1
    print(f"Validated {len(catalog_ids)} catalogue(s): {', '.join(catalog_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


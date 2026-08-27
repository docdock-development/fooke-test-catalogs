from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from validate_catalogs import CatalogValidationError, validate_repository


VERSION = "2026.08.27.1"
TIMESTAMP = "2026-08-27T10:00:00.000Z"
FIRST_ID = "01900000-0000-7000-8000-000000000001"
SECOND_ID = "01900000-0000-7000-8000-000000000002"
MIX_ID = "01900000-0000-7000-8000-000000000003"


def allergen(allergen_id: str, code: str, *, recombinant: bool = False) -> dict:
    return {
        "meta": {
            "id": allergen_id,
            "created_at": TIMESTAMP,
            "updated_at": TIMESTAMP,
            "deleted_at": None,
        },
        "code": code,
        "liquid": True,
        "igg": False,
        "mix": False,
        "recombinant": recombinant,
        "approval_state": "approved",
        "component_allergen_ids": [],
        "translations": {"de": {"label": f"Test {code}"}},
    }


def valid_allergen_data() -> dict:
    first = allergen(FIRST_ID, "E1")
    second = allergen(SECOND_ID, "R1", recombinant=True)
    mixture = allergen(MIX_ID, "MX1")
    mixture["mix"] = True
    mixture["component_allergen_ids"] = [FIRST_ID, SECOND_ID]
    return {"default_locale": "de", "allergens": [first, second, mixture]}


class CatalogueRepository:
    def __init__(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)

    def close(self) -> None:
        self._temporary.cleanup()

    def write_allergens(self, data: dict | None = None) -> Path:
        catalog_root = self.root / "public" / "catalogs" / "allergens"
        version_root = catalog_root / "versions" / VERSION
        version_root.mkdir(parents=True)
        payload = (json.dumps(data or valid_allergen_data(), indent=2) + "\n").encode()
        data_path = version_root / "allergens.json"
        data_path.write_bytes(payload)
        manifest = {
            "catalog_id": "allergens",
            "catalog_version": VERSION,
            "schema_version": 6,
            "generated_at": TIMESTAMP,
            "minimum_client_version": "0.2.0",
            "download_url": "allergens.json",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "file_size": len(payload),
            "allergen_count": len((data or valid_allergen_data())["allergens"]),
        }
        (version_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        index = {
            "catalog_id": "allergens",
            "latest_version": VERSION,
            "versions": [
                {
                    "catalog_version": VERSION,
                    "schema_version": 6,
                    "minimum_client_version": "0.2.0",
                    "manifest_url": f"versions/{VERSION}/manifest.json",
                }
            ],
        }
        (catalog_root / "index.json").write_text(json.dumps(index), encoding="utf-8")
        return data_path

    def write_generic(self, catalog_id: str) -> None:
        catalog_root = self.root / "public" / "catalogs" / catalog_id
        version_root = catalog_root / "versions" / VERSION
        version_root.mkdir(parents=True)
        payload = (json.dumps({"entries": []}, indent=2) + "\n").encode()
        (version_root / "catalog.json").write_bytes(payload)
        manifest = {
            "catalog_id": catalog_id,
            "catalog_version": VERSION,
            "schema_version": 1,
            "generated_at": TIMESTAMP,
            "minimum_client_version": "0.2.0",
            "download_url": "catalog.json",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "file_size": len(payload),
        }
        (version_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        index = {
            "catalog_id": catalog_id,
            "latest_version": VERSION,
            "versions": [
                {
                    "catalog_version": VERSION,
                    "schema_version": 1,
                    "minimum_client_version": "0.2.0",
                    "manifest_url": f"versions/{VERSION}/manifest.json",
                }
            ],
        }
        (catalog_root / "index.json").write_text(json.dumps(index), encoding="utf-8")


class ValidateCataloguesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = CatalogueRepository()

    def tearDown(self) -> None:
        self.repository.close()

    def test_accepts_valid_allergen_catalogue(self) -> None:
        self.repository.write_allergens()

        self.assertEqual(validate_repository(self.repository.root), ["allergens"])

    def test_accepts_an_additional_generic_catalogue(self) -> None:
        self.repository.write_allergens()
        self.repository.write_generic("assay-methods")

        self.assertEqual(
            validate_repository(self.repository.root), ["allergens", "assay-methods"]
        )

    def test_rejects_checksum_mismatch(self) -> None:
        data_path = self.repository.write_allergens()
        data_path.write_text("{}", encoding="utf-8")

        with self.assertRaisesRegex(CatalogValidationError, "SHA-256"):
            validate_repository(self.repository.root)

    def test_rejects_missing_mixture_component(self) -> None:
        data = valid_allergen_data()
        data["allergens"][2]["component_allergen_ids"] = [
            "01900000-0000-7000-8000-000000000099"
        ]
        self.repository.write_allergens(data)

        with self.assertRaisesRegex(CatalogValidationError, "missing component"):
            validate_repository(self.repository.root)

    def test_rejects_incorrect_recombinant_classification(self) -> None:
        data = valid_allergen_data()
        data["allergens"][1]["recombinant"] = False
        self.repository.write_allergens(data)

        with self.assertRaisesRegex(CatalogValidationError, "recombinant must be true"):
            validate_repository(self.repository.root)


if __name__ == "__main__":
    unittest.main()

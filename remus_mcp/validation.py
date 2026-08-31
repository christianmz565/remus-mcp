"""Strict validation for create/update."""
from __future__ import annotations

from typing import Any

from .config import MAX_NAME_LENGTH
from .jet.mdbtools import export_table
from .jet.schema import REQUIRED_FIELDS, WRITABLE_TYPES, VALUE_TABLES
def validate_create(type_name: str, data: dict[str, Any], db_path: str) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if type_name not in WRITABLE_TYPES and type_name != "trace":
        errors.append({"field": "type", "code": "READ_ONLY_TYPE", "message": f"Type {type_name} is read-only"})
    # Required fields
    req = REQUIRED_FIELDS.get(type_name, [])
    for f in req:
        if f not in data or data[f] is None or (isinstance(data[f], str) and not data[f].strip()):
            errors.append({"field": f, "code": "REQUIRED", "message": f"Field {f} is required for {type_name}"})
    # Name length
    if "name" in data and data["name"] is not None and len(str(data["name"])) > MAX_NAME_LENGTH:
        errors.append({"field": "name", "code": "TOO_LONG", "message": f"name exceeds {MAX_NAME_LENGTH} characters"})
    # FK: document exists if provided
    if "document" in data and data["document"] is not None:
        try:
            doc_oid = int(data["document"])
            found = False
            has_any_doc = False
            for doc_table in ["C_RequirementsSpecification", "D_RequirementsSpecification", "DefectsSpecification", "ChangeRequestsSpecification"]:
                rows = export_table(db_path, doc_table)
                if rows:
                    has_any_doc = True
                for r in rows:
                    if int(r.get("oid", -1)) == doc_oid:
                        found = True
                        break
                if found:
                    break
            if not found and has_any_doc:
                errors.append({"field": "document", "code": "FK_NOT_FOUND", "message": f"document oid {doc_oid} not found"})
        except Exception as e:
            errors.append({"field": "document", "code": "INVALID", "message": str(e)})
    # FK: parent if provided should exist in Section/Paragraph etc. Loose check: any table
    if "parent" in data and data["parent"] is not None:
        try:
            parent_oid = int(data["parent"])
            found = False
            for tbl in ["Section", "Appendix", "Paragraph"]:
                rows = export_table(db_path, tbl)
                for r in rows:
                    if int(r.get("oid", -1)) == parent_oid:
                        found = True
                        break
                if found:
                    break
            if not found:
                errors.append({"field": "parent", "code": "FK_NOT_FOUND", "message": f"parent oid {parent_oid} not found"})
        except Exception as e:
            errors.append({"field": "parent", "code": "INVALID", "message": str(e)})
    # Enum FKs: importance etc. Check against value tables if provided
    for fk, table in [("importance", "ImportanceValue"), ("urgency", "UrgencyValue"), ("status", "StatusValue"), ("stability", "StabilityValue")]:
        if fk in data and data[fk] is not None:
            try:
                val = int(data[fk])
                rows = export_table(db_path, table)
                oids = {int(r.get("oid", -999)) for r in rows}
                if val not in oids:
                    errors.append({"field": fk, "code": "FK_NOT_FOUND", "message": f"{fk}={val} not in {table}"})
            except Exception as e:
                errors.append({"field": fk, "code": "INVALID", "message": str(e)})
    return errors

def validate_update(type_name: str, patch: dict[str, Any], db_path: str) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if "name" in patch and patch["name"] is not None and len(str(patch["name"])) > MAX_NAME_LENGTH:
        errors.append({"field": "name", "code": "TOO_LONG", "message": f"name exceeds {MAX_NAME_LENGTH} characters"})
    # Validate FKs present in patch similar to create
    for fk, table in [("importance", "ImportanceValue"), ("urgency", "UrgencyValue"), ("status", "StatusValue"), ("stability", "StabilityValue")]:
        if fk in patch and patch[fk] is not None:
            try:
                val = int(patch[fk])
                rows = export_table(db_path, table)
                oids = {int(r.get("oid", -999)) for r in rows}
                if val not in oids:
                    errors.append({"field": fk, "code": "FK_NOT_FOUND", "message": f"{fk}={val} not in {table}"})
            except Exception as e:
                errors.append({"field": fk, "code": "INVALID", "message": str(e)})
    return errors

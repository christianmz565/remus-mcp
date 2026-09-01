"""Table to entity mapping from mdb-schema / DTD."""

from __future__ import annotations

# Canonical mapping table name -> MCP type (lower_snake).
# Table names are Jet names exactly as seen via mdb-tables.
ENTITY_TABLES: dict[str, str] = {
    "Section": "section",
    "Appendix": "appendix",
    "Paragraph": "paragraph",
    "GraphicFile": "graphic_file",
    "GlossaryItem": "glossary_item",
    "Organization": "organization",
    "Stakeholder": "stakeholder",
    "Meeting": "meeting",
    "Objective": "objective",
    "Actor": "actor",
    "InformationRequirement": "information_requirement",
    "ConstraintRequirement": "constraint_requirement",
    "UseCase": "use_case",
    "FunctionalRequirement": "functional_requirement",
    "NonFunctionalRequirement": "non_functional_requirement",
    "ObjectType": "object_type",
    "UserDefinedValueType": "user_defined_value_type",
    "AssociationType": "association_type",
    "SystemOperation": "system_operation",
    "Alternative": "alternative",
    "Conflict": "conflict",
    "Defect": "defect",
    "ChangeRequest": "change_request",
    "TraceabilityMatrix": "traceability_matrix",
    "Trace": "trace",
    "Attribute": "attribute",
    "Component": "component",
    "Role": "role",
    "Parameter": "parameter",
    "InvariantExpression": "invariant_expression",
    "Step": "step",
    # Specification documents
    "C_RequirementsSpecification": "c_requirements_specification",
    "D_RequirementsSpecification": "d_requirements_specification",
    "DefectsSpecification": "defects_specification",
    "ChangeRequestsSpecification": "change_requests_specification",
    # Join / auxiliary
    "Change": "change",
    "IsAuthorOf": "is_author_of",
    "IsPreparedFor": "is_prepared_for",
    "IsPreparedBy": "is_prepared_by",
}
DOC_SPEC_TYPES: frozenset[str] = frozenset({
    "c_requirements_specification",
    "d_requirements_specification",
    "defects_specification",
    "change_requests_specification",
})

SPEC_OBJECT_TYPES: frozenset[str] = frozenset({
    "section",
    "appendix",
    "paragraph",
    "graphic_file",
    "glossary_item",
    "organization",
    "stakeholder",
    "meeting",
    "objective",
    "actor",
    "information_requirement",
    "constraint_requirement",
    "use_case",
    "functional_requirement",
    "non_functional_requirement",
    "object_type",
    "user_defined_value_type",
    "association_type",
    "system_operation",
    "conflict",
    "defect",
    "change_request",
    "traceability_matrix",
})

VALID_CHANGE_OP_TYPES: frozenset[str] = frozenset({"C", "U", "D", "S"})

# Reverse
TYPE_TO_TABLE: dict[str, str] = {}
for _tbl, _typ in ENTITY_TABLES.items():
    # keep first table for each type (prefer canonical)
    if _typ not in TYPE_TO_TABLE:
        TYPE_TO_TABLE[_typ] = _tbl
# Ensure traceability_matrix alias not colliding: TraceabilityMatrix is primary
# Add alias for plural? Already handled.

TABLE_TO_TYPE: dict[str, str] = {k: v for k, v in ENTITY_TABLES.items()}

# Value lookup tables (read-only)
VALUE_TABLES = {
    "ImportanceValue",
    "UrgencyValue",
    "StatusValue",
    "StabilityValue",
    "ChangeRequestStatusValue",
    "DefectStatusValue",
    "DefectTypeValue",
    "TerminationValue",
    "TimeUnitValue",
}

WRITABLE_TYPES: set[str] = {
    t
    for t in TYPE_TO_TABLE
    if TYPE_TO_TABLE[t] not in VALUE_TABLES and t not in {"change"}  # Change is system-managed
}

# Required fields per type (minimal, from schema NOT NULL + DTD)
REQUIRED_FIELDS: dict[str, list[str]] = {
    "section": ["name"],
    "appendix": ["name"],
    "paragraph": ["name"],
    "graphic_file": ["name"],
    "glossary_item": ["name"],
    "organization": ["name"],
    "stakeholder": ["name"],
    "meeting": ["name"],
    "objective": ["name"],
    "actor": ["name"],
    "information_requirement": ["name"],
    "constraint_requirement": ["name"],
    "use_case": ["name"],
    "functional_requirement": ["name"],
    "non_functional_requirement": ["name"],
    "object_type": ["name"],
    "user_defined_value_type": ["name"],
    "association_type": ["name"],
    "system_operation": ["name"],
    "alternative": [],
    "conflict": ["name"],
    "defect": ["name"],
    "change_request": ["name"],
    "traceability_matrix": ["name"],
    "trace": ["source", "target"],
    "attribute": ["name"],
    "component": ["name"],
    "role": ["name"],
    "parameter": ["name"],
    "invariant_expression": [],
    "step": [],
    "c_requirements_specification": ["name"],
    "d_requirements_specification": ["name"],
    "defects_specification": ["name"],
    "change_requests_specification": ["name"],
    "is_prepared_for": ["document", "organization"],
    "is_prepared_by": ["document", "organization"],
    "is_author_of": ["stakeholder", "specificationObject"],
}

# Ordered list for RemType enum values (excluding doc specs and internals)
REM_TYPE_VALUES: list[str] = sorted(
    [
        "section",
        "appendix",
        "paragraph",
        "graphic_file",
        "glossary_item",
        "organization",
        "stakeholder",
        "meeting",
        "objective",
        "actor",
        "information_requirement",
        "constraint_requirement",
        "use_case",
        "functional_requirement",
        "non_functional_requirement",
        "object_type",
        "user_defined_value_type",
        "association_type",
        "system_operation",
        "alternative",
        "conflict",
        "defect",
        "change_request",
        "traceability_matrix",
        "attribute",
        "component",
        "role",
        "parameter",
        "invariant_expression",
        "step",
        "trace",
        "c_requirements_specification",
        "d_requirements_specification",
        "defects_specification",
        "change_requests_specification",
        "is_prepared_for",
        "is_prepared_by",
        "is_author_of",
    ]
)

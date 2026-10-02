import re

import pytest
from catalog_metadata.ht_indexer_config import ProcessingStatus
from ht_indexer_monitoring.ht_indexer_tracktable import HT_INDEXER_TRACKTABLE

# ProcessingStatus values are written to MySQL ENUM columns. These tests pin the exact
# strings and keep the enum in sync with the CREATE TABLE text in HT_INDEXER_TRACKTABLE.


def _extract_ddl_enum_values(column_name: str) -> set[str]:
    """Helper to parse raw SQL DDL and extract native ENUM string definitions."""
    match = re.search(rf"\b{column_name}\s+ENUM\(([^)]*)\)", HT_INDEXER_TRACKTABLE, re.IGNORECASE)
    assert match is not None, (
        f"Database schema validation error: No ENUM layout found for column '{column_name}'"
    )
    return {val.strip().strip("'") for val in match.group(1).split(",")}


class TestDatabaseSchemaAndEnumAlignment:
    """Pins Python execution configurations directly against raw SQL tracking DDL structures."""

    def test_processing_status_enum_members_use_lowercase_string_instances(self) -> None:
        """Ensures all enum members are valid strings and match standardized casing rules."""
        for member in ProcessingStatus:
            assert isinstance(member.value, str), (
                f"Enum member {member.name} value is not a string type."
            )
            assert member.value == member.name.lower(), (
                f"Enum value variation mismatch: Expected '{member.name.lower()}', got '{member.value}'."
            )

    def test_core_status_column_matches_python_enum_definitions_exactly(self) -> None:
        """The master tracking column must align 1:1 with standard processing states."""
        ddl_values = _extract_ddl_enum_values("status")
        enum_values = {member.value for member in ProcessingStatus}

        assert ddl_values == enum_values, (
            f"DDL schema drift detected! MySQL enum values {ddl_values} do not align with Python definitions {enum_values}."
        )

    @pytest.mark.parametrize(
        "stage_column", ["retriever_status", "generator_status", "indexer_status"]
    )
    def test_pipeline_sub_stages_are_supported_by_processing_status_enum(
        self, stage_column: str
    ) -> None:
        """Sub-stage track columns can be subsets, but cannot contain arbitrary strings outside ProcessingStatus."""
        ddl_values = _extract_ddl_enum_values(stage_column)
        enum_values = {member.value for member in ProcessingStatus}

        assert ddl_values.issubset(enum_values), (
            f"DDL column '{stage_column}' contains unmapped tracking strings: {ddl_values - enum_values}. "
            f"Please register these states inside the ProcessingStatus enum."
        )

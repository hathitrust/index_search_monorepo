from pymarc import Record

def extract_control_number(record: Record) -> str:
    """
    Extracts the unique identifier assigned to the MARC record.

    Parameters:
    record (Record): The record object from which the control number is extracted.

    Returns:
    str: The extracted control number as a string, or an empty string if the field
    is not present.
    """
    field = record.get_fields("001")
    if field:
        return field[0].value()
    return ""
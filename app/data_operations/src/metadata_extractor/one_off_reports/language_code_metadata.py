from metadata_extractor.one_off_reports.base_one_off_report import BaseOneOffReport


class LanguageCodeMetadata(BaseOneOffReport):

    def match_record(self, record):
        # Look for the 008 field and extract the language code (positions 35-37)
        field_008 = record.get_fields("008")
        if not field_008:
            return None
        language_code = field_008[0].data[35:38]
        return {"language_code": language_code}
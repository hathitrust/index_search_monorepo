import pandas as pd
from lxml import etree

# Create csv file
catalog_csv_file = open("catalog_fields.csv", "w", encoding="utf-8")

# Read XML file
parser = etree.XMLParser()
tree = etree.parse("full_text_schema.xml", parser)

root = tree.getroot()

schema_fields_dic = {}
for field in root.findall("field"):
    schema_fields_dic[field.attrib["name"]] = field.attrib
    schema_fields_dic[field.attrib["name"]].update({"schema.xml": "Exist"})
    schema_fields_dic[field.attrib["name"]].update({"origen": ""})

for field in root.findall("copyField"):
    name = field.attrib["dest"]
    if name in schema_fields_dic:
        schema_fields_dic[name].update(
            {"origen": f"copyField by {field.attrib['source']}"}
        )

schema_fields_list = list(schema_fields_dic.values())
df = pd.DataFrame.from_dict(schema_fields_list, orient="columns")

df.to_csv(sep="\t", path_or_buf="full_text_fields.csv", encoding="utf-8")

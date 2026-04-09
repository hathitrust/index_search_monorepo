from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_marc_json_reader import dict_to_pymarc_record

logger = get_ht_logger(name=__name__)

def test_dict_to_pymarc_record():

    data = {"leader":"00739nam a22002771  4500","fields":[{"001":"000000075"},{"003":"MiAaHDL"},{"005":"20130211000000.0"},{"006":"m        d        "},{"007":"cr bn ---auaua"},{"008":"880715t19691914nyu          |000 0 eng  "},{"010":{"subfields":[{"a":"69014047"}],"ind1":" ","ind2":" "}},{"035":{"subfields":[{"a":"(MiU)000000075"}],"ind1":" ","ind2":" "}},{"035":{"subfields":[{"a":"sdr-miu000000075"}],"ind1":" ","ind2":" "}},{"035":{"subfields":[{"a":"sdr-uva.u523160"}],"ind1":" ","ind2":" "}},{"035":{"subfields":[{"a":"(OCoLC)4950"}],"ind1":" ","ind2":" "}},{"035":{"subfields":[{"a":"(CaOTULAS)159818094"}],"ind1":" ","ind2":" "}},{"035":{"subfields":[{"a":"(RLIN)MIUG0004950-B"}],"ind1":" ","ind2":" "}},{"040":{"subfields":[{"a":"DLC"},{"c":"DLC"},{"d":"MiU"}],"ind1":" ","ind2":" "}},{"050":{"subfields":[{"a":"F1234"},{"b":".R32 1969b"}],"ind1":"0","ind2":"0"}},{"082":{"subfields":[{"a":"972.08/1"}],"ind1":"0","ind2":" "}},{"100":{"subfields":[{"a":"Reed, John,"},{"d":"1887-1920."}],"ind1":"1","ind2":" "}},
                                                          {"245":{"subfields":[{"a":"Insurgent Mexico."}],"ind1":"1","ind2":"0"}},{"260":{"subfields":[{"a":"New York :"},{"b":"Greenwood Press,"},{"c":"[1969, c1914]"}],"ind1":" ","ind2":" "}},{"300":{"subfields":[{"a":"viii, 325 p."},{"c":"23 cm."}],"ind1":" ","ind2":" "}},{"538":{"subfields":[{"a":"Mode of access: Internet."}],"ind1":" ","ind2":" "}},{"651":{"subfields":[{"a":"Mexico"},{"x":"History"},{"y":"1910-1946."}],"ind1":" ","ind2":"0"}},{"970":{"subfields":[{"a":"BK"}],"ind1":" ","ind2":" "}},{"974":{"subfields":[{"b":"MIU"},{"c":"MIU"},{"d":"20161214"},{"s":"google"},{"u":"mdp.39015004214865"},{"y":"1914"},{"r":"pd"},{"q":"bib"},{"a":"google"}],"ind1":" ","ind2":" "}}]}

    pymarc_record = dict_to_pymarc_record(data)

    assert pymarc_record['245'].indicator1 == "1"
    assert pymarc_record['245'].indicator2 == "0"
    assert pymarc_record['245'].get_subfields('a') == ["Insurgent Mexico."]
    assert pymarc_record["260"].get_subfields("a") == ["New York :"]
    assert pymarc_record['260'].get_subfields('b') == ["Greenwood Press,"]
    assert pymarc_record["260"].get_subfields("c") == ["[1969, c1914]"]
    assert pymarc_record["260"].indicator1 == " "
    assert pymarc_record["260"].indicator2 == " "



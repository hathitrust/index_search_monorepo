from pypairtree import pairtree
from ht_document.ht_document import HtDocument
from pathlib import Path
import os

os.environ["SDR_DIR"] = f"{Path(__file__).parents[1]}/data/document_generator"


def test_get_document_pair_path():
    doc_name = "39015051333915"

    path = pairtree.get_pair_path(doc_name)
    assert path == "/39/01/50/51/33/39/15/39015051333915"


def test_get_document_pairtree_path():
    namespace, obj = "uc2.ark:/13960/t4mk66f1d".split(".")

    sanitized_str = pairtree.sanitizeString(obj)
    path = pairtree.get_pair_path(sanitized_str)
    assert path == "/ar/k+/=1/39/60/=t/4m/k6/6f/1d/ark+=13960=t4mk66f1d"


def test_get_namespace():
    namespace = HtDocument.get_namespace("uc2.ark:/13960/t4mk66f1d")
    assert namespace == "uc2"


def test_get_object_id():
    namespace = HtDocument.get_object_id("uc2.ark:/13960/t4mk66f1d")
    assert namespace == "ark:/13960/t4mk66f1d"


def test_document_several_points():
    document_id = "miun.adh1541.0001.001"

    namespace = HtDocument.get_namespace(document_id)
    assert namespace == "miun"

    obj_id = HtDocument.get_object_id(document_id)
    assert obj_id == "adh1541.0001.001"


def test_pairpath_document_several_points():
    assert "miun,adh1541,0001,001" == pairtree.sanitizeString("miun.adh1541.0001.001")


def test_document_filesystem_folder():
    # TODO: USE a data_sample folder to  check the source_path
    ht_doc = HtDocument(document_id="mb.39015078560292_test")

    assert ht_doc.obj_id == "39015078560292_test"
    assert ht_doc.target_path == "/tmp/39015078560292_test"
    assert ht_doc.namespace == "mb"
    assert ht_doc.file_name == "39015078560292_test"
    # assert ht_doc.source_path == f"{os.environ.get('SDR_DIR')}/{ht_doc.file_name}"

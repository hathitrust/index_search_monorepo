from pypairtree import pairtree


def test_get_document_pair_path():
    doc_name = "39015051333915"

    path = pairtree.get_pair_path(doc_name)
    assert path == "/39/01/50/51/33/39/15/39015051333915"

# What is the path of this document? What is the right uc2.ark:/13960/t4mk66f1d

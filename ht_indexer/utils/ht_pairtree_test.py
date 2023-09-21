from pypairtree import pairtree


def test_get_document_pair_path():
    doc_name = "39015051333915"

    path = pairtree.get_pair_path(doc_name)
    assert path == "/39/01/50/51/33/39/15/39015051333915"


def test_get_document_pait_path():
    namespace, obj = "uc2.ark:/13960/t4mk66f1d".split('.')

    sanitized_str = pairtree.sanitizeString(obj)
    path = pairtree.get_pair_path(sanitized_str)
    assert path == "/ar/k+/=1/39/60/=t/4m/k6/6f/1d/ark+=13960=t4mk66f1d"

# What is the path of this document? What is the right uc2.ark:/13960/t4mk66f1d
# scp: /sdr1/obj/uc2/pairtree_root/ar/k://1/39/60//t/4m/k6/6f/1d/ark:/13960/t4mk66f1d/ark:/13960/t4mk66f1d.zip: No such file or directory
# INFO:root:Download /sdr1/obj/uc2/pairtree_root/ar/k://1/39/60//t/4m/k6/6f/1d/ark:/13960/t4mk66f1d/ark:/13960/t4mk66f1d.zip to /tmp/
# INFO:root:Document uc2.ark:/13960/t4mk66f1d failed 'int' object is not callable

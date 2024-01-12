"""
Implement here the function to check the access rights of the user.
We should include this feature to the full-text search query
"""

#Variable copy from mdp-lib/RightsGlobals.pm
g_access_requires_holdings_attribute_values = (2, 3, 4, 5, 6, 16) # SSD only, if institution holds
SSD_USER = 3
g_access_requires_brittle_holdings_attribute_value = 3 # Some users, if institution holds


def get_fulltext_attr_list(C):
    """
    This logic is implemented in mdp-lib/Access/Rights.pm

    Function to get fulltext attribute list
    :param C:
    :return:
    """
    return C.get_config('fulltext_attr_list')

def get_access_type_determination(C):
    """
    This logic is implemented in mdp-lib/Access/Rights.pm

    Function to get access type determination
    :param C:
    :return:
    """
    return C.get_config('access_type_determination')
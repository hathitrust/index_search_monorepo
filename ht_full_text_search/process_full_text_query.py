import os
import sys

# Set up paths for local libraries -- must come first
sys.path.insert(0, os.getenv('SDRROOT') + '/mdp-lib/Utils')
sys.path.insert(0, os.getenv('SDRROOT') + '/ls/lib/Config')
sys.path.insert(0, os.getenv('SDRROOT') + '/ls/cgi')
sys.path.insert(0, os.getenv('SDRROOT') + '/ls/lib/Config')

# Magic
#import Attribute::Handlers

# MBooks
#import Utils
#import Debug::DUtils
#import MdpGlobals
#import App
#import Database
#import MdpConfig
#import Action::Bind
#import Context
#import Session
#import Auth::Auth
#import Access::Rights
#import LS::Controller
#import LS::FacetConfig
#import LS::Query::Facets

VERSION = 0.2000

# ============================ Main ===================================

# Establish and populate the Context.  Order dependent.
C = Context()

# Configuration
#config = MdpConfig.MdpConfig(Utils.get_uber_config_path('ls'), os.getenv('SDRROOT') + '/ls/lib/Config/global.conf',
#                             os.getenv('SDRROOT') + '/ls/lib/Config/local.conf')
#C.set_object('MdpConfig', config)

# Additional configuration for facets and relevance weighting
#facet_config = LS::FacetConfig.LS::FacetConfig(os.getenv('SDRROOT') + '/ls/lib/Config/facetconfig.pl')
#C.set_object('FacetConfig', facet_config)

query_type = 'full_text'
start_rows = 0
num_rows = 2
user_query_string = None
#Q = LS::Query::Facets.LS::Query::Facets(C, user_query_string, None,
#                                        {'solr_start_row': start_rows, 'solr_num_rows': num_rows,
#                                         'query_type': query_type})
#

# ----------------------------------------------------------------------
# is(processQuery(Q, '"dog food" prices "good eats"', 'any'), '\\"dog food\\" OR prices OR \\"good eats\\"', qq{multiple quotes any})
# is(processQuery(Q, 'dog OR food prices', 'all'), 'dog OR food prices', qq{OR all})
q = 'dog  "food  "prices "  pizza'
i = 1
anyall = 'all'


def processQuery(q, anyall, i=None):
    if i is None:
        i = 1

    processed = Q.process_query(q, i, anyall)
    return processed


processed_result = processQuery(q, anyall, i)

print(f"{q}\\n{processed_result}\\n")
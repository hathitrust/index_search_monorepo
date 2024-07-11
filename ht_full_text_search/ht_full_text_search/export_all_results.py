import requests
import json
import yaml

SOLR_URL="http://localhost:8081/solr/core-1x/query"
SOLR_SHARDS = [f"http://solr-sdr-search-{i}:8081/solr/core-{i}x" for i in range(1,12)]

# This is a quick attempt to do a query to solr more or less as we issue it in
# production and to then export all results using the cursorMark results
# streaming functionality.

# This assumes the 'production' config with all shards available.

# Usage:
#
# poetry run python3 ht_full_text_search/export_all_results.py 'your query string'
#
# If you want to do a phrase query, be sure to surround it in double quotes, e.g.
# poetry run python3 ht_full_text_search/export_all_results.py '"a phrase"'

def default_solr_params():
  return {
     "rows": 500,
     "sort": "id asc",
     "fl": ",".join(["title","author","id"]),
     "wt": "json",
     "shards": ",".join(SOLR_SHARDS)
  }

def send_query(params):
  headers = {
     "Content-type": "application/json"
  }

  response = requests.post(
      url=SOLR_URL, params=params, headers=headers
  )

  return json.loads(response.content)

def output_results(results):
  for result in results['response']['docs']:
    print("\t".join([result['id'],", ".join(result.get('author',[]))," ,".join(result.get('title',[]))]))

def run_cursor(query):
  params = default_solr_params()
  params["cursorMark"] = "*"
  params["q"] = make_query(query)

  while True:
    results = send_query(params)# send_query
    output_results(results)
    if params["cursorMark"] != results["nextCursorMark"]:
      params["cursorMark"] = results["nextCursorMark"]
    else:
      break

def format_boosts(query_fields):
  formatted_boosts = ["^".join(map(str, field)) for field in query_fields]
  return " ".join(formatted_boosts)

def make_query(query):
  return f"{{!edismax {solr_query_params()}}} {query}"

def solr_query_params(config_file="config_files/full_text_search/config_query.yaml", conf_query="ocr"):
  with open(config_file, "r") as file:
      data = yaml.safe_load(file)[conf_query]

      params = {
        "pf": format_boosts(data["pf"]),
        "qf": format_boosts(data["qf"]),
        "mm": data["mm"],
        "tie": data["tie"],
      }
      return " ".join([f"{k}='{v}'" for k,v in params.items()])

if __name__ == "__main__": 
   run_cursor('"poetic justice"')

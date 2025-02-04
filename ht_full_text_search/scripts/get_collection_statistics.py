import os
from argparse import ArgumentParser

import pandas as pd

from config_search import FULL_TEXT_SOLR_URL
from ht_full_text_search.ht_full_text_query import HTFullTextQuery
from ht_full_text_search.ht_full_text_searcher import HTFullTextSearcher

statistics_fields = {"language008_full": "Language dist all",
                  "countryOfPubStr": "Place of Pub",
                  "bothPublishDateRange": "Date Dist",
                  "htsource": "Source Libs",
                  "callnoletters": "LC Class_dist",
                  "rights": "Public Domain Dist"}

def get_category_name(category: str) -> str:

    """Get the category name from the category number
    :param category:
    :return: Category name
    """

    if '-' in category:
        category = category.split('-')[1]
    return category

def map_callnoletters(df, map_file_path):
    """
    Map the two-letter callnoletters fields with the descriptions in the map_call_number.properties file.
    :param df: DataFrame containing the callnoletters field.
    :param map_file_path: Path to the map_call_number.properties file.
    :return: Updated DataFrame with mapped callnoletters.
    """
    # Read the map_call_number.properties file
    with open(map_file_path, 'r', encoding='latin-1') as file:
        lines = file.readlines()

    # Parse the properties file into a dictionary
    callno_map = {}
    general_callno_map = {}
    # TODO Refactor this code to use a regular expression. We are reading the file line until line 445 because we know
    # that after this line, the call number mapping starts and we only want letters.
    for pos in range(3, 445):
        if '=' in lines[pos]:
            key, value = lines[pos].strip().split('=', 1)
            key = key.strip()
            if len(key) >= 2 and key.isalpha():
                callno_map[key] = value.strip()
            else:
                general_callno_map[key.strip()] = value.strip()

    # Create a columns to store the first letter of the callnoletters
    df['first_letter'] = df['value'].str[0]

    # Group this letter and map with general_callno_map
    grouped_df = df.groupby('first_letter')['Count'].sum().reset_index()

    grouped_df['mapped_callnoletters'] = grouped_df['first_letter'].apply(
        lambda x: general_callno_map.get(x.upper(), x))
    grouped_df.drop(['first_letter'], axis=1, inplace=True)
    grouped_df['mapped_callnoletters'] = grouped_df['mapped_callnoletters'].apply(lambda x: get_category_name(x))

    # Create a new column to store the mapped values
    df.drop(['Percent'], axis=1, inplace=True)
    df.drop(['first_letter'], axis=1, inplace=True)
    df.sort_values(by='value', ascending=True, inplace=True)
    df['value'] = df['value'].str.upper()

    return df, grouped_df

def create_dataframe_from_facets(facet_fields):
    """
    Create a DataFrame from Solr facet fields output.
    :param facet_fields: Dictionary containing facet fields and their counts.
    :return: DataFrame with facet fields and counts.
    """
    facet_data = {}

    for field, values in facet_fields.get('facet_fields').items():
        data = []
        for i in range(0, len(values), 2):
            data.append({
                'value': values[i],
                'Count': values[i + 1]
            })
        facet_data[field] = data

    return facet_data


def add_percentage_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a column with the percentage of each row in the DataFrame.
    :param df: DataFrame containing facet fields and counts.
    :return: DataFrame with an additional percentage column.
    """
    total_count = df['Count'].sum()
    df['Percent'] = ((df['Count'] / total_count) * 100).round(2)
    return df


def sort_dataframe_by_percentage(df):
    """
    Sort the DataFrame by the percentage column in descending order.
    :param df: DataFrame containing facet fields, counts, and percentages.
    :return: Sorted DataFrame.
    """
    df_sorted = df.sort_values(by='Percent', ascending=False)
    return df_sorted


def create_copyrights_status(df: pd.DataFrame) -> pd.DataFrame:

    """Transform the right status into a more readable format
    :param df: DataFrame containing the right status and counts.
    :return: DataFrame with the right status in a more readable format.
    """

    # Ignoring these categories 4,6,16, 8, 26, 27
    rights_status = {
        "Public Domain worldwide": ['1', '17'],
        "In Copyright": ['2', '3', '5'],
        "Public Domain in the US": ['9'],
        "in copyright only in the US": ['19'],
        "creative commons or open access": ['7', '10', '11', '12', '13', '14', '15', '18', '20', '21', '22', '23', '24',
                                            '25'],
    }

    df_new = pd.DataFrame()
    for key, values in rights_status.items():
        filtered = df[df['value'].isin(values)]
        filtered['category'] = filtered["value"].apply(lambda x: key)
        df_new = pd.concat([df_new, filtered], ignore_index=True)

    df_new = df_new.groupby('category')['Count'].sum().reset_index()
    return df_new


def create_excel_file(solr_facets_output: dict, file_name: str, map_file_path: str = None):
    """
    Generate the output for each Solr facet field and create an Excel file with different sheets from the data
    :param solr_facets_output: Dictionary containing facet fields and their counts.
    :param file_name: Name of the Excel file to be created.
    :param map_file_path: Path to the map_call_number.properties file.
    :return: None
    """
    # TODO Use the Drive API to upload the file to Google Drive
    with pd.ExcelWriter(file_name, engine='openpyxl') as writer:

        for key, values in solr_facets_output.items():
            df = pd.DataFrame(values)
            df = add_percentage_column(df)

            if key == "bothPublishDateRange":

                # Filter out the date ranges that do not have - in them. For the statistics, we want only a range of dates
                # and not individual years.
                df = df[df['value'].str.contains("-")]

                df_sorted = df.sort_values(by='value', ascending=True)
                df_sorted.to_excel(writer, sheet_name=statistics_fields[key], index=False)
            elif key == "rights":
                df_sorted = create_copyrights_status(df)
                df_sorted.to_excel(writer, sheet_name=statistics_fields[key], index=False)
            elif key == 'callnoletters':
                # TODO Create a function to download the map_call_number.properties file from the repository
                # url = "https://github.com/projectblacklight/blacklight-marc/blob/main/lib/generators/blacklight/marc/templates/config/translation_maps/callnumber_map.properties"


                df_callnoletters, df_general = map_callnoletters(df, map_file_path)
                df_callnoletters.to_excel(writer, sheet_name=f"{statistics_fields[key]}_Callnoletters", index=False)
                df_general.to_excel(writer, sheet_name=f"{statistics_fields[key]}_General", index=False)
            else:
                df_sorted = sort_dataframe_by_percentage(df)
                df_sorted.to_excel(writer, sheet_name=statistics_fields[key], index=False)


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument("--env", default=os.environ.get("HT_ENVIRONMENT", "dev"))
    parser.add_argument("--query_string", help="Query string", default="*:*")
    parser.add_argument(
        "--fl", help="Fields to return", default=["author", "id", "title", "score"]
    )
    parser.add_argument("--solr_url", help="Solr url", default=None)
    parser.add_argument("--operator", help="Operator", type=str)  # Default value is None

    parser.add_argument(
        "--query_config", help="Type of query ocronly or all", default="all"
    )
    parser.add_argument(
        "--facet_config", help="Name of the facet to use all or only_facets", default="only_facets"
    )
    parser.add_argument(
        "--use_shards", help="If the query should include shards", default=False, action="store_true"
    )
    parser.add_argument(
        "--excel_file", help="Path of the excel file to load the statistics", default=None
    )
    parser.add_argument(
        "--map_file_path", help="Path to the map_call_number.properties file", default='/'.join([os.getcwd(), 'map_call_number.properties'])
    )

    # input:
    args = parser.parse_args()

    # Receive as a parameter an specific solr url
    if args.solr_url:
        solr_url = args.solr_url
    else:  # Use the default solr url, depending on the environment. If prod environment, use shards
        solr_url = FULL_TEXT_SOLR_URL[args.env]

    # The current production server does not require user and password

    if args.env == "dev":
        solr_user = os.getenv("SOLR_USER")
        solr_password = os.getenv("SOLR_PASSWORD")
    else:
        solr_user = None
        solr_password = None

    query_string = args.query_string
    fl = args.fl

    # Create query object
    Q = HTFullTextQuery(config_query=args.query_config,
                        config_facet_field=args.facet_config
                        )

    # Create a full text searcher object
    ht_full_search = HTFullTextSearcher(
        solr_url=solr_url, ht_search_query=Q, environment=args.env, user=solr_user, password=solr_password
    )

    solr_output = ht_full_search.solr_facets_output(query_string=None, fl=fl, operator=args.operator
                                                    )

    print(f"Total found {len(solr_output)}")
    print(solr_output)

    data_solr_facets = create_dataframe_from_facets(solr_output)

    create_excel_file(data_solr_facets, "collection_statistics_2024.xlsx", args.map_file_path)

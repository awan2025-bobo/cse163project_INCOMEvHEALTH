"""
Builds small, analysis-ready CSVs with one row per county (keyed by
5-digit FIPS) from the three raw data sources. Missing values are
written as NA.

Raw inputs (left unchanged):
    data/StateAndCountyData.csv           - USDA Food Environment Atlas
    data/PLACES__Local_Data_...csv        - CDC PLACES county data
    data/census_median/census_median_income_2023_raw.json
        - Census ACS API response (downloaded if missing)

Outputs:
    data/core/census_income.csv  - Census income
    data/core/places_health.csv  - CDC PLACES
    data/core/food_atlas.csv     - Food Atlas
"""
import json
import os
import urllib.request

import numpy as np
import pandas as pd

DATA = 'data/'
CENSUS_DIR = DATA + 'census_median/'
CORE = DATA + 'core/'
CHUNK = 200_000
NA = 'NA'

# Census ACS 2019-2023 5-year subject table, S1901_C01_012E is
# median household income (dollars). A key is optional; set the
# CENSUS_API_KEY environment variable to use one.
CENSUS_URL = ('https://api.census.gov/data/2023/acs/acs5/subject'
              '?get=NAME,S1901_C01_012E&for=county:*')
# Census codes for "no estimate" (e.g., too few sample observations).
CENSUS_MISSING_CODES = [-666666666, -999999999, -888888888, -555555555,
                        -333333333, -222222222]
# Food Atlas codes for suppressed or unavailable data.
FOOD_MISSING_CODES = [-9999, -8888]

# CDC PLACES measures to keep (MeasureId values).
PLACES_MEASURES = [
    'DIABETES',    # diagnosed diabetes
    'OBESITY',     # obesity (county level, unlike Food Atlas)
    'BPHIGH',      # high blood pressure
    'CHD',         # coronary heart disease
    'CSMOKING',    # current smoking
    'LPA',         # no leisure-time physical activity
    'ACCESS2',     # no health insurance (18-64)
    'CHECKUP',     # routine checkup in past year
    'GHLTH',       # fair or poor self-rated health
    'MHLTH',       # frequent mental distress
    'DEPRESSION',  # depression
]
# Age-adjusted prevalence is best for comparing counties with different
# age structures. Use 'CrdPrv' instead for crude prevalence.
PLACES_VALUE_TYPE = 'AgeAdjPrv'


def check_columns(path, needed):
    """Reads only the header row and fails clearly if columns are missing."""
    header = pd.read_csv(path, nrows=0).columns
    missing = [c for c in needed if c not in header]
    if missing:
        raise ValueError(f'{path} is missing columns {missing}. '
                         f'Found: {list(header)}')


def to_wide(df, index_cols, column_col, value_col):
    """
    Reshapes long data (one row per county per variable) into wide data
    (one row per county, one column per variable). Unlike pivot_table,
    this keeps counties whose values are all missing.
    """
    wide = (df.groupby(index_cols + [column_col])[value_col].first()
            .unstack(column_col).reset_index())
    wide.columns.name = None
    return wide


def download_census(raw_path):
    """Saves the Census API response to raw_path."""
    url = CENSUS_URL
    key = os.environ.get('CENSUS_API_KEY')
    if key:
        url += '&key=' + key
    with urllib.request.urlopen(url) as response:
        text = response.read().decode('utf-8')
    with open(raw_path, 'w', encoding='utf-8') as f:
        f.write(text)


def parse_census(rows):
    """
    Converts the Census API response (a list of lists whose first row is
    the header and whose values are all strings) into a DataFrame with a
    5-digit FIPS column and numeric income, with missing codes as NaN.
    """
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df['FIPS'] = df['state'] + df['county']
    df['MEDIAN_HH_INCOME_2023'] = pd.to_numeric(df['S1901_C01_012E'],
                                                errors='coerce')
    df['MEDIAN_HH_INCOME_2023'] = df['MEDIAN_HH_INCOME_2023'].replace(
        CENSUS_MISSING_CODES, np.nan)
    df = df.rename(columns={'state': 'STATE_FIPS',
                            'county': 'COUNTY_FIPS'})
    return df[['FIPS', 'NAME', 'STATE_FIPS', 'COUNTY_FIPS',
               'MEDIAN_HH_INCOME_2023']]


def clean_census():
    raw_path = CENSUS_DIR + 'census_median_income_2023_raw.json'
    if not os.path.exists(raw_path):
        print('Downloading Census data...')
        download_census(raw_path)
    with open(raw_path, encoding='utf-8') as f:
        rows = json.load(f)

    df = parse_census(rows)
    df.to_csv(CORE + 'census_income.csv', index=False,
              na_rep=NA)
    print(f'Census: {df.shape[0]} rows x {df.shape[1]} cols, '
          f'{df["MEDIAN_HH_INCOME_2023"].isna().sum()} missing income')


def clean_food_atlas():
    path = DATA + 'StateAndCountyData.csv'
    cols = ['FIPS', 'State', 'County', 'Variable_Code', 'Value']
    check_columns(path, cols)

    keep = set(pd.read_csv(DATA + 'VariableList_cleaned.csv')
               ['Variable_Code'])

    parts = []
    for chunk in pd.read_csv(path, usecols=cols, dtype={'FIPS': str},
                             chunksize=CHUNK):
        parts.append(chunk[chunk['Variable_Code'].isin(keep)])
    df = pd.concat(parts)

    df['FIPS'] = df['FIPS'].str.zfill(5)
    df['Value'] = pd.to_numeric(df['Value'], errors='coerce')
    df['Value'] = df['Value'].replace(FOOD_MISSING_CODES, np.nan)

    wide = to_wide(df, ['FIPS', 'State', 'County'], 'Variable_Code',
                   'Value')
    wide.to_csv(CORE + 'food_atlas.csv', index=False, na_rep=NA)

    found = set(df['Variable_Code'])
    print(f'Food Atlas: {wide.shape[0]} rows x {wide.shape[1]} cols')
    if keep - found:
        print('  Not found in data:', sorted(keep - found))


def clean_places():
    # Raw file name starts with 'PLACES__'; the cleaned output does not.
    matches = [f for f in os.listdir(DATA)
               if f.startswith('PLACES__') and f.endswith('.csv')]
    path = DATA + matches[0]
    cols = ['StateAbbr', 'LocationName', 'LocationID',
            'MeasureId', 'DataValueTypeID', 'Data_Value']
    check_columns(path, cols)

    parts = []
    for chunk in pd.read_csv(path, usecols=cols,
                             dtype={'LocationID': str}, chunksize=CHUNK):
        mask = (chunk['MeasureId'].isin(PLACES_MEASURES)
                & (chunk['DataValueTypeID'] == PLACES_VALUE_TYPE))
        parts.append(chunk[mask])
    df = pd.concat(parts)

    df = df.rename(columns={'LocationID': 'FIPS'})
    df['FIPS'] = df['FIPS'].str.zfill(5)

    wide = to_wide(df, ['FIPS', 'StateAbbr', 'LocationName'], 'MeasureId',
                   'Data_Value')
    wide.to_csv(CORE + 'places_health.csv', index=False, na_rep=NA)

    print(f'PLACES: {wide.shape[0]} rows x {wide.shape[1]} cols')
    missing = set(PLACES_MEASURES) - set(df['MeasureId'])
    if missing:
        print('  Not found in data:', sorted(missing))


if __name__ == '__main__':
    clean_census()
    clean_food_atlas()
    clean_places()

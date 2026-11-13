"""
Joins the cleaned Census income, CDC PLACES, and USDA Food Atlas data
on the 5-digit county FIPS code and adds a Census region column.

Produces two joined datasets:
    data/joined/census_places.csv       - income + health (RQ1-RQ3)
    data/joined/census_places_food.csv  - income + health + food

Run clean_data.py first to build the cleaned input files.
"""
import pandas as pd

CENSUS_PATH = 'data/core/census_income.csv'
PLACES_PATH = 'data/core/places_health.csv'
FOOD_PATH = 'data/core/food_atlas.csv'

# Census Bureau regions, keyed by 2-digit state FIPS code. Source:
# https://www.cdc.gov/nchs/hus/sources-definitions/geographic-region.htm
REGIONS = {
    'Northeast': ['09', '23', '25', '33', '34', '36', '42', '44', '50'],
    'Midwest': ['17', '18', '19', '20', '26', '27', '29', '31', '38',
                '39', '46', '55'],
    'South': ['01', '05', '10', '11', '12', '13', '21', '22', '24', '28',
              '37', '40', '45', '47', '48', '51', '54'],
    'West': ['02', '04', '06', '08', '15', '16', '30', '32', '35', '41',
             '49', '53', '56'],
}


def load_csv(path):
    """Reads a cleaned CSV, keeping FIPS codes as 5-character strings."""
    return pd.read_csv(path, dtype={'FIPS': str})


def add_region(df):
    """
    Returns a copy of df with a 'region' column based on the first two
    digits (state code) of FIPS. Areas outside the four regions, such as
    Puerto Rico, get NaN.
    """
    state_to_region = {state: region
                       for region, states in REGIONS.items()
                       for state in states}
    result = df.copy()
    result['region'] = result['FIPS'].str[:2].map(state_to_region)
    return result


def unmatched(left, right, left_name, right_name):
    """
    Returns a dict mapping each dataset name to a DataFrame of its rows
    whose FIPS code does not appear in the other dataset.
    """
    return {
        left_name: left[~left['FIPS'].isin(right['FIPS'])],
        right_name: right[~right['FIPS'].isin(left['FIPS'])],
    }


def join_census_places(census, places):
    """
    Inner-joins Census income and PLACES health data on FIPS and adds a
    region column. Keeps one copy of the county name columns.
    """
    places = places.drop(columns=['LocationName'])
    merged = census.merge(places, on='FIPS', how='inner')
    return add_region(merged)


def join_with_food(census_places, food):
    """
    Inner-joins the Census + PLACES data with the Food Atlas data on
    FIPS, dropping the Food Atlas's duplicate state and county names.
    """
    food = food.drop(columns=['State', 'County'])
    return census_places.merge(food, on='FIPS', how='inner')


def report_unmatched(missing):
    """Prints how many rows of each dataset failed to match, with examples."""
    for name, rows in missing.items():
        print(f'  {name}: {len(rows)} rows not matched')
        if len(rows) > 0:
            label = 'NAME' if 'NAME' in rows.columns else rows.columns[1]
            examples = (rows['FIPS'] + ' ' + rows[label].astype(str))
            print('    e.g.', ', '.join(examples.head(5)))


def main():
    census = load_csv(CENSUS_PATH)
    places = load_csv(PLACES_PATH)
    food = load_csv(FOOD_PATH)

    census_places = join_census_places(census, places)
    print(f'Census + PLACES: {census_places.shape[0]} rows x '
          f'{census_places.shape[1]} cols')
    report_unmatched(unmatched(census, places, 'Census', 'PLACES'))

    census_places_food = join_with_food(census_places, food)
    print(f'Census + PLACES + Food Atlas: {census_places_food.shape[0]} '
          f'rows x {census_places_food.shape[1]} cols')
    report_unmatched(unmatched(census_places, food,
                               'Census + PLACES', 'Food Atlas'))

    census_places.to_csv('data/joined/census_places.csv', index=False,
                         na_rep='NA')
    census_places_food.to_csv('data/joined/census_places_food.csv',
                              index=False, na_rep='NA')


if __name__ == '__main__':
    main()

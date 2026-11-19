"""
Tests for the EDA code in clean_data.py, join_data.py, eda.py, and
visualize.py.

Part 1 runs each function on small hand-made inputs whose correct
outputs were worked out by hand. Part 2 runs sanity checks on the real
cleaned and joined files, which must already exist (run clean_data.py
and join_data.py first).

Run with:  python test_eda.py   or   python -m pytest test_eda.py
"""
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go

import clean_data
import eda
import join_data
import visualize


# ---------- Part 1: small hand-made inputs ----------

def test_parse_census():
    """
    Census API rows: header first, all strings, -666666666 for missing.
    """
    rows = [
        ['NAME', 'S1901_C01_012E', 'state', 'county'],
        ['Autauga County, Alabama', '69841', '01', '001'],
        ['Esmeralda County, Nevada', '-666666666', '32', '009'],
        ['Kalawao County, Hawaii', '-999999999', '15', '005'],
    ]
    df = clean_data.parse_census(rows)
    assert list(df['FIPS']) == ['01001', '32009', '15005']
    assert df.loc[0, 'MEDIAN_HH_INCOME_2023'] == 69841
    assert math.isnan(df.loc[1, 'MEDIAN_HH_INCOME_2023'])
    assert math.isnan(df.loc[2, 'MEDIAN_HH_INCOME_2023'])
    assert len(df) == 3  # header row is not treated as data


def test_clean_food_values():
    """Food Atlas: -9999 and -8888 become NaN; FIPS keeps leading zero."""
    df = pd.DataFrame({
        'FIPS': ['1001', '01003', '02010'],
        'Value': ['12.5', '-9999', '-8888'],
    })
    result = clean_data.clean_food_values(df)
    assert list(result['FIPS']) == ['01001', '01003', '02010']
    assert result.loc[0, 'Value'] == 12.5
    assert result['Value'].isna().sum() == 2


def test_to_wide():
    """
    Long to wide: one row per county, one column per variable, and a
    county whose values are all missing is kept (not silently dropped).
    """
    long = pd.DataFrame({
        'FIPS': ['01001', '01001', '01003', '01003', '01005', '01005'],
        'Variable_Code': ['A', 'B', 'A', 'B', 'A', 'B'],
        'Value': [1.0, 2.0, 3.0, np.nan, np.nan, np.nan],
    })
    wide = clean_data.to_wide(long, ['FIPS'], 'Variable_Code', 'Value')
    assert list(wide['FIPS']) == ['01001', '01003', '01005']
    assert list(wide.columns) == ['FIPS', 'A', 'B']
    assert wide.loc[0, 'A'] == 1.0 and wide.loc[0, 'B'] == 2.0
    assert wide.loc[1, 'A'] == 3.0 and math.isnan(wide.loc[1, 'B'])
    assert wide.loc[2, ['A', 'B']].isna().all()


def test_add_region():
    """One state from each region, plus Puerto Rico (no region)."""
    df = pd.DataFrame({'FIPS': ['53033', '36061', '17031', '48201',
                                '72001']})
    result = join_data.add_region(df)
    assert list(result['region'][:4]) == ['West', 'Northeast', 'Midwest',
                                          'South']
    assert pd.isna(result.loc[4, 'region'])


def test_regions_cover_all_states():
    """50 states + DC, each in exactly one region."""
    states = [s for codes in join_data.REGIONS.values() for s in codes]
    assert len(states) == 51
    assert len(set(states)) == 51


def test_joins_and_unmatched():
    """
    Census has 3 counties, PLACES has 2 of them plus one Census lacks.
    The inner join keeps exactly the 2 shared counties.
    """
    census = pd.DataFrame({'FIPS': ['01001', '01003', '21001'],
                           'NAME': ['A', 'B', 'Adair County, Kentucky'],
                           'MEDIAN_HH_INCOME_2023': [50000, 60000, 40000]})
    places = pd.DataFrame({'FIPS': ['01001', '01003', '99999'],
                           'StateAbbr': ['AL', 'AL', 'ZZ'],
                           'LocationName': ['A', 'B', 'Z'],
                           'DIABETES': [12.0, 10.0, 9.0]})
    food = pd.DataFrame({'FIPS': ['01001'], 'State': ['AL'],
                         'County': ['A'], 'PCT_LACCESS_POP19': [20.0]})

    joined = join_data.join_census_places(census, places)
    assert list(joined['FIPS']) == ['01001', '01003']
    assert list(joined['DIABETES']) == [12.0, 10.0]
    assert list(joined['region']) == ['South', 'South']
    assert 'LocationName' not in joined.columns

    missing = join_data.unmatched(census, places, 'Census', 'PLACES')
    assert list(missing['Census']['FIPS']) == ['21001']
    assert list(missing['PLACES']['FIPS']) == ['99999']

    with_food = join_data.join_with_food(joined, food)
    assert list(with_food['FIPS']) == ['01001']
    assert 'State' not in with_food.columns


def test_missing_summary():
    """Column a: 1 of 4 missing (25%); b: 2 of 4 (50%); c: none."""
    df = pd.DataFrame({'a': [1, np.nan, 3, 4],
                       'b': [np.nan, np.nan, 1, 2],
                       'c': [1, 2, 3, 4]})
    summary = eda.missing_summary(df)
    assert list(summary.index) == ['b', 'a', 'c']
    assert summary.loc['a', 'missing'] == 1
    assert summary.loc['a', 'percent_missing'] == 25.0
    assert summary.loc['b', 'percent_missing'] == 50.0
    assert summary.loc['c', 'missing'] == 0


def test_seven_number_summary():
    """
    For 1, 2, 3, 4, 5 (and one NaN, which must be ignored), by hand:
    mean 3, std 1.58, min 1, Q1 2, median 3, Q3 4, max 5.
    """
    df = pd.DataFrame({'x': [1, 2, 3, 4, 5, np.nan]})
    summary = eda.seven_number_summary(df, ['x'])
    row = summary.loc['x']
    assert list(summary.columns) == ['mean', 'std_dev', 'min', 'Q1',
                                     'median', 'Q3', 'max']
    assert row['mean'] == 3
    assert row['std_dev'] == 1.58
    assert (row['min'], row['Q1'], row['median']) == (1, 2, 3)
    assert (row['Q3'], row['max']) == (4, 5)


def test_category_counts():
    """Counts include missing values as their own category."""
    df = pd.DataFrame({'region': ['South', 'South', 'West', None]})
    counts = eda.category_counts(df, 'region')
    as_dict = dict(zip(counts['region'].fillna('NaN'), counts['count']))
    assert as_dict == {'South': 2, 'West': 1, 'NaN': 1}


def test_add_trendline():
    """Points exactly on y = 2x + 1 give a line with that slope."""
    fig = go.Figure()
    x = pd.Series([0.0, 1.0, 2.0, 3.0])
    visualize.add_trendline(fig, x, 2 * x + 1, 'trend', 'red')
    line = fig.data[0]
    assert list(line.x) == [0.0, 3.0]
    assert np.allclose(line.y, [1.0, 7.0])


# ---------- Part 2: sanity checks on the real data ----------

def load(path):
    """Reads a cleaned or joined CSV with FIPS as strings."""
    return pd.read_csv(path, dtype={'FIPS': str})


def test_real_fips_codes():
    """Every dataset has unique, 5-digit FIPS codes."""
    for path in ['data/core/census_income.csv',
                 'data/core/places_health.csv',
                 'data/core/food_atlas.csv',
                 'data/joined/census_places.csv',
                 'data/joined/census_places_food.csv']:
        df = load(path)
        assert df['FIPS'].str.fullmatch(r'\d{5}').all(), path
        assert df['FIPS'].is_unique, path


def test_real_values_in_range():
    """
    No missing-value codes survived cleaning: percentages are between
    0 and 100, and income is positive and realistic.
    """
    df = load('data/joined/census_places_food.csv')
    percents = ['DIABETES', 'OBESITY', 'BPHIGH', 'CHD', 'CSMOKING', 'LPA',
                'ACCESS2', 'CHECKUP', 'GHLTH', 'MHLTH', 'DEPRESSION',
                'PCT_LACCESS_POP19', 'POVRATE21', 'PCT_SNAP22']
    for column in percents:
        values = df[column].dropna()
        assert values.between(0, 100).all(), column
    income = df['MEDIAN_HH_INCOME_2023'].dropna()
    assert income.between(10000, 300000).all()
    numbers = df.select_dtypes('number')
    assert (numbers < 0).sum().sum() == 0  # no -9999/-8888 codes left


def test_real_join_counts():
    """
    The joins lose exactly the counties we expect: all of Kentucky (21),
    Pennsylvania (42), and Puerto Rico (72), and nothing else. Loving
    County, TX, which has no PLACES estimates, is kept with NaN values.
    """
    census = load('data/core/census_income.csv')
    places = load('data/core/places_health.csv')
    joined = load('data/joined/census_places.csv')
    joined_food = load('data/joined/census_places_food.csv')

    assert len(joined) == len(places) == 2957
    assert len(joined_food) == len(joined)
    lost = census[~census['FIPS'].isin(joined['FIPS'])]
    lost_states = lost['FIPS'].str[:2].value_counts().to_dict()
    assert lost_states == {'21': 120, '72': 78, '42': 67}
    assert joined['region'].notna().all()
    loving = joined[joined['FIPS'] == '48301']
    assert len(loving) == 1 and loving['DIABETES'].isna().all()


def main():
    tests = [value for name, value in globals().items()
             if name.startswith('test_') and callable(value)]
    for test in tests:
        test()
        print('passed', test.__name__)
    print(f'All {len(tests)} tests passed.')


if __name__ == '__main__':
    main()

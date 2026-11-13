"""
Creates the EDA visualizations for the two joined datasets with plotly
and saves them as PNG files in figures/.

Census + PLACES (RQ1-RQ3):
    1. diabetes_vs_income.png    - scatter with least-squares trend line
    2. obesity_vs_income.png     - scatter with least-squares trend line
    3. diabetes_by_region.png    - box plot per Census region
    4. diabetes_map.png          - county map of diabetes prevalence
Census + PLACES + Food Atlas:
    5. food_access_vs_diabetes.png - scatter colored by metro status
    6. income_vs_food_access.png   - scatter colored by metro status

Run clean_data.py and join_data.py first.
"""
import json
import os
import urllib.request

import kaleido
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

FIGURES = 'figures/'
CENSUS_PLACES = 'data/joined/census_places.csv'
CENSUS_PLACES_FOOD = 'data/joined/census_places_food.csv'
COUNTY_SHAPES = 'data/counties.geojson'
COUNTY_SHAPES_URL = ('https://raw.githubusercontent.com/plotly/datasets/'
                     'master/geojson-counties-fips.json')

INCOME = 'MEDIAN_HH_INCOME_2023'
REGION_ORDER = ['Northeast', 'Midwest', 'South', 'West']
METRO_LABELS = {1: 'Metro', 0: 'Nonmetro'}
METRO_COLORS = {'Metro': '#1f4e9c', 'Nonmetro': '#e07b00'}
LABELS = {
    INCOME: 'Median household income ($)',
    'DIABETES': 'Diagnosed diabetes (% of adults)',
    'OBESITY': 'Obesity (% of adults)',
    'PCT_LACCESS_POP19': 'Population with low access to a store (%)',
    'region': 'Census region',
    'METRO23': 'County type',
}
WIDTH = 900
HEIGHT = 550


def load_joined(path):
    """
    Reads a joined CSV with FIPS kept as strings and drops rows missing
    income or diabetes, which no plot can use.
    """
    df = pd.read_csv(path, dtype={'FIPS': str})
    df = df.dropna(subset=[INCOME, 'DIABETES'])
    if 'METRO23' in df.columns:
        df['METRO23'] = df['METRO23'].map(METRO_LABELS)
    return df


def load_county_shapes():
    """Returns the county boundary GeoJSON, downloading it if needed."""
    if not os.path.exists(COUNTY_SHAPES):
        urllib.request.urlretrieve(COUNTY_SHAPES_URL, COUNTY_SHAPES)
    with open(COUNTY_SHAPES, encoding='utf-8') as f:
        return json.load(f)


def save(fig, name):
    """
    Saves a plotly figure as a PNG in the figures folder. kaleido's
    headless browser occasionally fails to start a render, so a failed
    save is retried up to two more times.
    """
    for attempt in range(3):
        try:
            fig.write_image(FIGURES + name, width=WIDTH, height=HEIGHT,
                            scale=2)
            print('Saved', FIGURES + name)
            return
        except Exception:
            if attempt == 2:
                raise


def add_trendline(fig, x, y, name, color):
    """
    Adds a least-squares line of y on x to fig. Uses numpy rather than
    plotly's statsmodels trendline so it does not depend on scipy.
    """
    slope, intercept = np.polyfit(x, y, 1)
    xs = np.array([x.min(), x.max()])
    fig.add_trace(go.Scatter(x=xs, y=slope * xs + intercept, mode='lines',
                             name=name, line={'color': color,
                                              'width': 3}))


def plot_health_vs_income(df, measure, name):
    """Scatter of a health measure against income with a trend line."""
    fig = px.scatter(df, x=INCOME, y=measure, opacity=0.35,
                     render_mode='svg', labels=LABELS,
                     title=f'{LABELS[measure]} vs. median household '
                           'income by county')
    fig.data[0].name = 'County'
    fig.data[0].showlegend = True
    add_trendline(fig, df[INCOME], df[measure], 'Linear trend', 'red')
    save(fig, name)


def plot_diabetes_by_region(df):
    """Box plot of county diabetes prevalence for each Census region."""
    counts = df['region'].value_counts()
    names = {region: f'{region} (n = {counts[region]})'
             for region in REGION_ORDER}
    df = df.assign(region=df['region'].map(names))
    fig = px.box(df, x='region', y='DIABETES', color='region',
                 category_orders={'region': list(names.values())},
                 labels=LABELS,
                 title='Diagnosed diabetes prevalence by Census region')
    save(fig, 'diabetes_by_region.png')


def plot_diabetes_map(df, counties):
    """County map of diagnosed diabetes prevalence."""
    fig = px.choropleth(df, geojson=counties, locations='FIPS',
                        color='DIABETES', scope='usa',
                        color_continuous_scale='Reds', labels=LABELS,
                        title='Diagnosed diabetes prevalence by county '
                              '(gray = no data)')
    fig.update_traces(marker_line_width=0)
    fig.update_geos(bgcolor='white', landcolor='lightgray',
                    showland=True)
    save(fig, 'diabetes_map.png')


def plot_food_access_vs_diabetes(df):
    """Scatter of low food access against diabetes, colored by metro."""
    df = df.dropna(subset=['PCT_LACCESS_POP19', 'METRO23'])
    colors = METRO_COLORS
    fig = px.scatter(df, x='PCT_LACCESS_POP19', y='DIABETES',
                     color='METRO23', color_discrete_map=colors,
                     opacity=0.35, render_mode='svg', labels=LABELS,
                     title='Diagnosed diabetes vs. low food access, '
                           'metro and nonmetro counties')
    for group, color in colors.items():
        rows = df[df['METRO23'] == group]
        add_trendline(fig, rows['PCT_LACCESS_POP19'], rows['DIABETES'],
                      f'{group} trend', color)
    save(fig, 'food_access_vs_diabetes.png')


def plot_income_vs_food_access(df):
    """Scatter of income against low food access, colored by metro."""
    df = df.dropna(subset=['PCT_LACCESS_POP19', 'METRO23'])
    fig = px.scatter(df, x=INCOME, y='PCT_LACCESS_POP19', color='METRO23',
                     color_discrete_map=METRO_COLORS, opacity=0.35,
                     render_mode='svg', labels=LABELS,
                     title='Low food access vs. median household income, '
                           'metro and nonmetro counties')
    save(fig, 'income_vs_food_access.png')


def main():
    os.makedirs(FIGURES, exist_ok=True)
    # One shared headless browser for all PNG exports; starting a new
    # one for every figure fails intermittently on Windows.
    kaleido.start_sync_server(silence_warnings=True)

    census_places = load_joined(CENSUS_PLACES)
    plot_health_vs_income(census_places, 'DIABETES',
                          'diabetes_vs_income.png')
    plot_health_vs_income(census_places.dropna(subset=['OBESITY']),
                          'OBESITY', 'obesity_vs_income.png')
    plot_diabetes_by_region(census_places)
    plot_diabetes_map(census_places, load_county_shapes())

    census_places_food = load_joined(CENSUS_PLACES_FOOD)
    plot_food_access_vs_diabetes(census_places_food)
    plot_income_vs_food_access(census_places_food)
    kaleido.stop_sync_server(silence_warnings=True)


if __name__ == '__main__':
    main()

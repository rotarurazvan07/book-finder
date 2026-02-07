import argparse
import sys

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, dash_table, State, ctx
import pandas as pd
from datetime import datetime
import numpy as np

# Assuming DatabaseManager is in your project
from book_framework.DatabaseManager import DatabaseManager
from book_framework.SettingsManager import settings_manager

class BookDashboard:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
            suppress_callback_exceptions=True
        )
        self.app.title = "Live Book Monitor"
        self._setup_layout()
        self._setup_callbacks()

    def _setup_layout(self):
        self.app.layout = dbc.Container([
            # --- Header ---
            dbc.Row([
                dbc.Col([
                    html.Div([
                        dbc.Row([
                            dbc.Col([
                                html.H2([html.I(className="fas fa-book-reader me-3"), "Live Book Monitor"],
                                        className="text-white fw-bold mb-0"),
                                html.P("Smart Antiquarian Scraper & Analyzer", className="text-white-50 mb-0")
                            ], width=8),
                            dbc.Col([
                                dbc.Button([
                                    html.I(className="fas fa-redo-alt me-2"), "Refresh Data"
                                ], id="refresh-btn", color="light", outline=True, className="float-end mt-2")
                            ], width=4)
                        ], align="center")
                    ], className="p-3 rounded-3 shadow-sm mb-3 mt-2",
                       style={"background": "linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)"})
                ])
            ]),

            # --- Unified Filter Row (One row only) ---
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        # 1. Search
                        dbc.Col([
                            html.Label("🔍 Search", className="fw-bold small"),
                            dbc.Input(id="search-filter", placeholder="Title/Author...", type="text", size="sm")
                        ], width=12, lg=2),

                        # 2. Category
                        dbc.Col([
                            html.Label("📂 Category", className="fw-bold small"),
                            dcc.Dropdown(id="category-filter", multi=True, placeholder="All")
                        ], width=12, lg=2),

                        # 3. Store
                        dbc.Col([
                            html.Label("🏢 Store", className="fw-bold small"),
                            dcc.Dropdown(id="store-filter", multi=True, placeholder="All")
                        ], width=12, lg=2),

                        # 4. Rating Input
                        dbc.Col([
                            html.Label("⭐ Min", className="fw-bold small"),
                            dbc.Input(id="rating-input", type="number", min=0, max=5, step=0.1, value=0, size="sm")
                        ], width=6, lg=1),

                        dbc.Col([
                            html.Label("💰 Price Range", className="fw-bold small"),
                            dcc.RangeSlider(
                                id="price-filter",
                                min=0,
                                max=1000,
                                value=[2, 100],  # This is the secret for 2 heads
                                tooltip={"always_visible": True, "placement": "bottom"},
                                className="mt-2"
                            )
                        ], width=12, lg=4),
                    ], className="g-2 align-items-end"),
                    html.Div(id="last-updated-text", className="text-muted small mt-2 text-end")
                ], className="py-2")
            ], className="shadow-sm mb-3 border-0"),

            # --- Table Section ---
            dbc.Row([
                dbc.Col([
                    dcc.Loading(id="loading-table", children=html.Div(id="table-container"))
                ])
            ])
        ], fluid=True, className="bg-light min-vh-100 px-3")

    def _setup_callbacks(self):
        @self.app.callback(
            [Output("table-container", "children"),
             Output("category-filter", "options"),
             Output("store-filter", "options"),
             Output("last-updated-text", "children"),
             Output("price-filter", "min"),
             Output("price-filter", "max"),
             Output("price-filter", "marks")],
            [Input("refresh-btn", "n_clicks"),
             Input("search-filter", "value"),
             Input("category-filter", "value"),
             Input("store-filter", "value"),
             Input("price-filter", "value"),
             Input("rating-input", "value")]
        )
        def update_view(n_clicks, search, selected_cats, selected_stores, price_range, min_rating):
            df = self.db_manager.fetch_all_as_dataframe()
            timestamp = f"Last updated: {datetime.now().strftime('%H:%M:%S')}"

            if df.empty:
                return dbc.Alert("No data found."), [], [], timestamp, 0, 1000, {}

            f_df = df.copy()

            # --- Filtering ---
            if search:
                f_df = f_df[f_df['title'].str.contains(search, case=False, na=False) |
                           f_df['author'].str.contains(search, case=False, na=False)]

            if selected_cats:
                f_df = f_df[f_df['category'].isin(selected_cats)]

            if selected_stores:
                f_df = f_df[f_df['store'].isin(selected_stores)]

            if min_rating is not None and min_rating > 0:
                f_df = f_df[f_df['rating'] >= min_rating]


            p_min_db = float(f_df['price'].min()) if not f_df.empty else 0
            p_max_db = float(f_df['price'].max()) if not f_df.empty else 1000
            p_marks = {}
            if p_min_db <= 2 <= p_max_db:
                p_marks[2] = "2"
            if p_min_db <= 100 <= p_max_db:
                p_marks[100] = "100"
            if isinstance(price_range, list) and len(price_range) == 2:
                f_df = f_df[(f_df['price'] >= price_range[0]) & (f_df['price'] <= price_range[1])]

            # 4. Data Preparation
            f_df['price'] = f_df['price'].round(2)
            f_df['rating'] = f_df['rating'].apply(lambda x: round(x, 2) if pd.notnull(x) else x)

            f_df['store_md'] = f_df['url'].apply(lambda x: f"[Buy]({x})")
            f_df['gr_md'] = f_df['goodreads_url'].apply(lambda x: f"[GR]({x})" if x and str(x) != 'None' else "N/A")

            cat_opts = [{"label": str(c), "value": c} for c in sorted(df['category'].dropna().unique())]
            store_opts = [{"label": str(s), "value": s} for s in sorted(df['store'].dropna().unique())]

            # 5. Table Rendering
            table = dash_table.DataTable(
                data=f_df.to_dict('records'),
                columns=[
                    {"name": "Title", "id": "title"},
                    {"name": "Author", "id": "author"},
                    {"name": "⭐", "id": "rating", "type": "numeric"},
                    {"name": "Price", "id": "price", "type": "numeric", "format": {"specifier": ".2f"}},
                    {"name": "Store", "id": "store"},
                    {"name": "Link", "id": "store_md", "presentation": "markdown"},
                    {"name": "Info", "id": "gr_md", "presentation": "markdown"}
                ],
                sort_action="native",
                page_size=20,
                style_table={'overflowX': 'auto', 'minWidth': '100%'},
                style_cell={
                    'textAlign': 'left', 'padding': '10px',
                    'overflow': 'hidden', 'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap'
                },
                style_cell_conditional=[
                    {'if': {'column_id': 'title'}, 'width': '35%'},
                    {'if': {'column_id': 'author'}, 'width': '20%'},
                    {'if': {'column_id': 'rating'}, 'width': '8%', 'textAlign': 'center'},
                    {'if': {'column_id': 'price'}, 'width': '8%', 'textAlign': 'center'},
                    {'if': {'column_id': 'store'}, 'width': '10%'},
                    {'if': {'column_id': 'store_md'}, 'width': '9%', 'textAlign': 'center'},
                    {'if': {'column_id': 'gr_md'}, 'width': '10%', 'textAlign': 'center'},
                ],
                style_header={'backgroundColor': '#2c3e50', 'color': 'white', 'fontWeight': 'bold'},
                style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#f8f9fa'}]
            )

            # (Remember to return the 9 outputs)
            return table, cat_opts, store_opts, timestamp, p_min_db, p_max_db, p_marks

    def run(self, debug=True, port=8050):
        print(f"Starting dashboard on http://0.0.0.0:{port}")
        self.app.run(debug=debug, host='0.0.0.0', port=port)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Book Finder Scraper")
    parser.add_argument("db_path", help="Path to the SQLite database file (e.g., books.db)")
    args = parser.parse_args()

    db_manager = DatabaseManager(args.db_path)

    dashboard = BookDashboard(db_manager)
    dashboard.run(debug=False, port=8051)
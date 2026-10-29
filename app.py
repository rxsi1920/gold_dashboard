"""Gold stock-transfer monitor - desktop build.

Run:  python ingest.py --synthetic   (once, or --all for live data)
      streamlit run app.py

Design contract (reasoning in the companion notebook):
  - solid = reported, dashed = estimated; one colour per country everywhere
  - the same event rules on every time axis; labels only on the dominant charts
  - one bordered region (the KPI strip); whitespace does all other grouping
  - one dominant chart per tab: P1 carries Declared, P4 carries Inferred
"""
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

import streamlit as st

import design as dz

DATA = Path(__file__).parent / "data"

st.set_page_config(page_title="Gold stock-transfer monitor",
                   layout="wide", initial_sidebar_state="collapsed")


st.set_option("client.toolbarMode", "minimal")

# ---------------------------------------------------------------- chrome/css --
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400;1,6..72,500&family=Archivo:wght@400;500;600&display=swap');

@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,200..900;1,8..60,200..900&display=swap');

div[data-baseweb="tag"], 
span[data-baseweb="tag"],
div[role="button"] {border-radius: 0px !important;}

[data-baseweb="select"] * {border-radius: 0px !important;}

button {border-radius: 0px !important;}

html, body, [class*="css"], .stMarkdown, p, li {font-family: 'Archivo', system-ui, sans-serif;
  font-variant-numeric: tabular-nums;}

grammar {font-size: 8px;}

header [data-testid="stHeader"] { display: none; }

.stMainBlockContainer, .block-container {max-width: 100% !important;padding-top: 0rem !important;
    margin-top: -1.1rem !important;}

.stApp { background: #fbfbf8; color: #1c1c18; }
.block-container { max-width: 100%; padding-left: 1.5rem; padding-right: 1.5rem; padding-top: 0rem; padding-bottom: 3rem; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }

h1 { font-weight: 100; letter-spacing: -.01em;
     font-size: 2rem; margin-bottom: 0; }
.stSubHeader, h2 { font-weight: 500;
     font-size: 1.35rem; margin-bottom: 0; }
h3 { font-weight: 500;
     font-size: 1.2rem; margin-bottom: 0; }
.stCaption, [data-testid="stCaptionContainer"] { color: #8c8c84; }

/* tabs: underline grammar, gold for the active page */
.stTabs [data-baseweb="tab-list"] { gap: 30px; border-bottom: 1px solid #ecece5; }
.stTabs [data-baseweb="tab"] { font-size: 15px; font-weight: 500; color: #8c8c84;
  padding: 6px 0 10px; background: none; }
.stTabs [aria-selected="true"] { color: #1c1c18; }
.stTabs [data-baseweb="tab-highlight"] { background-color: #a3780a; height: 2px; }
.stTabs [data-baseweb="tab-border"] { background-color: transparent; }

/* KPI strip: the only bordered region on the page */
.kpis { border: 1.5px solid #1c1c18; border-radius: 3px;
  display: grid; grid-template-columns: repeat(6, 1fr); gap: 0 26px;
  padding: 14px 18px 10px; margin: 6px 0 4px; margin-top: -1.1rem !important; margin-bottom: -1rem !important;}
.kpi .l { font-size: 11px; color: #8c8c84; line-height: 1.25; }
.kpi .v { font-size: 20px; font-weight: 600; margin-top: 1px; }
.kpi .v small { font-size: 11.5px; font-weight: 500; color: #8c8c84; margin-left: 4px; }
.kpi svg { display: block; margin-top: 4px; }

.grammar { color: #8c8c84; margin: 2px 0 10px; }
.grammar b { color: #1c1c18; font-weight: 500; }
.grammar p { font-size: 4px;}
.masthead { display: flex; justify-content: space-between; align-items: baseline; }
.masthead .d { color: #8c8c84; font-size: 13px; text-align: right;}
.masthead h1 { font-family: "Source Serif 4", serif !important; font-weight: 700; letter-spacing: -.01em;
    font-size: 1.85rem; margin-bottom: 0; }

[data-testid="stHeading"] h2,
[data-testid="stHeading"] h2 * { font-family: "Source Serif 4", serif !important; font-style: normal;
  font-weight: 500; margin-bottom: 0; font-size: 1.4rem;}
[data-testid="stHeading"] h3,
[data-testid="stHeading"] h3 * { font-family: "Source Serif 4", serif !important; font-style: italic;
  font-weight: 500; margin-bottom: 0; font-size: 1.3rem;}
[data-testid="stVerticalBlock"] {gap: 0.6rem !important;}
[data-testid="stCaptionContainer"] {margin-top: -0.6rem !important; margin-bottom: 0rem !important;}
h1, h2, h3 {margin-top: 0rem !important; margin-bottom: 0rem !important;}

.legend-text {padding-bottom: 18px;}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------- plotly theme --
pio.templates["ledger"] = go.layout.Template(layout=dict(
    paper_bgcolor=dz.PAPER, plot_bgcolor=dz.PAPER,
    font=dict(family="Archivo, system-ui, sans-serif", color=dz.INK, size=13),
    margin=dict(l=10, r=64, t=34, b=10), showlegend=False,
    xaxis=dict(showgrid=False, ticks="outside", tickcolor=dz.GHOST,
               linecolor=dz.GHOST),
    yaxis=dict(gridcolor="#efefe8", zeroline=False, side="right",
               tickformat=","),
    hoverlabel=dict(bgcolor=dz.PAPER, bordercolor=dz.GHOST,
                    font=dict(family="Archivo, system-ui, sans-serif",
                              color=dz.INK, size=12)),
))
pio.templates.default = "ledger"
 
# ------------------------------------------------------------------ loading --
@st.cache_data(ttl=3600)
def load(name: str, dates=("date",)) -> pd.DataFrame:
    return pd.read_csv(DATA / f"{name}.csv", parse_dates=list(dates))
 
try:
    price = load("price")
    etf = load("etf")
    declared = load("declared")
    gap = load("gap", dates=("quarter_end",))
    swiss = load("swiss")
except FileNotFoundError:
    st.error("No data found. Run `python ingest.py --synthetic` first.")
    st.stop()
 
asof = {"price": price.date.max(), "etf": etf.date.max(),
        "declared": declared.date.max(), "gap": gap.quarter_end.max(),
        "swiss": swiss.date.max()}
fmt = lambda t: pd.Timestamp(t).strftime("%b %y")
 
# --------------------------------------------------------------- helpers -----
def events(fig, label: bool):
    for i, (d, t) in enumerate(dz.EVENTS):
        try:
            fig.add_shape(type="line", x0=d, x1=d, y0=0, y1=1, xref="x",
                        yref="paper", line=dict(color=dz.GHOST, width=1.5))
            if label:
                fig.add_annotation(x=d, y=1.02 + 0.04 * (i % 2), yref="paper",
                                text=t, showarrow=False,
                                font=dict(size=11, color=dz.FAINT))
        except Exception:
            fig.add_vline(x=d, line_color=dz.GHOST, line_width=1)
            if label:
                fig.add_annotation(x=d, y=1.03 + 0.075 * (i % 2), yref="paper",
                                text=t, showarrow=False,
                                font=dict(size=11, color=dz.FAINT))

 
def endlabel(fig, x, y, text, row=None, color=dz.FAINT):
    try:
        fig.add_annotation(x=1, y=y, xref="paper",
                        yref="y" if row == 1 else f"y{row}", text=text,
                        showarrow=False, xanchor="left", xshift=56,
                        font=dict(size=12, color=color))
    except Exception:
        fig.add_annotation(x=x, y=y, text=text, showarrow=False, xanchor="left",
                        xshift=8, font=dict(size=12, color=color))
 
def paneltitle(fig, row, title, sub):
    dom = fig.layout["yaxis" if row == 1 else f"yaxis{row}"].domain
    fig.add_annotation(x=0, y=dom[1], xref="paper", yref="paper",
                       xanchor="left", yanchor="top", xshift=-215, yshift=-2,
                       text=f"<b style='font-weight: 100;'>{title}</b>", showarrow=False,
                       font=dict(family="'Source Serif 4', serif", size=19,
                                 color=dz.INK))
    fig.add_annotation(x=0, y=dom[1], xref="paper", yref="paper",
                       xanchor="left", yanchor="top", xshift=-215, yshift=-30,
                       text=sub, showarrow=False, align="left",
                       font=dict(size=11, color=dz.FAINT))
 
def chart(fig, h):
    fig.update_layout(height=h)
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False})
 
def spark(vals, color, w=76, h=20):
    lo, hi = min(vals), max(vals) + 1e-9
    pts = " ".join(f"{2 + (w-4)*i/(len(vals)-1):.1f},"
                   f"{h-2 - (h-4)*(v-lo)/(hi-lo):.1f}" for i, v in enumerate(vals))
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="1.6" stroke-linejoin="round"/></svg>')
 
# ------------------------------------------------------------- derived nums --
t12 = (declared[declared.date > asof["declared"] - pd.DateOffset(months=12)]
       .groupby("country").net_purchases_t.sum().sort_values(ascending=False))
top_buy, top_sell = t12.index[0], t12.index[-1]
east_m = (swiss[swiss.destination.isin(["China + HK", "India", "Turkey"])]
          .groupby("date").tonnes.sum())
all_last = swiss[swiss.date == asof["swiss"]].tonnes.sum()
gap_res = (gap.wgc_estimate_t - gap.imf_reported_t)
p_now, p_prev = price.price_usd_oz.iloc[-1], price.price_usd_oz.iloc[-2]
e_now, e_prev = etf.tonnes.iloc[-1], etf.tonnes.iloc[-2]
china12 = declared[declared.country == top_buy].net_purchases_t.tail(12)
russia12 = declared[declared.country == top_sell].net_purchases_t.tail(12)
 
# ----------------------------------------------------------------- masthead --
st.markdown(f"""
<div class="masthead"><h1>Gold stock-transfer monitor</h1>
<div class="d"><b>Sample data</b><br>{pd.Timestamp(asof['price']).strftime('%d %B %Y')}</div></div>
""", unsafe_allow_html=True)
st.caption("Who holds the stock, and which way it is moving?")
 
KPIS = [
    ("price, $/oz", f"{p_now:,.0f}", f"{p_now/p_prev-1:+.1%} m/m",
     spark(price.price_usd_oz.tail(12).tolist(), dz.GOLD)),
    ("GLD + IAU", f"{e_now:,.0f} t", f"{e_now-e_prev:+.0f} t m/m",
     spark(etf.tonnes.tail(12).tolist(), dz.hue("West"))),
    ("gap, latest qtr", f"+{gap_res.iloc[-1]:,.0f} t", "unreported",
     spark(gap_res.tail(8).tolist(), dz.GOLD)),
    ("top buyer, 12m", top_buy, f"+{t12.iloc[0]:,.0f} t",
     spark(china12.tolist(), dz.hue(top_buy))),
    ("top seller, 12m", top_sell, f"{t12.iloc[-1]:,.0f} t",
     spark(russia12.tolist(), dz.hue(top_sell))),
    (f"Swiss → east, {fmt(asof['swiss'])}", f"{east_m.iloc[-1]:,.0f} t",
     f"of {all_last:,.0f} t out",
     spark(east_m.tail(12).tolist(), dz.hue("China"))),
]
tiles = "".join(f'<div class="kpi"><div class="l">{l}</div>'
                f'<div class="v">{v}<small>{s}</small></div>{sp}</div>'
                for l, v, s, sp in KPIS)
st.markdown(f'<div class="kpis">{tiles}</div>', unsafe_allow_html=True)
 
# ================================================================ BIG CHART ===
show_repl = st.session_state.get("show_repl", False)
f = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.065,
                  row_heights=[.25, .17, .17, .18, .23])
order = declared.groupby("country").net_purchases_t.sum().sort_values(
    ascending=False).index

f.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    legend=dict(bgcolor='rgba(0,0,0,0)'))
 
for c in order:
    d = declared[declared.country == c]
    f.add_trace(go.Bar(x=d.date, y=d.net_purchases_t, name=c,
        marker_color=dz.hue(c), width=24 * 86400000,
        hovertemplate=f"{c}: %{{y:+.0f}} t<extra></extra>"), row=1, col=1)
net = declared.groupby("date").net_purchases_t.sum()
f.add_trace(go.Scatter(x=net.index, y=net.values, name="net purchases",
    mode="lines", line=dict(color=dz.INK, width=1.6, shape="spline")),
    row=1, col=1)
 
f.add_trace(go.Scatter(x=gap.quarter_end, y=gap.imf_reported_t,
    mode="lines", line=dict(width=0), hoverinfo="skip"), row=2, col=1)
f.add_trace(go.Scatter(x=gap.quarter_end, y=gap.wgc_estimate_t,
    name="WGC estimate", mode="lines",
    line=dict(color=dz.INK, width=1.6, dash=dz.DASH),
    fill="tonexty", fillcolor="rgba(163,120,10,.16)"), row=2, col=1)
f.add_trace(go.Bar(x=gap.quarter_end, y=gap.imf_reported_t,
    name="reported to IMF", marker_color=dz.INK, opacity=.85,
    width=62 * 86400000), row=2, col=1)
 
f.add_trace(go.Scatter(x=etf.date, y=etf.tonnes, name="GLD + IAU",
    mode="lines", line=dict(color=dz.hue("West"), width=2.2)), row=3, col=1)
 
f.add_trace(go.Scatter(x=price.date, y=price.yield_implied_usd_oz,
    name="yield-implied", mode="lines",
    line=dict(color=dz.INK, width=1.3, dash=dz.DASH)), row=4, col=1)
f.add_trace(go.Scatter(x=price.date, y=price.price_usd_oz, name="price",
    mode="lines", line=dict(color=dz.GOLD, width=2.6),
    fill="tonexty", fillcolor="rgba(163,120,10,.13)"), row=4, col=1)
 
for dest in ["other", "UAE + Gulf", "UK + US", "Turkey", "India",
             "China + HK"]:
    d = swiss[swiss.destination == dest]
    f.add_trace(go.Scatter(x=d.date, y=d.tonnes, name=dest,
        stackgroup="flow", mode="none", fillcolor=dz.hue(dest),
        hovertemplate=f"{dest}: %{{y:.0f}} t<extra></extra>"), row=5, col=1)
 
if show_repl:
    f.add_hline(y=dz.MINE_TOTAL_TPM,
        line=dict(color=dz.INK, width=1.2, dash="dash"),
        annotation_text="all mine supply ≈ 300 t/mo",
        annotation_position="top left", row=5, col=1)
    f.add_hline(y=dz.MINE_WESTERN_TPM,
        line=dict(color=dz.INK, width=1.2, dash="dot"),
        annotation_text="enters Western circuit ≈ 200 t/mo",
        annotation_position="bottom left", row=5, col=1)
 
f.update_layout(barmode="relative", bargap=0.1, hovermode="x unified",
                margin=dict(l=230, r=150, t=80, b=30))
f.update_xaxes(tick0=f"{price.date.min().year}-01-01", dtick="M12",
               tickformat="%Y", row=5, col=1, tickfont=dict(color="#2c2e35"), title_font=dict(color="#2c2e35"))
f.update_xaxes(range=[declared.date.min() - pd.Timedelta(days=15),
                      asof["declared"] + pd.Timedelta(days=15)], tickfont=dict(color="#2c2e35"), title_font=dict(color="#2c2e35"))
f.update_yaxes(tickvals=[0, 50], range=[-14, 62], zeroline=True,
               zerolinecolor=dz.GHOST, row=1, col=1, tickfont=dict(color="#2c2e35"), title_font=dict(color="#2c2e35"))
f.update_yaxes(tickvals=[0, 200, 400], range=[0, 430], row=2, col=1, tickfont=dict(color="#2c2e35"), title_font=dict(color="#2c2e35"))
f.update_yaxes(tickvals=[1200, 1400, 1600], range=[1150, 1680], row=3, col=1, tickfont=dict(color="#2c2e35"), title_font=dict(color="#2c2e35"))
f.update_yaxes(tickvals=[2000, 4000],
               range=[price.yield_implied_usd_oz.min() * 0.92,
                      price.price_usd_oz.max() * 1.03], row=4, col=1, tickfont=dict(color="#2c2e35"), title_font=dict(color="#2c2e35"))
f.update_yaxes(tickvals=[0, 200], range=[0, 330 if show_repl else 230],
               row=5, col=1, tickfont=dict(color="#2c2e35"), title_font=dict(color="#2c2e35"))


 
events(f, label=True)
 
paneltitle(f, 1, "Official purchases",
           f"{declared.country.nunique()} countries · tonnes / month<br>"
           f"to {fmt(asof['declared'])}<br>Black line: net purchases")
paneltitle(f, 2, "Estimated buying",
           f"Reported / WGC estimate<br>tonnes / quarter · "
           f"{gap.quarter_end.iloc[-1].to_period('Q')}")
paneltitle(f, 3, "ETF holdings",
           f"GLD + IAU · tonnes<br>to {fmt(asof['etf'])}")
paneltitle(f, 4, "Gold price",
           f"Actual / yield-implied · $/oz<br>to {fmt(asof['price'])}")
paneltitle(f, 5, "Swiss exports",
           f"By destination · tonnes / month<br>to {fmt(asof['swiss'])}")
 
endlabel(f, gap.quarter_end.iloc[-1], gap.wgc_estimate_t.iloc[-1],
         "WGC estimate", 2)
endlabel(f, gap.quarter_end.iloc[-1], gap.imf_reported_t.iloc[-1],
         "Reported", 2)
endlabel(f, etf.date.iloc[-1], e_now, f"{e_now:,.0f} t", 3)
endlabel(f, price.date.iloc[-1], p_now, f"{p_now:,.0f} $/oz", 4, dz.GOLD)
endlabel(f, price.date.iloc[-1], price.yield_implied_usd_oz.iloc[-1],
         "Yield-implied", 4)
 
chart(f, 780)
 
# ------------------------------------------------------------- legend row ----
sep = '<span style="color:#8c8c84;margin:0 6px">·</span>'
dots = "".join(
    f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;'
    f'background:{dz.hue(k)};margin:0 5px 0 10px"></span>{n}'
    for k, n in [("China", "China / HK"), ("Russia", "Russia"),
                 ("India", "India"), ("Turkey", "Turkey"),
                 ("UK + US", "UK / US")])

@st.dialog("Bank details", width="large")
def show_bank_detail(declared, asof, t12, dz, pd, px, chart):
  d12 = declared[declared.date > asof["declared"] - pd.DateOffset(months=12)].copy()
  order12 = t12.index.tolist()
  fig = px.bar(d12, x="date", y="net_purchases_t", facet_col="country", facet_col_wrap=5,
    category_orders={"country": order12}, color="country", color_discrete_map={
    c: dz.hue(c) for c in order12}, facet_row_spacing=0.10, facet_col_spacing=0.03)
  fig.update_yaxes(matches=None, title=None, side="left")
  fig.update_xaxes(title=None, showticklabels=False)
  fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1], font=dict(size=12)))
  chart(fig, 520)


@st.dialog("Sources & notes")
def show_sources_notes():
  st.caption(
      "Sources when live: COMEX front-month futures (GC=F), FRED DFII10, "
      "GLD and IAU daily bar lists, IMF International Financial "
      "Statistics, World Gold Council Gold Demand Trends, Swiss-Impex "
      "tariff heading 7108. Event rules: Feb 22 reserve freeze, Jun 22 "
      "G7 import ban, Jun 25 Iran war, Nov 25 CBR sales begin, May 26 "
      "escalation."
  )
  st.caption(
      "Bars: purchases reported to the IMF. Dashed: World Gold "
      "Council estimate of actual official demand. Shaded: the "
      "unreported residual. Mine supply lines: output above the "
      "lower line drains the Western float faster than the ground "
      "refills it."
  )

with st.container(horizontal=True, vertical_alignment='center'):
    st.markdown(f'<div class="legend-text" style="font-size:12.5px; white-space:nowrap;">'
                f'<b>Solid</b> reported{sep}<b>Dashed</b> estimated{sep}{dots}'
                f'{sep}Grey: other countries</div>', unsafe_allow_html=True)
    st.toggle("Mine supply", key="show_repl")

    if st.button("Bank detail"):
        show_bank_detail(declared, asof, t12, dz, pd, px, chart)
    if st.button("Sources & notes"):
        show_sources_notes()
 
# ======================================================= COUNTRY COMPARISONS ==
st.header("Explore selected countries")
options = sorted(declared["country"].unique())
countries = st.multiselect("Choose a country", options,
            default=[c for c in ["Singapore"] if c in options])
extra_colors = px.colors.qualitative.Prism + px.colors.qualitative.Safe
color_map = {c: (dz.hue(c) if dz.hue(c) != dz.REST else extra_colors[i % len(extra_colors)])
    for i, c in enumerate(options)}

left, right = st.columns([3, 2], gap="small")
if countries:
    with left:
        country_data = declared[declared["country"].isin(countries)]
    
        fig = px.bar(country_data, x="date", y="net_purchases_t", color="country",
            labels={"date": "Month", "net_purchases_t": "Tonnes", "country": "Country"},
            color_discrete_map=color_map)
    
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", showlegend=True, legend=dict(orientation="h",
            yanchor="top", y=-0.2, xanchor="center", x=0.5, title_side="left"))

        st.markdown("""<h3 style='text-align: center; font-style: italic; font-size: 1.1rem;'>
            Monthly purchases and sales by country (sample data)</h3>""", unsafe_allow_html=True)
    
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Declared official sector", text_alignment="center")
        st.caption(f"Trailing 12-month reported change - IMF, "
                   f"{fmt(asof['declared'])}", text_alignment="center")
        s = t12.sort_values()
        bar_colors = [color_map.get(c, dz.hue(c)) for c in s.index]
        f = go.Figure(go.Bar(x=s.values, y=s.index, orientation="h", marker_color=bar_colors,
            text=[f"{v:+,.0f}" for v in s.values], textposition="outside",
            textfont=dict(size=14, color=dz.FAINT), cliponaxis=False))
        f.update_xaxes(title="tonnes", showgrid=False)
        f.update_yaxes(side="left", gridcolor=dz.PAPER)
        f.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        chart(f, 330)
else:
    st.warning("Please select at least one country.")

st.markdown("""<h3 style='text-align: center; font-style: italic; font-size: 1.2rem;'>
            Country rank over time, who is buying the most?</h3>""", unsafe_allow_html=True)
st.caption("Rank of each country by trailing 12-month net purchases. "
            "#1 is the biggest net buyer; a falling line is rising buying.",
            text_alignment="center")

agg_period = st.selectbox("Aggregation Period", ["Year", "Quarter", "Month"], index=1)
freq_map = {"Year": "YE", "Quarter": "QE", "Month": "ME"}
pad_map = {"Year": 400, "Quarter": 120, "Month": 40}

df_agg = pd.to_datetime(declared['date'])
wide = (declared.groupby(['country', pd.Grouper(key='date', freq=freq_map[agg_period])])['net_purchases_t'].sum()
        .unstack(level='country', fill_value=0).sort_index())
rank = wide.rolling(1).sum().dropna(how="all").rank(axis=1, ascending=False, method="first").astype(int)
n = rank.shape[1]
hl = set(options) if options else set(rank.columns)
pad = pd.Timedelta(days=pad_map[agg_period])

fb = go.Figure()
for c in sorted(rank.columns, key=lambda x: x in hl):
    on = c in hl
    col = dz.hue(c) if on else "#d9d9d2"
    if on and col == dz.REST: col = "#6b6b63"
    fb.add_trace(go.Scatter(
        x=rank.index, y=rank[c], name=c, mode="lines+markers",
        line=dict(color=col, width=3 if on else 1.5),
        marker=dict(size=7 if on else 4, color=col),
        customdata=wide[c].round(0),
        hovertemplate=f"<b>{c}</b><br>rank %{{y}}<br>%{{customdata:+,.0f}} t<extra></extra>",
        opacity=1 if on else .8))

for side, idx, anchor, shift in [("left", -1, "left", 10), ("right", 0, "right", -1)]:
    for c, r in rank.iloc[idx].items():
        fb.add_annotation(x=rank.index[idx], y=r, text=c, showarrow=False, xanchor=anchor, xshift=shift,
                          font=dict(size=12, color=dz.INK if c in hl else dz.FAINT))

for d, _ in dz.EVENTS:
    if rank.index[0] <= pd.Timestamp(d) <= rank.index[-1]:
        fb.add_shape(type="line", x0=d, x1=d, y0=0, y1=1, yref="paper", line=dict(color=dz.GHOST, width=1.5))

fb.update_layout(
    height=560, hovermode="closest", showlegend=False, margin=dict(l=110, r=110, t=20, b=30),
    xaxis=dict(range=[rank.index[0] - pad, rank.index[-1] + pad]),
    yaxis=dict(autorange=False, range=[n + .5, .5], side="left", tickmode="array", 
               tickvals=[1, 5, 10, n], ticktext=["#1", "#5", "#10", f"#{n}"], showgrid=False))
st.plotly_chart(fb, use_container_width=True, config={"displayModeBar": False})



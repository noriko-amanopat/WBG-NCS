"""
CarePool — Individual Levy Calculator
Women's Budget Group | August 2026

Based on Section F (Levy Estimates) of CarePool_CarePool_Tool_v5.xlsx.

Running requires: streamlit, plotly  (pip install streamlit plotly)
"""
# ── Packages ──────────────────────────────────────────────────────────────
import math
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

# ── Figures/Icons ─────────────────────────────────────────────────────────
IMAGES_DIR      = Path(__file__).parent / "Images"
LOGO_PATH       = IMAGES_DIR / "WBG-Concepts_logo.svg"
ICON_EARNINGS   = IMAGES_DIR / "earnings.svg"
ICON_BIRTHDAY   = IMAGES_DIR / "birthday.svg"
ICON_DATE       = IMAGES_DIR / "date.svg"
ICON_ASSETS     = IMAGES_DIR / "assets.svg"

# ─── Page configuration ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="WBG's CarePool Contribution Calculator",
    page_icon=str(LOGO_PATH),
    layout="wide",
)

# The following commands tweak some Streamlit defaults:
# 1. Hide the "link to heading" anchor icon that Streamlit adds automatically to 
#    markdown headings (###, ####, etc.). In this case, there's nothing to link to.
# 2. darken # st.caption() text: Streamlit shows these at the same colour as body 
#    text but with opacity: 0.6, which is a bit too faint for some people.
# 3. let st.metric()'s delta text flow into a second line if needed.
st.markdown(
    "<style>"
    "[data-testid='stHeaderActionElements'] {display: none;}"
    "[data-testid='stCaptionContainer'] {opacity: 0.7;}" # adjust opacity of captions
    "[data-testid='stMetricDelta'] {height: auto; align-items: flex-start;}"
    "[data-testid='stMetricDelta'] [data-testid='stMarkdownContainer'],"
    "[data-testid='stMetricDelta'] [data-testid='stMarkdownContainer'] p "
    "{white-space: normal; overflow: visible;}"
    "</style>",
    unsafe_allow_html=True,
)

# ── Colour palette: WBG concepts ────────────────────────────────────────────────────────────
maincolour_1   = "#550692"  # deep purple — primary WBG colour 
colouraccent_1 = "#1B0692"
colouraccent_2 = "#062C92"
colouraccent_3 = "#066692"
maincolour_2   = "#069284"  # teal — primary CarePool colour 


# ── Constants (from CarePool_CarePool_Tool_v5.xlsx, Levy Estimates tab) ─────────────
# capitalised to make it easier to see where they are used in calculations, and to  
# avoid accidental reassignment – using python's numeric literal syntax for readability.

# Income tax
PA             = 12_570     # Personal allowance 2025-26
BASIC_UPPER    = 50_270     # Top of basic rate band
HIGHER_UPPER   = 125_140    # Top of higher rate band

# National Insurance
NI_LOWER       = 12_570
NI_UPPER       = 50_270
NI_MAIN        = 0.08       # Post-April 2025 employee NI rate
NI_UPPER_RATE  = 0.02

# Council tax
COUNCIL_TAX    = 1_628.25   # Band D, 25% single-person discount, 2024-25

# CarePool levy structure
K2             = 1.6        # r_higher / r_basic
K3             = 2.0        # r_additional / r_basic
SCALING        = 1.3532     # Weighted levy base / England wage bill

# Self-insurance saving horizon
RETIREMENT_AGE = 70         # assumed retirement age; default saving horizon = RETIREMENT_AGE − age

# Care cost constants (LaingBuisson, uplifted to Q2 2026 prices at +2.75%)
RESI_CARE_ANNUAL   = 69_356   # £/yr residential care home (£67,500 * 1.0275)
HOME_CARE_ANNUAL   = 33_751   # £/yr visiting home care, 3 hrs/day (£32,850 * 1.0275)
MEANS_TEST_UPPER   = 23_250   # upper capital limit: self-fund above this (frozen since 2010)
MEANS_TEST_LOWER   = 14_250   # lower capital limit: full LA support below this (frozen since 2010)
MEANS_TEST_MID     = 18_750   # midpoint assumption for £14,250–£23,250 band
# Tariff income for midpoint: £1/wk per £250 (or part) above lower limit → 18 * 52 = £936/yr
TARIFF_INCOME_ANNUAL = math.ceil((MEANS_TEST_MID - MEANS_TEST_LOWER) / 250) * 52  # £936
# see https://www.nhs.uk/social-care-and-support/money-work-and-benefits/when-the-council-might-pay-for-your-care/

# Year: aggregate levy rate (% of England wage bill)
# Phase 1: linear ramp from 1.0% (2026) to 2.0% (2035)
# Phase 2 (2036+, "CarePool launched"): 2.0% gross levy; pre-funded reserve
# investment income (~£9.7bn/yr) offsets net cost, keeping individual contributions stable.
ALL_YEARS = list(range(2026, 2037))  # 2026–2036 inclusive

def agg_rate_for_year(yr: int) -> float:
    if yr <= 2035:
        return 0.01 + 0.01 * (yr - 2026) / 9
    return 0.0200  # Phase 2 with pre-funded reserve

def year_label(yr: int) -> str:
    if yr <= 2035:
        return f"{yr}–{yr - 1999:02d}"
    return "CarePool launched<br>(2036–37)"

def year_label_plain(yr: int) -> str:
    if yr <= 2035:
        return f"{yr}–{yr - 1999:02d}"
    return "CarePool launched (2036–37)"


# ── Core calculator functions ─────────────────────────────────────────────────

def income_tax(y: float) -> float:
    # Bands are split on GROSS income (PA→BASIC_UPPER, BASIC_UPPER→HIGHER_UPPER,
    # above HIGHER_UPPER), not on taxable income with fixed band widths — the
    # latter silently assumes a full, untapered PA and overcharges anyone in or
    # above the £100k–£125,140 taper zone, since the 20%/40% bands need to
    # widen as the taper shrinks the PA rather than staying a fixed £37,700/
    # £74,870. Verified against the known "60% marginal rate" trap in that zone.
    pa   = max(0.0, PA - max(0.0, y - 100_000) / 2)
    tax  = 0.20 * max(0.0, min(y, BASIC_UPPER) - pa)
    tax += 0.40 * max(0.0, min(y, HIGHER_UPPER) - BASIC_UPPER)
    tax += 0.45 * max(0.0, y - HIGHER_UPPER)
    return tax

def ni_contributions(y: float) -> float:
    return (max(0.0, min(y, NI_UPPER) - NI_LOWER) * NI_MAIN
            + max(0.0, y - NI_UPPER) * NI_UPPER_RATE)

def carepool_levy(y: float, agg_rate: float) -> float:
    rb   = agg_rate / SCALING
    levy = max(0.0, min(y, BASIC_UPPER) - PA) * rb
    if y > BASIC_UPPER:
        levy += (min(y, HIGHER_UPPER) - BASIC_UPPER) * rb * K2
    if y > HIGHER_UPPER:
        levy += (y - HIGHER_UPPER) * rb * K3
    return levy

def levy_band_breakdown(y: float, agg_rate: float) -> dict:
    rb         = agg_rate / SCALING
    basic_inc  = max(0.0, min(y, BASIC_UPPER) - PA)
    higher_inc = max(0.0, min(y, HIGHER_UPPER) - BASIC_UPPER) if y > BASIC_UPPER else 0.0
    add_inc    = max(0.0, y - HIGHER_UPPER)                   if y > HIGHER_UPPER else 0.0
    return {
        "basic_income":  basic_inc,  "basic_rate":  rb,       "basic_levy":  basic_inc  * rb,
        "higher_income": higher_inc, "higher_rate": rb * K2,  "higher_levy": higher_inc * rb * K2,
        "add_income":    add_inc,    "add_rate":    rb * K3,  "add_levy":    add_inc    * rb * K3,
    }


# ── Style functions ─────────────────────────────────────────────────

def render_legend(items: list[tuple[str, str]] | list[tuple[str, str, bool]]) -> None:
    """Display a vertical legend (coloured swatch + colour-matched label) for the
    right-hand column next to a chart — Plotly's default legends support one
    uniform font colour, not one colour per entry. Pass a 3rd tuple element of
    True to draw the swatch with the same diagonal hatch as a patterned bar."""
    def swatch_style(color: str, hatched: bool) -> str:
        if hatched:
            # -45deg (not 45deg) to match Plotly's marker_pattern_shape="/",
            # which are the ones that appear in the legend marker.
            return (f"background-image:repeating-linear-gradient(-45deg,"
                     f"{color},{color} 3px,white 3px,white 6px);")
        return f"background:{color};"

    # html for the custom colour charts' legends
    rows = "".join(
        f'<div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:10px;">'
        f'<span style="flex:0 0 12px;width:12px;height:12px;border-radius:2px;'
        f'{swatch_style(item[1], len(item) > 2 and item[2])}margin-top:4px;"></span>'
        f'<span style="color:{item[1]};font-size:0.88rem;line-height:1.3;">{item[0]}</span>'
        f'</div>'
        for item in items
    )
    # render the legend in a div with some padding to separate it from the chart
    st.markdown(f'<div style="padding-top:1.5rem;">{rows}</div>', unsafe_allow_html=True)
    # Note that the setting `unsafe_allow_html=True` just tells Streamlit to render any 
    # HTML tags in between <div>...</div>. 

def icon_heading(icon_path: Path, text: str, help: str | None = None, icon_width: int = 28) -> None:
    """##### heading with a small SVG image as an icon to avoid looking blurriness.

    Pass `help` here (rather than on the widget below) when that widget uses
    label_visibility="collapsed" — Streamlit nests a widget's help tooltip
    inside its label, so collapsing the label also hides the tooltip icon,
    making that help text unreachable in the browser."""
    icon_col, text_col = st.columns([1, 20], vertical_alignment="center")
    with icon_col:
        st.image(str(icon_path), width=icon_width)
    with text_col:
        st.markdown(f"##### {text}", help=help)


# ––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
# ── Header of the page ──────────────────────────────────────────────────────────
# ––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

header_logo, header_title = st.columns([1, 8], gap="large", vertical_alignment="center")
with header_logo:
    st.image(str(LOGO_PATH))
with header_title:
    st.title(":primary[CarePool Contribution Calculator]")
st.markdown(
    "This app allows you to estimate your annual contribution to fund the proposed " 
    "Women's Budget Group National Care Service model, CarePool. Fill in your details "
    "below to see how much your CarePool Levy contribution would be and how it compares "
    "to self-funding care under the current rules. "
)

st.markdown("---")

# ––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
# ── User inputs/levers ──────────────────────────────────────────────────────────
# ––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
# Stacked one-per-row (rather than side-by-side columns) so labels, captions and
# help text have the full page width to work with — keeps them legible at larger
# font sizes on small screens.

icon_heading(
    ICON_EARNINGS, "Your annual salary",
    help=(
        "Enter your gross (pre-tax) annual salary. "
        "The default of £39,039 is England's median full-time salary (ONS, 2025–26)."
    ),
)
income = st.number_input(
    "Annual gross income (£)",
    min_value = 0,
    max_value = 500_000,
    value     = 39_039,
    step      = 500,
    format    = "%d",
    label_visibility = "collapsed",
)
st.caption(f"= £{income:,} · Default: £39,039 – England's median full-time salary (ONS 2025–26)")

icon_heading(
    ICON_BIRTHDAY, "Your age",
    help=(
        "This is used to set a sensible guess for the number of years you'd spread the cost of "
        f"an unforeseen care need, assuming the retirement age is around {RETIREMENT_AGE} years "
        "(e.g. a 40-year-old defaults to a 30-year spread). You can override this setting"
        "at the bottom of the chart below."
    ),
)
age = st.number_input(
    "Age",
    min_value = 18,
    max_value = 95,
    value     = 40,
    step      = 1,
    format    = "%d",
    label_visibility = "collapsed",
)
st.caption(f"Default saving horizon: {RETIREMENT_AGE} − age (min 5 yrs)")

icon_heading(
    ICON_DATE, "Year: For what year would you like to see your levy contribution?",
    help=(
            "Choose the year you'd like to see your CarePool contribution for. " 
            "The contribution slowly increases until the year of launch (2036). "
            "Go back to the main page to see details behind our calculations."
    ),
)
year = st.slider(
    "Year",
    min_value = 2026,
    max_value = 2036,
    value     = 2027,
    step      = 1,
    label_visibility = "collapsed",
)
if year <= 2035:
    phase_name = f"Phase 1: Year {year - 2025} of 10  ·  pre-funding"
else:
    phase_name = "Phase 2: CarePool launched"
st.caption(f"{year_label_plain(year)}  ·  {phase_name}")

icon_heading(ICON_ASSETS, "Assets or savings above £23,250?")
has_assets = st.radio(
    "Assets / savings level",
    options    = ["Yes (above £23,250)", "£14,250–£23,250", "No (below £14,250)"],
    index      = 0,
    horizontal = False,
    label_visibility = "collapsed",
)
with st.expander("What does this mean?"):
    st.markdown(
        "England's means-test for adult social care has two thresholds (both frozen since 2010):  \n"
        "- **Above £23,250** — you self-fund care in full until your assets fall below this level.  \n"
        "- **£14,250–£23,250** — the council helps, but you pay *tariff income*: "
        "£1/week for every £250 (or part) of capital above £14,250 "
        "(max ~£36/week ≈ £1,872/year at the top of the band).  \n"
        "- **Below £14,250** — the council pays in full; no tariff income.  \n\n"
        "Assets include savings **and** the value of your home if you need residential care. "
        "Most homeowners fall in the top band. See https://commonslibrary.parliament.uk/research-briefings/sn01911/"
    )

st.markdown("---")


# ── Compute values for key metrics and charts ────────────────────────────────────────────────────────────

# saving_years widget appears below the first chart but its value is needed here.
# Its default tracks age (RETIREMENT_AGE − age); re-seed session state whenever
# age changes, but leave a manual override in place while age stays the same.
default_saving_years = int(max(5, min(50, RETIREMENT_AGE - age)))
if st.session_state.get("_saving_years_age_seed") != age:
    st.session_state["saving_years_key"] = default_saving_years
    st.session_state["_saving_years_age_seed"] = age
saving_years = int(st.session_state.get("saving_years_key", default_saving_years))

it            = income_tax(income)
ni            = ni_contributions(income)
ct            = COUNCIL_TAX
current_total = it + ni + ct

agg      = agg_rate_for_year(year)
levy_now = carepool_levy(income, agg)
pct_inc  = levy_now / current_total * 100 if current_total > 0 else 0.0

# All-year series
all_levies = [carepool_levy(income, agg_rate_for_year(yr)) for yr in ALL_YEARS]
all_pcts   = [lv / current_total * 100 if current_total > 0 else 0.0 for lv in all_levies]
all_labels = [year_label(yr) for yr in ALL_YEARS]

# Self-insurance annual equivalents (Q2 2026 prices, spread over saving_years)
HOME_CARE_YEARS  = 2   # scenario: 2 years of home care
RESI_YEARS_CHART = 3   # scenario: 3 years of residential care

if has_assets == "Yes (above £23,250)":
    self_insure_home = (HOME_CARE_ANNUAL * HOME_CARE_YEARS) / saving_years
    self_insure_resi = (RESI_CARE_ANNUAL * RESI_YEARS_CHART) / saving_years
elif has_assets == "£14,250–£23,250":
    # Only tariff income applies (assume £18,750 midpoint → £936/yr)
    self_insure_home = (TARIFF_INCOME_ANNUAL * HOME_CARE_YEARS) / saving_years
    self_insure_resi = (TARIFF_INCOME_ANNUAL * RESI_YEARS_CHART) / saving_years
else:  # below £14,250
    self_insure_home = 0.0
    self_insure_resi = 0.0

# ── KEY METRICS ────────────────────────────────────────────────────────────────
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("CarePool contribution", f"£{levy_now/12:,.0f}/month", f"£{levy_now:,.0f}/year")
m2.metric("Increase on total tax paid", f"+{pct_inc:.1f}%")
m3.metric("Effective additional rate on income", f"{levy_now/income*100:.2f}%" if income > 0 else "—")
m4.metric(
    "Your total tax amount without CarePool",
    f"£{current_total:,.0f}",
)
m5.metric(
    "Your total tax amount with CarePool",
    f"£{current_total + levy_now:,.0f}",
    f"You'd pay £{levy_now:,.0f} more a year with the CarePool Levy",
)
st.markdown("---")

# ── First chart ──────────────────────────────────────────────────────────────────

# Stacked bar — before / with CarePool / without CarePool self-insurance scenarios
st.markdown("#### What would the cost of an unforeseen care need be with and without CarePool?")

if has_assets == "Yes (above £23,250)":
    no_assets_note = ""
elif has_assets == "£14,250–£23,250":
    no_assets_note = "<br><i>(tariff income only)</i>"
else:
    no_assets_note = "<br><i>(council pays)</i>"
bar_labels = [
    "Before CarePool<br>(today)",
    f"With CarePool<br>({year_label(year)})",
    f"Without CarePool<br>2yr home care*{no_assets_note}",
    f"Without CarePool<br>3yr residential*{no_assets_note}",
]

# Annotation text above each bar
def bar_top_text(extra, base):
    if extra == 0 and has_assets == "No (below £14,250)":
        return "Council pays"
    if extra == 0:
        return ""
    pct = extra / base * 100
    return f"+£{extra:,.0f}/yr<br>(+{pct:.0f}%)"

it_vals   = [it] * 4
ni_vals   = [ni] * 4
ct_vals   = [ct] * 4
levy_vals = [0, levy_now, 0, 0]
home_vals = [0, 0, self_insure_home, 0]
resi_vals = [0, 0, 0, self_insure_resi]

# Each trace handles its own top label so all sit at "outside" the same layer
levy_texts = ["", f"+£{levy_now:,.0f}/yr<br>(+{pct_inc:.0f}%)", "", ""]
resi_texts = ["", "", bar_top_text(self_insure_home, current_total),
                      bar_top_text(self_insure_resi, current_total)]

fig_bar = go.Figure()
fig_bar.add_bar(name="Income Tax",         x=bar_labels, y=it_vals,   marker_color=colouraccent_1,  legendgroup=2)
fig_bar.add_bar(name="National Insurance", x=bar_labels, y=ni_vals,   marker_color=colouraccent_2,  legendgroup=1)
fig_bar.add_bar(name="Council Tax",        x=bar_labels, y=ct_vals,   marker_color=colouraccent_3,  legendgroup=0)
fig_bar.add_bar(
    name="CarePool Levy",
    x=bar_labels, y=levy_vals, marker_color=maincolour_1, legendgroup=3,
    text=levy_texts, textposition="outside",
    textfont=dict(size=12, color=maincolour_1),
)
fig_bar.add_bar(
    name=f"No CarePool: 2yr home care (÷{saving_years}yr)",
    x=bar_labels, y=home_vals, marker_color=maincolour_2, legendgroup=4,
)
fig_bar.add_bar(
    name=f"No CarePool: 3yr residential (÷{saving_years}yr)",
    x=bar_labels, y=resi_vals, marker_color=maincolour_2, legendgroup=5,
    marker_pattern_shape="/",
    text=resi_texts, textposition="outside",
    textfont=dict(size=12, color=maincolour_2),
)

# Dashed divider between "With CarePool" (bar 1) and "Without CarePool" (bar 2)
fig_bar.add_vline(
    x=1.5, line_dash="dash", line_color="rgba(0,0,0,0.8)", line_width=1.5,
)
fig_bar.add_annotation(
    x=1.5525, y=0, yref="paper", yanchor="bottom", yshift=350,
    text="← with CarePool  |  without CarePool →",
    showarrow=False, font=dict(size=15, color="rgba(0,0,0,0.8)"),
    bgcolor="white",
)

y_max = max(current_total + levy_now,
            current_total + self_insure_home,
            current_total + self_insure_resi)

fig_bar.update_layout(
    barmode="stack",
    xaxis=dict(tickfont=dict(size=13)),
    yaxis=dict(
        tickprefix="£", tickformat=",",
        title="Annual contribution (£)",
        range=[0, y_max * 1.32],
    ),
    showlegend=False,
    height=470, margin=dict(t=20, b=10, l=0, r=0),
    plot_bgcolor="white", paper_bgcolor="white",
)
bar_chart_col, bar_legend_col = st.columns([2, 1])
with bar_chart_col:
    st.plotly_chart(fig_bar, use_container_width=True)
with bar_legend_col:
    render_legend([ 
        ("CarePool Levy", maincolour_1),
        (f"No CarePool: 2yr home care (÷{saving_years}yr)", maincolour_2),
        (f"No CarePool: 3yr residential (÷{saving_years}yr)", maincolour_2, True),
        ("Council Tax", colouraccent_3),
        ("National Insurance", colouraccent_2),
        ("Income Tax", colouraccent_1),
    ])
col_sy, _ = st.columns([5, 5])
with col_sy:
    st.number_input(
        "Years to spread self-funding costs",
        min_value=5, max_value=50, step=1,
        key="saving_years_key",
        help="How many years you'd have to save — defaults to your working years "
             f"remaining (retirement age {RETIREMENT_AGE} minus your age), but you "
             "can override it here.",
    )
mid_note = (
    f" Assets in the £14,250–£23,250 band, are assumed to be £{MEANS_TEST_MID:,} (midpoint) for the chart,"
    f"→ tariff income of £{TARIFF_INCOME_ANNUAL}/yr (£1/wk per £250 above £{MEANS_TEST_LOWER:,})."
    if has_assets == "£14,250–£23,250" else ""
)
st.caption(
    f"\\* The cost of self-funding (without CarePool) is spread equally over {saving_years} years of saving. "
    "The costs of residential care are assumed to be £69,356/yr (LaingBuisson, Q2 2026). "
    "The costs of home care are assumed to be £33,751/yr (3 hrs/day visiting care); these are current private-market rates. "
    f"Note: The chart does not account for investment returns or care cost inflation.{mid_note}"
)

# ── Context:  ──────────────────────────────────────────────────────────────────
# ── WITHOUT CarePool: SELF-FUNDING COMPARISON ──────────────────────────────────────

st.markdown("##### Key takeaways:")

RESI_YEARS = 3
resi_total = RESI_CARE_ANNUAL * RESI_YEARS
monthly_saving = resi_total / (saving_years * 12)

levy_yr1_monthly = carepool_levy(income, agg_rate_for_year(2026)) / 12
levy_now_monthly = levy_now / 12
sc1, sc2 = st.columns(2)

with sc1:
    if has_assets == "Yes (above £23,250)":
        st.markdown(
            f"Your assets exceed £{MEANS_TEST_UPPER:,}, so you would self-fund care "
            f"in full until you spend down below that threshold.  \n\n"
            f"**{RESI_YEARS} years of residential care** at current market rates "
            f"(£{RESI_CARE_ANNUAL:,}/yr, LaingBuisson, Q2 2026 prices) would cost around "
            f"**£{resi_total:,.0f}** in total.  \n\n"
            f"Saving for that over **{saving_years} years** (feel free to adjust the number"
            f"of years in the window above) means setting aside "
            f"**£{monthly_saving:,.0f}/month** on top of all your existing taxes."
        )
    elif has_assets == "£14,250–£23,250":
        tariff_total = TARIFF_INCOME_ANNUAL * RESI_YEARS
        tariff_monthly = tariff_total / (saving_years * 12)
        st.markdown(
            f"Your assets fall in the middle band (£{MEANS_TEST_LOWER:,}–£{MEANS_TEST_UPPER:,}). "
            f"The council would help, but you'd pay **tariff income** — £1/week per £250 of "
            f"capital above £{MEANS_TEST_LOWER:,}.  \n\n"
            f"Assuming you have £{MEANS_TEST_MID:,} assets (the midpoint), that's **£{TARIFF_INCOME_ANNUAL}/year**. "
            f"Over {RESI_YEARS} years of residential care, your total contribution would be "
            f"**£{tariff_total:,}**. This is far less than full self-funding, but not zero.  \n\n"
            f"Saving for that over **{saving_years} years** (feel free to adjust the number "
            f"of years in the window above) means setting aside "
            f"**£{tariff_monthly:,.0f}/month**."
        )
    else:  # below £14,250
        st.markdown(
            f"Your assets are below £{MEANS_TEST_LOWER:,}, so the council would pay your "
            f"care costs in full; no tariff income applies.  \n\n"
            f"Note that both thresholds have been frozen since 2010 and are not uprated "
            f"with inflation. If you accumulate savings or own a home over a working life, "
            f"you may well move into a higher band by the time you need care."
        )

with sc2:
    st.markdown("**Under CarePool, those same care years cost you nothing extra.**")
    st.markdown(
        f"The entitlement floor covers up to **4 years of residential care** and "
        f"**3 years of home care** in full regardless of your assets."
    )
    st.markdown(
        f"Your CarePool contribution would start at **£{levy_yr1_monthly:,.0f}/month** (2026–27) "
        f"and reaches **£{levy_now_monthly:,.0f}/month** by {year_label_plain(year)}.  \n\n"
    )
    if has_assets == "Yes (above £23,250)" and monthly_saving > levy_yr1_monthly:
        ratio = monthly_saving / levy_yr1_monthly
        st.success(
            f"Self-funding against just **one** {RESI_YEARS}-year residential care episode "
            f"would cost **{ratio:.1f}× more per month** than the CarePool contribution from day one — "
            f"and the contribution covers the worst case, not just one scenario."
        )
    elif has_assets == "£14,250–£23,250":
        st.success(
            f"To provide safeguards for individuals who earn above the income tax threshold (£12,570) " 
            f"but have limited accumulated assets, we need data on the distribution "
            f"of assets and savings across income and age bands. We will update out app once we "
            f"have analysed those data."
        )
    else:
        st.success(
            f"To provide safeguards for individuals who earn above the income tax threshold (£12,570) " 
            f"but have limited or no accumulated assets, we need data on the distribution"
            f"of assets and savings across income bands."
        )
        # st.success(
        #     f"Even if you have no assets, the CarePool contribution is a small monthly contribution "
        #     f"that guarantees coverage for the worst-case scenario; up to 4 years of residential care "
        #     f"and 3 years of home care."
        # )

    




st.markdown("---")

# ── Second chart ──────────────────────────────────────────────────────────────────
# Stacked bar — CarePool contribution on top of your existing IT/NI/Council Tax, by year
st.markdown("#### What would your monthly CarePool contribution be on top of today's total "
            "tax bill (Income Tax, National Insurance, Council Tax)?"
            )

all_monthly = [lv / 12 for lv in all_levies]
n_years     = len(ALL_YEARS)
monthly_it, monthly_ni, monthly_ct = it / 12, ni / 12, ct / 12
stack_top   = [monthly_it + monthly_ni + monthly_ct + m for m in all_monthly]

# Outline the selected year's bar so it's easy to spot amid the stack, and
# fade every year except the selected one and the CarePool-launch year (2036)
sel_idx        = ALL_YEARS.index(year)
launch_idx     = ALL_YEARS.index(2036)
line_widths    = [0.85 if i == sel_idx else 0 for i in range(n_years)]
line_colors    = ["#000000"] * n_years
bar_opacities  = [1.0 if i == sel_idx else 0.85 if i == launch_idx else 0.55 for i in range(n_years)]

fig_ts = go.Figure()
fig_ts.add_bar(
    name="Income Tax", x=all_labels, y=[monthly_it] * n_years,
    marker=dict(color=colouraccent_1, opacity=bar_opacities, line=dict(color=line_colors, width=line_widths)),
)
fig_ts.add_bar(
    name="National Insurance", x=all_labels, y=[monthly_ni] * n_years,
    marker=dict(color=colouraccent_2, opacity=bar_opacities, line=dict(color=line_colors, width=line_widths)),
)
fig_ts.add_bar(
    name="Council Tax", x=all_labels, y=[monthly_ct] * n_years,
    marker=dict(color=colouraccent_3, opacity=bar_opacities, line=dict(color=line_colors, width=line_widths)),
)
fig_ts.add_bar(
    name="CarePool Contribution", x=all_labels, y=all_monthly,
    marker=dict(color=maincolour_1, opacity=bar_opacities, line=dict(color=line_colors, width=line_widths)),
    text=[f"+{p:.1f}%" for p in all_pcts],
    textposition="outside",
    textfont=dict(size=11, color=maincolour_1),
    hovertemplate=(
        "<b>%{x}</b><br>"
        "Monthly levy: £%{y:,.2f}<br>"
        "Increase vs today: %{text}<extra></extra>"
    ),
)

# Subtle arrow annotation above the selected bar's stack
if levy_now > 0:
    fig_ts.add_annotation(
        x=all_labels[sel_idx],
        y=stack_top[sel_idx],
        yshift=34,
        text=f"◀ {year}",
        showarrow=False,
        font=dict(size=13, color=maincolour_1, family="Arial"),
        align="left",
    )

y_max = max(stack_top) if max(stack_top) > 0 else 100

# Dotted divider before "CarePool launched" bar
fig_ts.add_vline(
    x=9.5,
    line_dash="dot", line_color="rgba(0,0,0,0.8)", line_width=1.2,
)
fig_ts.add_annotation(
    x=8.65,
    y=y_max * 1.22,
    text="CarePool launched →",
    showarrow=False,
    font=dict(size=13, color=maincolour_1),
    align="center",
)

fig_ts.update_layout(
    barmode="stack",
    xaxis=dict(tickangle=-38, title="", tickfont=dict(size=12)),
    yaxis=dict(
        tickprefix="£", tickformat=",",
        title="Monthly contribution (£)",
        range=[0, y_max * 1.35],
    ),
    showlegend=False,
    height=430, margin=dict(t=40, b=10, l=0, r=10),
    plot_bgcolor="white", paper_bgcolor="white",
)
ts_chart_col, ts_legend_col = st.columns([2, 1])
with ts_chart_col:
    st.plotly_chart(fig_ts, use_container_width=True)
with ts_legend_col:
    render_legend([
        ("CarePool contribution", maincolour_1),
        ("Council Tax", colouraccent_3),
        ("National Insurance", colouraccent_2),
        ("Income Tax", colouraccent_1),
    ])

# ── CONTEXT BOXES ──────────────────────────────────────────────────────────────
st.markdown("---")
c1, c2 = st.columns(2)
with c1:
    levy_yr1 = carepool_levy(income, agg_rate_for_year(2026))
    pct_yr1  = levy_yr1 / current_total * 100 if current_total > 0 else 0
    st.info(
        f"**Starting contribution (2026–27):** £{levy_yr1/12:,.2f}/month · £{levy_yr1:,.0f}/yr  \n"
        f"A **{pct_yr1:.1f}% increase** on your current combined tax bill "
        f"of £{current_total:,.0f}/yr. The contribution starts low and ramps gradually."
    )
with c2:
    levy_yr10 = carepool_levy(income, agg_rate_for_year(2035))
    pct_yr10  = levy_yr10 / current_total * 100 if current_total > 0 else 0
    st.info(
        f"**By CarePool launch (2035–36):** £{levy_yr10/12:,.2f}/month · £{levy_yr10:,.0f}/yr  \n"
        f"A **{pct_yr10:.1f}% increase** on today's bill. The 10-year pre-funding phase "
        f"builds a **£194bn reserve** — so individual contributions stay stable at "
        f"launch rather than jumping further."
    )

# ── BANNER: link back to the full CarePool proposal ────────────────────────────
st.markdown(
    f"""
    <div style="background:{maincolour_1};border-radius:8px;padding:1rem 1.5rem;
                margin:1.5rem 0;display:flex;align-items:center;justify-content:space-between;
                gap:1rem;flex-wrap:wrap;">
        <span style="color:white;font-size:1rem;">
            Want to find out more about CarePool?
        </span>
        <a href="https://www.wbg.org.uk/publication-library/wbg-concepts/carepool/"
           target="_blank" rel="noopener noreferrer"
           style="background:white;color:{maincolour_1};padding:0.5rem 1.25rem;border-radius:6px;
                  text-decoration:none;font-weight:600;white-space:nowrap;">
            Click here to return to the CarePool homepage.
        </a>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── FOOTER ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "**Source:** CarePool_CarePool_Tool_v4.xlsx, Women's Budget Group, August 2026.  "
    "Aggregate levy rates from Fund Projection tab; progressive structure (k₂=1.6, k₃=2.0) "
    "and scaling ratio (1.353) from Levy Estimates tab Section G.  "
    "Income tax: 2025-26 rates including personal allowance taper above £100k. "
    "NI: post-April 2025 main rate (8%). "
    "Council tax: Band D with 25% single-person discount (MHCLG 2024-25).  "
    "Phase 2 (2036–37): gross levy held at 2.0% of wage bill; pre-funded reserve "
    "investment income (approx. £9.7bn/yr) offsets net cost, keeping individual contributions "
    "stable at Phase 1 Year 10 levels. Government backstop (approx. £8.8bn contingent liability) "
    "excluded from levy base."
)

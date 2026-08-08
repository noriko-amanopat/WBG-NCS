"""
NCS CarePool — Individual Levy Calculator
Women's Budget Group | August 2026

Based on Section F (Levy Estimates) of NCS_CarePool_Tool_v4.xlsx.

Run:  streamlit run ncs_levy_calculator.py
Requires: streamlit, plotly  (pip install streamlit plotly)
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(
    page_title="NCS CarePool Levy Calculator",
    page_icon="🏥",
    layout="wide",
)

# ── CONSTANTS (from NCS_CarePool_Tool_v4.xlsx, Levy Estimates tab) ─────────────
PA             = 12_570     # Personal allowance 2025-26
BASIC_UPPER    = 50_270     # Top of basic rate band
HIGHER_UPPER   = 125_140    # Top of higher rate band
NI_LOWER       = 12_570
NI_UPPER       = 50_270
NI_MAIN        = 0.08       # Post-April 2025 employee NI rate
NI_UPPER_RATE  = 0.02
COUNCIL_TAX    = 1_628.25   # Band D, 25% single-person discount, 2024-25
K2             = 1.6        # r_higher / r_basic
K3             = 2.0        # r_additional / r_basic
SCALING        = 1.3532     # Weighted levy base / England wage bill

# Year → aggregate levy rate (% of England wage bill)
# Phase 1: linear ramp from 1.0% (2026) to 2.0% (2035)
# Phase 2 (2036+, "NCS launched"): 2.0% gross levy; pre-funded reserve
# investment income (~£9.7bn/yr) offsets net cost, keeping individual contributions stable.
ALL_YEARS = list(range(2026, 2037))  # 2026–2036 inclusive


def agg_rate_for_year(yr: int) -> float:
    if yr <= 2035:
        return 0.01 + 0.01 * (yr - 2026) / 9
    return 0.0200  # Phase 2 with pre-funded reserve


def year_label(yr: int) -> str:
    if yr <= 2035:
        return f"{yr}–{yr - 1999:02d}"
    return "NCS launched<br>(2036–37)"


def year_label_plain(yr: int) -> str:
    if yr <= 2035:
        return f"{yr}–{yr - 1999:02d}"
    return "NCS launched (2036–37)"


# ── CORE CALCULATION FUNCTIONS ─────────────────────────────────────────────────

def income_tax(y: float) -> float:
    pa      = max(0.0, PA - max(0.0, y - 100_000) / 2)
    taxable = max(0.0, y - pa)
    tax     = min(taxable, 37_700) * 0.20
    if taxable > 37_700:
        tax += min(taxable - 37_700, 74_870) * 0.40
    if taxable > 112_570:
        tax += (taxable - 112_570) * 0.45
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


# ── HEADER ─────────────────────────────────────────────────────────────────────
st.title("🏥 NCS CarePool — Individual Levy Calculator")
st.markdown(
    "Estimate your annual contribution to the proposed **Social Care Levy** under the "
    "Women's Budget Group National Care Service (NCS) model. The levy funds a guaranteed "
    "floor of home and residential care for everyone in England, built up through a "
    "10-year pre-funding phase before NCS launches in 2036–37."
)

with st.expander("ℹ️ What assumptions are behind these figures?"):
    st.markdown(
        """
To keep costs manageable, WBG proposes a **guaranteed entitlement floor** rather than open-ended coverage:
the state covers care costs up to a set number of years, individuals contribute for a window after that,
and a government backstop then kicks in for the very longest-term cases — protecting people from catastrophic costs
without unlimited public liability.

The levy figures shown here correspond to a floor that covers:
- **4 years of residential care** and **3 years of home care** (with a 15 hours/week cap)

Because WBG is committed to fair pay for care workers, all costs are calculated using **fair wages —
equivalent to 75% of NHS Band 4 pay** (the band covering healthcare assistants and senior care workers).
This is meaningfully above current average care sector wages, and reflects the workforce investment
a well-functioning NCS would require.

On the funding side, the model assumes that inheritance tax (IHT) revenue is hypothecated to the NCS fund
(OBR 2026–27 estimate: £9.5bn, growing to ~£26bn by 2036–37), alongside redirected local authority adult
social care spending and a levy on private equity providers' excess profits.
        """
    )

st.markdown("---")

# ── PROMINENT INPUTS ───────────────────────────────────────────────────────────
col_sal, col_yr = st.columns([3, 2])

with col_sal:
    st.markdown("### 💷 Enter your annual salary")
    income = st.number_input(
        "Annual gross income (£)",
        min_value=0,
        max_value=500_000,
        value=39_039,
        step=500,
        format="%d",
        help=(
            "Enter your gross (pre-tax) annual salary. "
            "The default of £39,039 is the England median full-time salary (ONS, 2025–26)."
        ),
        label_visibility="collapsed",
    )
    st.caption("Default: £39,039 — England median full-time salary (ONS 2025–26)")

with col_yr:
    st.markdown("### 📅 Pick a year")
    year = st.slider(
        "Year",
        min_value=2026,
        max_value=2036,
        value=2027,
        step=1,
        label_visibility="collapsed",
    )
    if year <= 2035:
        phase_name = f"Phase 1 — Year {year - 2025} of 10  ·  pre-funding"
    else:
        phase_name = "Phase 2 — NCS launched 🎉"
    st.caption(f"{year_label_plain(year)}  ·  {phase_name}")

st.markdown("---")

# ── COMPUTED VALUES ────────────────────────────────────────────────────────────
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

# ── KEY METRICS ────────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("NCS levy", f"£{levy_now/12:,.0f}/month", f"£{levy_now:,.0f}/year")
m2.metric("Increase on current tax bill", f"+{pct_inc:.1f}%")
m3.metric("Effective rate on income", f"{levy_now/income*100:.2f}%" if income > 0 else "—")
m4.metric(
    "Current taxes (IT + NI + CT)",
    f"£{current_total:,.0f}",
    f"→ £{current_total + levy_now:,.0f} with levy",
)

st.markdown("---")

# ── CHARTS ────────────────────────────────────────────────────────────────────
left, right = st.columns(2)

# LEFT: stacked bar — before vs this year
with left:
    st.markdown("#### Where your money goes")
    bar_labels = ["Before NCS<br>(today)", f"With NCS levy<br>({year_label(year)})"]

    fig_bar = go.Figure()
    fig_bar.add_bar(
        name="Income Tax",
        x=bar_labels, y=[it, it],
        marker_color="#1f4e79",
    )
    fig_bar.add_bar(
        name="National Insurance",
        x=bar_labels, y=[ni, ni],
        marker_color="#2e75b6",
    )
    fig_bar.add_bar(
        name="Council Tax",
        x=bar_labels, y=[ct, ct],
        marker_color="#9dc3e6",
    )
    fig_bar.add_bar(
        name="CarePool Levy",
        x=bar_labels, y=[0, levy_now],
        marker_color="#c00000",
        text=["", f"+{pct_inc:.1f}%"],
        textposition="outside",
        textfont=dict(size=13, color="#c00000"),
    )
    fig_bar.update_layout(
        barmode="stack",
        yaxis=dict(tickprefix="£", tickformat=",", title="Annual contribution (£)"),
        legend=dict(orientation="h", y=1.1, x=0),
        height=430, margin=dict(t=40, b=10, l=0, r=0),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# RIGHT: bar chart — levy trajectory by year with % increase labels on top
with right:
    st.markdown("#### Your monthly CarePool levy by year  (% increase vs today's taxes)")

    all_monthly = [lv / 12 for lv in all_levies]

    bar_colors = []
    for yr in ALL_YEARS:
        if yr == year:
            bar_colors.append("#c00000")        # selected: deep red
        elif yr > 2035:
            bar_colors.append("#7030a0")        # Phase 2: purple
        else:
            bar_colors.append("#2e75b6")        # Phase 1: blue

    fig_ts = go.Figure()
    fig_ts.add_bar(
        x=all_labels,
        y=all_monthly,
        marker_color=bar_colors,
        text=[f"+{p:.1f}%" for p in all_pcts],
        textposition="outside",
        textfont=dict(size=9, color="#333333"),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Monthly levy: £%{y:,.2f}<br>"
            "Increase vs today: %{text}<extra></extra>"
        ),
    )

    # Subtle arrow annotation on selected bar
    sel_idx = ALL_YEARS.index(year)
    if levy_now > 0:
        fig_ts.add_annotation(
            x=all_labels[sel_idx],
            y=all_monthly[sel_idx],
            yshift=36,
            text=f"◀ {year}",
            showarrow=False,
            font=dict(size=10, color="#c00000", family="Arial"),
            align="left",
        )

    # Dotted divider before "NCS launched" bar
    fig_ts.add_vline(
        x=9.5,
        line_dash="dot", line_color="#888888", line_width=1.2,
    )
    fig_ts.add_annotation(
        x=10,
        y=max(all_monthly) * 1.22 if max(all_monthly) > 0 else 100,
        text="NCS launched →",
        showarrow=False,
        font=dict(size=9, color="#7030a0"),
        align="center",
    )

    y_max = max(all_monthly) if max(all_monthly) > 0 else 100
    fig_ts.update_layout(
        xaxis=dict(tickangle=-38, title="", tickfont=dict(size=9)),
        yaxis=dict(
            tickprefix="£", tickformat=",",
            title="Monthly levy (£)",
            range=[0, y_max * 1.35],
        ),
        showlegend=False,
        height=430, margin=dict(t=40, b=10, l=0, r=10),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig_ts, use_container_width=True)

# ── CONTEXT BOXES ──────────────────────────────────────────────────────────────
st.markdown("---")
c1, c2 = st.columns(2)
with c1:
    levy_yr1 = carepool_levy(income, agg_rate_for_year(2026))
    pct_yr1  = levy_yr1 / current_total * 100 if current_total > 0 else 0
    st.info(
        f"**Starting levy (2026–27):** £{levy_yr1/12:,.2f}/month · £{levy_yr1:,.0f}/yr  \n"
        f"A **{pct_yr1:.1f}% increase** on your current combined tax bill "
        f"of £{current_total:,.0f}/yr. The levy starts low and ramps gradually."
    )
with c2:
    levy_yr10 = carepool_levy(income, agg_rate_for_year(2035))
    pct_yr10  = levy_yr10 / current_total * 100 if current_total > 0 else 0
    st.info(
        f"**By NCS launch (2035–36):** £{levy_yr10/12:,.2f}/month · £{levy_yr10:,.0f}/yr  \n"
        f"A **{pct_yr10:.1f}% increase** on today's bill. The 10-year pre-funding phase "
        f"builds a **£194bn reserve** — so individual contributions stay stable at "
        f"launch rather than jumping further."
    )

# ── WITHOUT NCS: SELF-FUNDING COMPARISON ──────────────────────────────────────
st.markdown("---")
st.markdown("### What would care cost you without NCS?")

# Care cost constants (LaingBuisson, uplifted to Q2 2026 prices at +2.75%)
RESI_CARE_ANNUAL = 69_356   # £/yr residential care home (£67,500 × 1.0275)
MEANS_TEST_THRESHOLD = 23_250  # £ savings threshold for council support (statutory, unchanged since 2010)

RESI_YEARS = 3   # illustrative duration for comparison
resi_total = RESI_CARE_ANNUAL * RESI_YEARS

sc1, sc2, sc3 = st.columns([2, 2, 1])

with sc3:
    saving_years = st.number_input(
        "Years to save",
        min_value=5, max_value=50, value=40, step=1,
        help="How many years you'd have to set money aside. "
             "Roughly your working years remaining — e.g. 40 if you're around 25, 30 if you're around 35.",
    )

monthly_saving = resi_total / (saving_years * 12)

with sc1:
    st.markdown(
        f"""
**Without NCS**, whether the council helps depends on your savings:

- If you have **less than £{MEANS_TEST_THRESHOLD:,}** in savings when you need adult social care,
  the local council contributes towards your costs.
- If you have **more than £{MEANS_TEST_THRESHOLD:,}** — for example, if you own a home —
  you are expected to fund your own care until your assets fall below that threshold.

If you needed **{RESI_YEARS} years of residential care** at current market rates
(£{RESI_CARE_ANNUAL:,}/yr, LaingBuisson, Q2 2026 prices), the total bill would be around
**£{resi_total:,.0f}**.

To cover that by saving gradually over **{saving_years} years**, you would need to set
aside roughly **£{monthly_saving:,.0f}/month** — on top of everything else.
        """
    )

with sc2:
    st.markdown("**Under NCS, those same 3 years cost you nothing extra.**")
    st.markdown(
        f"The NCS entitlement floor covers up to **4 years of residential care** and "
        f"**3 years of home care** in full. Any episode within those limits is paid by the state."
    )
    levy_yr1_monthly = carepool_levy(income, agg_rate_for_year(2026)) / 12
    levy_now_monthly = levy_now / 12
    st.markdown(
        f"Your NCS levy starts at **£{levy_yr1_monthly:,.0f}/month** (2026–27) "
        f"and reaches **£{levy_now_monthly:,.0f}/month** by {year_label_plain(year)} — "
        f"compared to the **£{monthly_saving:,.0f}/month** you would need to self-insure "
        f"against the same scenario."
    )
    if monthly_saving > levy_now_monthly:
        ratio = monthly_saving / levy_yr1_monthly
        st.success(
            f"Self-insuring against just **one** 3-year residential care episode "
            f"would cost **{ratio:.1f}× more per month** than the NCS levy from day one — "
            f"and the levy covers the worst case, not just one scenario."
        )

# ── BAND BREAKDOWN ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Levy breakdown by income band")
st.caption(
    f"Showing {year_label_plain(year)} "
    f"(aggregate rate: {agg*100:.3f}% of England wage bill · "
    f"basic rate: {agg/SCALING*100:.3f}%)"
)

bd = levy_band_breakdown(income, agg)
bd_df = pd.DataFrame([
    {
        "Band": "Basic rate  (£12,570 – £50,270)",
        "Your income in band": f"£{bd['basic_income']:,.0f}",
        "Levy rate": f"{bd['basic_rate']*100:.3f}%",
        "Levy": f"£{bd['basic_levy']:,.2f}",
    },
    {
        "Band": "Higher rate  (£50,270 – £125,140)",
        "Your income in band": f"£{bd['higher_income']:,.0f}",
        "Levy rate": f"{bd['higher_rate']*100:.3f}%",
        "Levy": f"£{bd['higher_levy']:,.2f}",
    },
    {
        "Band": "Additional rate  (above £125,140)",
        "Your income in band": f"£{bd['add_income']:,.0f}",
        "Levy rate": f"{bd['add_rate']*100:.3f}%",
        "Levy": f"£{bd['add_levy']:,.2f}",
    },
    {
        "Band": "TOTAL",
        "Your income in band": f"£{bd['basic_income']+bd['higher_income']+bd['add_income']:,.0f}",
        "Levy rate": "—",
        "Levy": f"£{bd['basic_levy']+bd['higher_levy']+bd['add_levy']:,.2f}",
    },
])
st.dataframe(bd_df, use_container_width=True, hide_index=True)

# ── ALL-YEAR COMPARISON TABLE ──────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Full year-by-year comparison")
rows = []
for yr in ALL_YEARS:
    ar  = agg_rate_for_year(yr)
    lv  = carepool_levy(income, ar)
    pct = lv / current_total * 100 if current_total > 0 else 0
    rows.append({
        "Year": year_label_plain(yr),
        "Phase": "Phase 1 — pre-funding" if yr <= 2035 else "Phase 2 — NCS launched",
        "Agg. rate (% WB)": f"{ar*100:.3f}%",
        "Monthly": f"£{lv/12:,.0f}",
        "Annual levy": f"£{lv:,.0f}",
        "% increase vs today": f"+{pct:.1f}%",
        "As % of gross income": f"{lv/income*100:.2f}%" if income > 0 else "—",
    })
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── FOOTER ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "**Source:** NCS_CarePool_Tool_v4.xlsx, Women's Budget Group, August 2026.  "
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

# ta_dashboard.py
import pandas as pd, numpy as np, streamlit as st, plotly.express as px

st.set_page_config(page_title="TA Dashboard", layout="wide")

# ---- Sidebar / Settings ----
st.sidebar.header("Settings")
PATH = st.sidebar.text_input("Excel file path", r"F:\TA\powerbi.xlsx")
upload = st.sidebar.file_uploader("...or upload Excel", type=["xlsx"])
ALERT_PERM = st.sidebar.number_input("Alert if %Permanent below", 0.0, 100.0, 25.0, 1.0)

st.title("Recruiter & Client Dashboard")

# ---- Load workbook (all sheets) ----
def load_book(u, p):
    if u:
        import io
        return pd.read_excel(io.BytesIO(u.read()), sheet_name=None)
    return pd.read_excel(p, sheet_name=None)

sheets = load_book(upload, PATH)

# ---- Get sheets by name or auto-detect ----
rec_df = sheets.get("RecruiterData")
cli_df = sheets.get("ClientWise")

def autodetect(d, key):
    for df in d.values():
        if df is None: continue
        if set(df.columns) >= {"Date", key, "Total", "Subcon", "Permanent"}:
            return df.copy()
    return None

if rec_df is None: rec_df = autodetect(sheets, "Recruiter")
if cli_df is None: cli_df = autodetect(sheets, "Client")

if rec_df is None:
    st.error("Need sheet with columns: Date, Recruiter, Total, Subcon, Permanent."); st.stop()

# ---- Clean recruiter + filters ----
rec_df["Date"] = pd.to_datetime(rec_df["Date"], errors="coerce")
rec_df = rec_df.dropna(subset=["Date"])
rec_df["Date"] = rec_df["Date"].dt.date

dates = sorted(rec_df["Date"].unique())
d0, d1 = (dates[0], dates[-1]) if dates else (None, None)
rng = st.sidebar.date_input("Recruiter date range", (d0, d1)) if d0 else (None, None)

recs = sorted(rec_df["Recruiter"].unique())
pick_recs = st.sidebar.multiselect("Recruiters", recs, default=recs)

rf = rec_df.copy()
if rng and all(rng): rf = rf[(rf["Date"] >= rng[0]) & (rf["Date"] <= rng[1])]
if pick_recs: rf = rf[rf["Recruiter"].isin(pick_recs)]
if rf.empty: st.warning("No recruiter data after filters."); st.stop()

# ---- Recruiter KPIs ----
team_total = int(rf["Total"].sum())
team_subc  = int(rf["Subcon"].sum())
team_perm  = int(rf["Permanent"].sum())
p_subc     = (team_subc/team_total*100) if team_total else 0
p_perm     = (team_perm/team_total*100) if team_total else 0

by_rec = rf.groupby("Recruiter", as_index=False).agg(
    Total=("Total","sum"), Subcon=("Subcon","sum"), Permanent=("Permanent","sum")
)
top_sub_rec  = by_rec.sort_values("Subcon", ascending=False).iloc[0]["Recruiter"]
top_perm_rec = by_rec.sort_values("Permanent", ascending=False).iloc[0]["Recruiter"]

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("Total", f"{team_total}")
c2.metric("% Subcon", f"{p_subc:.1f}%")
c3.metric("% Permanent", f"{p_perm:.1f}%")

if p_perm < ALERT_PERM:
    st.warning(f"Team %Permanent {p_perm:.1f}% below {ALERT_PERM:.1f}%")

# ---- Recruiter charts ----
st.subheader("Daily Trend by Recruiter")
st.plotly_chart(px.line(rf, x="Date", y="Total", color="Recruiter", markers=True),
                use_container_width=True)

st.subheader("Subcon vs Permanent by Recruiter (Stacked)")
mix_rec = by_rec[["Recruiter","Subcon","Permanent"]]
st.plotly_chart(px.bar(mix_rec, x="Recruiter", y=["Subcon","Permanent"], barmode="stack"),
                use_container_width=True)

# ---- ClientWise handling (day-only support) ----
if cli_df is not None:
    cf = cli_df.copy()
    # detect day-only numbers
    day_mode = pd.to_numeric(cf["Date"], errors="coerce").dropna().le(31).all()
    if day_mode:
        cf["Day"] = pd.to_numeric(cf["Date"], errors="coerce").astype("Int64")
        dmin, dmax = int(cf["Day"].min()), int(cf["Day"].max())
        day_sel = st.sidebar.slider("Client day filter", dmin, dmax, (dmin, dmax))
        cf = cf[(cf["Day"] >= day_sel[0]) & (cf["Day"] <= day_sel[1])]
        xcol = "Day"
    else:
        cf["Date"] = pd.to_datetime(cf["Date"], errors="coerce")
        cf = cf.dropna(subset=["Date"]); cf["Date"] = cf["Date"].dt.date
        cdates = sorted(cf["Date"].unique())
        crng = st.sidebar.date_input("Client date range", (cdates[0], cdates[-1]))
        cf = cf[(cf["Date"] >= crng[0]) & (cf["Date"] <= crng[1])]
        xcol = "Date"

    if not cf.empty:
        by_cli = cf.groupby("Client", as_index=False).agg(
            Total=("Total","sum"), Subcon=("Subcon","sum"), Permanent=("Permanent","sum")
        )
        # Top clients row
  

        st.subheader("Subcon vs Permanent by Client (Stacked)")
        st.plotly_chart(px.bar(by_cli, x="Client", y=["Subcon","Permanent"], barmode="stack"),
                        use_container_width=True)

        st.subheader(f"Client Trend by {xcol}")
        st.plotly_chart(px.line(cf, x=xcol, y="Total", color="Client", markers=True),
                        use_container_width=True)

# ---- Consistency table (full width) ----
st.subheader("Consistency, Quality & Target Gaps")
st.caption("Lower Consistency = steadier daily output")
cons = (rf.groupby("Recruiter")
          .agg(Consistency=("Total", lambda s: np.nanstd(s, ddof=0)),
               AvgDaily=("Total","mean"),
               TotalSum=("Total","sum"),
               PermSum=("Permanent","sum"),
               SubconSum=("Subcon","sum"))
          .reset_index())
cons["%Permanent"] = (cons["PermSum"]/cons["TotalSum"]*100).round(1)
cons["%Subcon"]    = (cons["SubconSum"]/cons["TotalSum"]*100).round(1)
st.dataframe(cons.sort_values("Consistency"), use_container_width=True)

st.caption("Append new rows to Excel and click Rerun in Streamlit.")

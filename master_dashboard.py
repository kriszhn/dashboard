
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Master Dashboard", layout="wide")
st.title("Master Record Dashboard")

# File input
file_path = st.sidebar.text_input("Excel file path", r"F:\TA\master.xlsx")

@st.cache_data
def load_excel(path):
    try:
        return pd.read_excel(path)
    except:
        return None

df = load_excel(file_path)
if df is None:
    st.error("Failed to load the file. Check the path and try again.")
    st.stop()

#st.write(df.columns.tolist())  # ← ADD THIS LINE HERE

# Clean and normalize column names
df.columns = df.columns.str.strip().str.lower()

# Use the cleaned column name
#df["req received date"] = pd.to_datetime(df["req received date"], errors="coerce")
df["req received date"] = pd.to_datetime(df["req received date"], format="%d-%b-%y", errors="coerce")
df = df.dropna(subset=["req received date"])

# Filter
min_date, max_date = df["req received date"].min(), df["req received date"].max()
d_from, d_to = st.sidebar.date_input("Date range", (min_date, max_date))
mask = (df["req received date"].dt.date >= d_from) & (df["req received date"].dt.date <= d_to)
df = df.loc[mask]

# ---- make numeric columns truly numeric ----
NUM_COLS = [
    "no of open position", "profiles submitted", "screen select from client",
    "feedback pending", "l1 select", "l2 select", "final select",
    "onboarded", "screen reject from client", "l1 reject", "l2 reject",
    "total", "subcon", "permanent"
]

def force_numeric(s):
    # handles commas, +, %, text like "10+"
    return (pd.to_numeric(
        s.astype(str)
         .str.replace(',', '', regex=False)
         .str.extract(r'([-+]?\d*\.?\d+)')[0],  # take first number
        errors='coerce'
    ).fillna(0))

for c in NUM_COLS:
    if c in df.columns:
        df[c] = force_numeric(df[c]).astype(int)


# KPIs
st.subheader("Summary KPIs")
col1, col2, col3 = st.columns(3)
col1.metric("Total Open Positions", df["no of open position"].sum())
col2.metric("Total Profiles Submitted", df["profiles submitted"].sum())
col3.metric("Total Onboarded", df["onboarded"].sum())

# Client-wise summary
st.subheader("Client-wise Summary")
by_client = df.groupby("customer name").agg({
    "no of open position": "sum",
    "profiles submitted": "sum",
    "screen select from client": "sum",
    "l1 select": "sum",
    "l2 select": "sum",
    "final select": "sum",
    "onboarded": "sum"
}).reset_index()
st.dataframe(by_client)

# Recruiter performance
st.subheader("Recruiter-wise Performance")
by_rec = df.groupby("recruiter assigned").agg({
    "profiles submitted": "sum",
    "screen select from client": "sum",
    "final select": "sum",
    "onboarded": "sum"
}).reset_index()
st.dataframe(by_rec)

# Charts
st.subheader("Profiles Submitted Over Time")
daily = df.groupby(df["req received date"].dt.date)["profiles submitted"].sum().reset_index()
fig = px.line(daily, x="req received date", y="profiles submitted", title="Daily Submissions")
st.plotly_chart(fig, use_container_width=True)

# Aging analysis
st.subheader("Aging Analysis (Open positions)")
df["age (days)"] = (pd.Timestamp.today().normalize() - df["req received date"]).dt.days
aging = df[["customer name", "job title", "no of open position", "req received date", "age (days)"]]
st.dataframe(aging.sort_values("age (days)", ascending=False))

# ---- Pending Counts ----
if all(c in df.columns for c in ["screen select from client", "l1 select", "l1 reject"]):
    df["l1 pending"] = df["screen select from client"] - (df["l1 select"] + df["l1 reject"])

if all(c in df.columns for c in ["l1 select", "l2 select", "l2 reject"]):
    df["l2 pending"] = df["l1 select"] - (df["l2 select"] + df["l2 reject"])

if all(c in df.columns for c in ["l2 select", "final select"]):
    df["final pending"] = df["l2 select"] - df["final select"]

# ---- Client-wise Pending Summary ----
pending_summary = df.groupby("customer name", dropna=False).agg({
    "l1 pending": "sum",
    "l2 pending": "sum",
    "final pending": "sum"
}).reset_index()

st.subheader("Client-wise Pending Counts")
st.dataframe(pending_summary)

# --- Role-wise profiles submitted ---
ROLE = "job title"           # or "role"/"position" if that’s your header
CLIENT = "customer name"
SUBMIT = "profiles submitted"

# 1) Overall by role
role_summary = (df.groupby(ROLE, dropna=False)[SUBMIT]
                  .sum().sort_values(ascending=False).reset_index())
st.subheader("Profiles Submitted by Role")
st.dataframe(role_summary)

# 2) Client + role
client_role = (df.groupby([CLIENT, ROLE], dropna=False)[SUBMIT]
                 .sum().reset_index())
st.subheader("Client-wise Profiles per Role")
st.dataframe(client_role)

# 3) Quick filter & chart
sel_client = st.multiselect("Filter clients", sorted(df[CLIENT].dropna().unique()))
sel_role   = st.multiselect("Filter roles",   sorted(df[ROLE].dropna().unique()))

f = df.copy()
if sel_client: f = f[f[CLIENT].isin(sel_client)]
if sel_role:   f = f[f[ROLE].isin(sel_role)]

chart = (f.groupby([CLIENT, ROLE], dropna=False)[SUBMIT]
           .sum().reset_index())
fig = px.bar(chart, x=ROLE, y=SUBMIT, color=CLIENT, barmode="group",
             title="Profiles Submitted per Role (by Client)")
st.plotly_chart(fig, use_container_width=True)

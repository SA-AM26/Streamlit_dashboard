import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import os
import base64

st.set_page_config(
    page_title="DAS Manufacturing",
    page_icon="🏢",
    layout="wide"
)
    
# --- Sidebar configuration ---
st.sidebar.header("🔧 Settings")

rejection_threshold = st.sidebar.slider(
    "Rejection Threshold (NG Count)",
    min_value=1,
    max_value=10,
    value=3,
    step=1,
    help="Reject parts with more than this number of NG dimensions"
)

ng_chance_percent = st.sidebar.slider(
    "NG Chance (%)",
    min_value=0,
    max_value=100,
    value=10,
    step=1,
    help="Chance for a dimension to go NG"
)

ng_chance = ng_chance_percent / 100

# --- Feature specs ---
features = [
    {"name": "height_emboss_top", "mean": 5.20, "min": 4.90, "max": 5.20},
    {"name": "height_chamfer_top", "mean": 2.25, "min": 2.00, "max": 2.25},
    {"name": "height_emboss_bottom", "mean": 2.00, "min": 1.85, "max": 2.15},
    {"name": "outer_dia", "mean": 81.60, "min": 81.50, "max": 81.65},
    {"name": "central_pivot_dia", "mean": 11.60, "min": 11.60, "max": 11.70},
    {"name": "angle_1", "mean": 120.00, "min": 120.00, "max": 120.00},
    {"name": "angle_2", "mean": 119.77, "min": 119.77, "max": 119.77},
    {"name": "angle_3", "mean": 120.23, "min": 120.23, "max": 120.23},
    {"name": "flatness", "mean": 0.03, "min": 0.00, "max": 0.10},
    {"name": "dia_circle", "mean": 13.00, "min": 12.95, "max": 13.05}
]

# --- Initialize session state ---
if "part_num" not in st.session_state:
    st.session_state.part_num = 1
if "parts_df" not in st.session_state:
    st.session_state.parts_df = pd.DataFrame(columns=["timestamp", "part_id", "part_type"] + [f["name"] for f in features])

# --- Alternating LH/RH ---
side = "LH" if st.session_state.part_num % 2 == 1 else "RH"
part_id = f"{side} PART_{st.session_state.part_num:03d}"

# --- Generate value ---
def generate_value(feat):
    low, high, mean = feat["min"], feat["max"], feat["mean"]
    if np.random.rand() > ng_chance:
        val = np.random.normal(loc=mean, scale=(high - low) / 12)
        return round(np.clip(val, low, high), 4)
    else:
        return round(high + (high - low) * 0.1, 4) if np.random.rand() > 0.5 else round(low - (high - low) * 0.1, 4)

# --- Create new part ---
part_data = {"timestamp": datetime.now().replace(microsecond=0), "part_id": part_id, "part_type": side}
for feat in features:
    part_data[feat["name"]] = generate_value(feat)

st.session_state.parts_df = pd.concat([st.session_state.parts_df, pd.DataFrame([part_data])], ignore_index=True)

# --- Good/NG check ---
def check_status(row):
    ng_count = 0
    status = {}
    for feat in features:
        name, low, high = feat["name"], feat["min"], feat["max"]
        val = row[name]
        ok = np.isclose(val, low, atol=0.01) if low == high else low <= val <= high
        status[name] = "Good" if ok else "NG"
        if not ok:
            ng_count += 1
    return pd.Series(status), ng_count

status_rows = []
ng_counts = []

for _, row in st.session_state.parts_df.iterrows():
    status_row, ng_count = check_status(row)
    status_row.index = [f"{col}_status" for col in status_row.index]
    status_rows.append(status_row)
    ng_counts.append(ng_count)

status_df = pd.DataFrame(status_rows).reset_index(drop=True)

result_df = pd.concat([
    st.session_state.parts_df.reset_index(drop=True),
    status_df
], axis=1)
result_df["NG_count"] = ng_counts
result_df["Part_Status"] = result_df["NG_count"].apply(lambda x: "Rejected" if x > rejection_threshold else "Accepted")

# --- UI ---
st.title("🟢 Real-Time Plate Holder Inspection Dashboard")

# --- Show image based on part type ---
latest_part = result_df.tail(1).iloc[0]
image_file = "lh_part.jpg" if latest_part["part_type"] == "LH" else "rh_part.jpg"
if os.path.exists(image_file):
    encoded_image = base64.b64encode(open(image_file, 'rb').read()).decode()
    st.markdown(f"""
    <div style='text-align: center;'>
        <img src="data:image/jpeg;base64,{encoded_image}" width="300"/>
        <p style='text-align:center;'><b>{latest_part['part_type']} Part</b></p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.warning(f"Image '{image_file}' not found. Please make sure it's in the project folder.")

st.info("Generating a new part every second...")

# --- Latest part table ---
st.markdown("### 🆕 Latest Part")
dimension_names = [f["name"] for f in features]
selected_dimensions = st.multiselect("📌 Select Dimensions to Display:", options=dimension_names, default=dimension_names)

base_columns = ["timestamp", "part_id", "part_type", "Part_Status", "NG_count"]
selected_status_columns = [f"{name}_status" for name in selected_dimensions]
display_columns = base_columns + selected_dimensions + selected_status_columns

latest_part_df = result_df.tail(1)[display_columns].reset_index(drop=True).rename(columns=lambda x: x.replace("_", " ").title())
latest_part_df.index = [""]  # Remove index label
st.table(latest_part_df)

# --- Dimension Quality Cards ---
for side in ["LH", "RH"]:
    st.markdown(f"### 🔍 Dimension Quality Indicator - {side}")
    filtered_df = result_df[result_df["part_type"] == side]

    if not filtered_df.empty:
        filtered = filtered_df.tail(1).iloc[0]
        cols = st.columns(len(selected_dimensions))

        for col, dim in zip(cols, selected_dimensions):
            status = filtered[f"{dim}_status"]
            bg_color = "#2ecc71" if status == "Good" else "#e74c3c"

            with col:
                st.markdown(
                    f"""
                    <div style="
                        background-color: {bg_color};
                        padding: 10px;
                        border-radius: 8px;
                        text-align: center;
                        color: white;
                        font-weight: bold;
                        font-size: 12px;
                        line-height: 1.4;
                    ">
                        {dim.replace('_', ' ').title()}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

# --- LH & RH Split Table ---
for side in ["LH", "RH"]:
    side_df = result_df[result_df["part_type"] == side]
    acc_df = side_df[side_df["Part_Status"] == "Accepted"]
    rej_df = side_df[side_df["Part_Status"] == "Rejected"]

    st.markdown(f"## {'🗭' if side == 'LH' else '🔵'} {side} Parts")
    st.write(f"**Total:** {len(side_df)} | ✅ Accepted: {len(acc_df)} | ❌ Rejected: {len(rej_df)}")

    with st.expander("✅ Accepted Parts"):
        st.dataframe(acc_df[display_columns].reset_index(drop=True), use_container_width=True)
        csv_acc = acc_df[display_columns].to_csv(index=False)
        st.download_button(
            label=f"📅 Download {side} Accepted Parts",
            data=csv_acc,
            file_name=f"{side}_accepted_parts.csv",
            mime="text/csv"
        )

    with st.expander("❌ Rejected Parts"):
        st.dataframe(rej_df[display_columns].reset_index(drop=True), use_container_width=True)
        csv_rej = rej_df[display_columns].to_csv(index=False)
        st.download_button(
            label=f"📅 Download {side} Rejected Parts",
            data=csv_rej,
            file_name=f"{side}_rejected_parts.csv",
            mime="text/csv"
        )

# --- Refresh ---
st_autorefresh(interval=1000, limit=None, key="auto_refresh")
st.session_state.part_num += 1

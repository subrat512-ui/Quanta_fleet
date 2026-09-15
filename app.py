import streamlit as st
import pandas as pd
import random

# -----------------------------
# Page configuration
# -----------------------------
st.set_page_config(
    page_title="Green Quanta",
    page_icon="🌱",
    layout="wide"
)

st.title("🌱 Green Quanta")
st.caption("Quantum-Inspired Green Fleet Optimization")

st.divider()

# -----------------------------
# Sidebar inputs
# -----------------------------
st.sidebar.header("Scenario Inputs")

scenario_name = st.sidebar.text_input(
    "Scenario Name",
    "Demo Fleet Optimization"
)

number_of_vessels = st.sidebar.number_input(
    "Number of Vessels",
    min_value=1,
    max_value=20,
    value=3
)

number_of_routes = st.sidebar.number_input(
    "Number of Routes",
    min_value=1,
    max_value=20,
    value=3
)

st.sidebar.subheader("Objective Weights")

fuel_weight = st.sidebar.slider(
    "Fuel Importance (%)",
    0,
    100,
    50
)

emission_weight = st.sidebar.slider(
    "Emission Importance (%)",
    0,
    100,
    30
)

cost_weight = st.sidebar.slider(
    "Cost Importance (%)",
    0,
    100,
    20
)

total_weight = fuel_weight + emission_weight + cost_weight

if total_weight != 100:
    st.sidebar.warning(
        f"Total objective weight is {total_weight}%. It should equal 100%."
    )

st.sidebar.subheader("Optimization Settings")

iterations = st.sidebar.number_input(
    "Iterations",
    min_value=5,
    max_value=500,
    value=50
)

samples_per_iteration = st.sidebar.number_input(
    "Samples per Iteration",
    min_value=5,
    max_value=100,
    value=20
)

run_optimization = st.sidebar.button(
    "🚀 Run Optimization",
    use_container_width=True
)

# -----------------------------
# Main input tables
# -----------------------------
st.subheader("🚢 Fleet Details")

fleet_data = pd.DataFrame({
    "Vessel": [f"V{i+1}" for i in range(number_of_vessels)],
    "Vessel Type": ["Container"] * number_of_vessels,
    "Capacity (tonnes)": [1500] * number_of_vessels,
    "Available": [True] * number_of_vessels
})

fleet_data = st.data_editor(
    fleet_data,
    use_container_width=True,
    num_rows="dynamic"
)

st.subheader("🗺️ Route Details")

route_data = pd.DataFrame({
    "Route": [f"R{i+1}" for i in range(number_of_routes)],
    "Distance (km)": [400] * number_of_routes,
    "Cargo Demand (tonnes)": [800] * number_of_routes,
    "Deadline": ["18:00"] * number_of_routes
})

route_data = st.data_editor(
    route_data,
    use_container_width=True,
    num_rows="dynamic"
)

st.subheader("🌦️ Environmental Conditions")

col1, col2, col3, col4 = st.columns(4)

with col1:
    wind_speed = st.number_input("Wind Speed (m/s)", value=12.0)

with col2:
    wave_height = st.number_input("Wave Height (m)", value=1.8)

with col3:
    sea_current = st.number_input("Sea Current (m/s)", value=0.7)

with col4:
    water_temperature = st.number_input(
        "Water Temperature (°C)",
        value=18.0
    )

# -----------------------------
# Optimization demo
# -----------------------------
if run_optimization:

    st.divider()
    st.subheader("✅ Optimization Results")

    # Demo result for first UI draft
    random.seed(42)

    baseline_fuel = 1450
    optimized_fuel = 1240

    baseline_emissions = 710
    optimized_emissions = 580

    baseline_cost = 9250
    optimized_cost = 8400

    objective_score = 712

    fuel_reduction = (
        (baseline_fuel - optimized_fuel) / baseline_fuel
    ) * 100

    emission_reduction = (
        (baseline_emissions - optimized_emissions)
        / baseline_emissions
    ) * 100

    cost_reduction = (
        (baseline_cost - optimized_cost) / baseline_cost
    ) * 100

    # -----------------------------
    # KPI cards
    # -----------------------------
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    kpi1.metric(
        "Total Fuel",
        f"{optimized_fuel} units",
        f"-{fuel_reduction:.1f}%"
    )

    kpi2.metric(
        "Emissions",
        f"{optimized_emissions} kg",
        f"-{emission_reduction:.1f}%"
    )

    kpi3.metric(
        "Operating Cost",
        f"€{optimized_cost}",
        f"-{cost_reduction:.1f}%"
    )

    kpi4.metric(
        "Objective Score",
        objective_score,
        "Best Found"
    )

    # -----------------------------
    # Recommended plan
    # -----------------------------
    st.subheader("🚢 Recommended Fleet Plan")

    optimized_plan = pd.DataFrame({
        "Vessel": ["V1", "V2", "V3"],
        "Route": ["R1", "R2", "R3"],
        "Cargo (tonnes)": [800, 1000, 600],
        "Fuel": ["LNG", "MGO", "LNG"],
        "Speed (knots)": [12, 13, 12],
        "Trim (degrees)": [1.2, 0.8, 1.0],
        "Predicted Fuel": [420, 510, 310],
        "Status": ["Feasible", "Feasible", "Feasible"]
    })

    st.dataframe(
        optimized_plan,
        use_container_width=True,
        hide_index=True
    )

    # -----------------------------
    # Optimization evolution
    # -----------------------------
    st.subheader("📈 Optimization Evolution")

    evolution_data = pd.DataFrame({
        "Iteration": list(range(1, iterations + 1)),
        "Best Objective": [
            1200 - (488 * i / iterations)
            for i in range(1, iterations + 1)
        ]
    })

    st.line_chart(
        evolution_data.set_index("Iteration")
    )

    # -----------------------------
    # Probability evolution
    # -----------------------------
    st.subheader("⚛️ Quantum Probability Evolution")

    probability_data = pd.DataFrame({
        "Decision": [
            "V1 uses LNG",
            "V2 uses MGO",
            "V1 uses Route R1",
            "V1 uses 12 knots"
        ],
        "Initial Probability": [0.50, 0.50, 0.50, 0.50],
        "Final Probability": [0.91, 0.72, 0.88, 0.84]
    })

    st.dataframe(
        probability_data,
        use_container_width=True,
        hide_index=True
    )

    # -----------------------------
    # Baseline comparison
    # -----------------------------
    st.subheader("📊 Baseline vs Optimized")

    comparison_data = pd.DataFrame({
        "Metric": ["Fuel", "Emissions", "Operating Cost"],
        "Baseline": [
            baseline_fuel,
            baseline_emissions,
            baseline_cost
        ],
        "Optimized": [
            optimized_fuel,
            optimized_emissions,
            optimized_cost
        ]
    })

    st.bar_chart(
        comparison_data.set_index("Metric")
    )

    st.success(
        "Demo optimization completed. "
        "The real quantum optimizer will be connected next."
    )

else:
    st.info(
        "Enter your fleet requirements in the sidebar "
        "and click 'Run Optimization'."
    )
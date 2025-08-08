import streamlit as st
import pandas as pd
from pathlib import Path
import pypsa
from plot_dispatch import plot_dispatch

# Page config
st.set_page_config(
    page_title="Energy Dispatch Analysis",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] p {
        font-size: 12px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Cache network loading and scenario data
@st.cache_data
def get_scenarios(resolution="30mins"):
    """Get available scenarios for specified resolution"""
    scen_dir = Path(f"results/scenarios/{resolution}")
    if scen_dir.exists():
        return {p.stem: str(p) for p in sorted(scen_dir.glob("*.nc"))}
    return {}

@st.cache_data
def load_scenario_objectives(resolution="30mins"):
    """Load scenario objectives from CSV for specified resolution"""
    try:
        results_dir = Path(f"results/scenarios/{resolution}")
        csv_files = list(results_dir.glob("scenarios_summary_*.csv"))
        
        if not csv_files:
            st.warning(f"No scenarios_summary_*.csv file found in results/scenarios/{resolution}/")
            return {}
        
        # Use the most recent CSV file
        csv_file = sorted(csv_files)[-1]
        
        # Read only the first two columns (Scenario and Objective)
        df_results = pd.read_csv(csv_file, usecols=[0, 1])
        
        # Create a dictionary mapping scenario name to objective
        objectives = {}
        
        for _, row in df_results.iterrows():
            scenario_name = str(row.iloc[0])
            objective = str(row.iloc[1])
            
            if pd.notna(scenario_name) and pd.notna(objective):
                objective = objective.replace("\\n", "\n")
                objectives[scenario_name] = objective
        
        st.sidebar.success(f"✅ Loaded {len(objectives)} objectives from {csv_file.name}")
        return objectives
        
    except Exception as e:
        st.sidebar.error(f"Error loading scenario objectives: {e}")
        return {}

@st.cache_data
def load_network(path_str: str):
    """Load PyPSA network with caching"""
    return pypsa.Network(path_str)

@st.cache_data
def get_network_info(scenario_path: str):
    """Get basic network info without loading full network"""
    try:
        n = load_network(scenario_path)
        return {
            'regions': list(n.buses.index),
            'start_date': n.snapshots.min().date(),
            'end_date': n.snapshots.max().date()
        }
    except Exception as e:
        st.error(f"Error loading network info: {e}")
        return None

def main():
    st.title("⚡ High-Level NEM Dispatch Analysis")
    st.markdown("Interactive visualisation of PyPSA dispatch scenarios at different temporal resolutions.")
    
    # Sidebar controls
    st.sidebar.header("📊 Controls")
    
    # Resolution selection (at the top of sidebar)
    resolution = st.sidebar.selectbox(
        "⏱️ Temporal Resolution:",
        options=["30mins", "60mins"],
        help="Select the temporal resolution for analysis. 30mins is a slightly modified subset of scenarios, with some scenarios not available at 30mins resolution."
    )
    
    # Load scenarios and objectives based on selected resolution
    scenarios = get_scenarios(resolution)
    scenario_objectives = load_scenario_objectives(resolution)
    
    if not scenarios:
        st.error(f"No scenarios found in `results/scenarios/{resolution}/` directory!")
        st.info(f"Please ensure your `.nc` files are in the `results/scenarios/{resolution}/` folder.")
        return
    
    # Scenario selection
    scenario_name = st.sidebar.selectbox(
        "Scenario:",
        options=list(scenarios.keys()),
        help="Select the energy scenario to analyze - this will load the corresponding network data. Scenarios are scaled-up from the *0_2024_baseline* baseline scenario."
    )
    
    # Get network info for selected scenario
    network_info = get_network_info(scenarios[scenario_name])
    
    if not network_info:
        st.error("Failed to load scenario data")
        return
    
    # Get objective for selected scenario
    scenario_objective = scenario_objectives.get(scenario_name, "")
    
    # Display scenario objective if available
    if scenario_objective:
        st.sidebar.header("📋 Scenario Objective")
        st.sidebar.markdown(
            scenario_objective.replace("\n", "<br>"),
            unsafe_allow_html=True
        )
    
    # Region selection
    regions = st.sidebar.multiselect(
        "Regions:",
        options=network_info['regions'],
        default=network_info['regions'],
        help="Select one or more regions to include in the analysis"
    )
    
    # Date selection
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date:",
            value=network_info['start_date'],
            min_value=network_info['start_date'],
            max_value=network_info['end_date'],
            help="Select the start date for analysis"
        )
    
    with col2:
        # Adjust default days based on resolution
        default_days = 7
        max_days = 365
        
        days = st.number_input(
            "Days:",
            min_value=1,
            max_value=max_days,
            value=default_days,
            help=f"Number of days to analyse."
        )
    
    # Options
    st.sidebar.markdown("### 🔧 Display Options")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        show_imports = st.checkbox(
            "Imports/Exports",
            value=True,
            help="Show import/export flows"
        )
    
    with col2:
        show_curtailment = st.checkbox(
            "Curtailment",
            value=True,
            help="Show renewable curtailment (wind, utility-scale solar & rooftop solar)"
        )
    
    # Get the objective from the loaded CSV data
    csv_scenario_name = scenario_name
    scenario_objective_from_csv = scenario_objectives.get(csv_scenario_name, "")
    
    # Auto-generate plot when inputs change
    if regions:
        generate_plot(
            scenario_name=scenario_name,
            scenario_path=scenarios[scenario_name],
            start_date=start_date,
            days=days,
            regions=regions,
            show_imports=show_imports,
            show_curtailment=show_curtailment,
            scenario_objective=scenario_objective_from_csv,
            resolution=resolution
        )
    
    # Info panel
    with st.sidebar.expander("ℹ️ Scenario Info"):
        st.write(f"**Resolution:** {resolution}")
        st.write(f"**Available regions:** {len(network_info['regions'])}")
        st.write(f"**Date range:** {network_info['start_date']} to {network_info['end_date']}")
        st.write(f"**Selected regions:** {len(regions) if regions else 0}")
        if scenario_objectives:
            st.write(f"**Objectives loaded:** {len(scenario_objectives)} scenarios")
    
    st.sidebar.markdown("<span style='font-size: 11px; color: gray;'>by Grant Chalmers</span>", unsafe_allow_html=True)
    
    # Show warning if no regions selected
    if not regions:
        st.sidebar.warning("⚠️ Please select at least one region to display the plot.")

def generate_plot(scenario_name, scenario_path, start_date, days, regions, show_imports, show_curtailment, scenario_objective="", resolution="30mins"):
    """Generate and display the dispatch plot"""
    
    try:
        with st.spinner("🔄 Updating plot..."):
            n = load_network(scenario_path)
            
            # Convert date to string format
            start_date_str = start_date.strftime("%Y-%m-%d")
            
            # Generate plot with scenario_objective
            fig = plot_dispatch(
                n,
                time=start_date_str,
                days=days,
                regions=regions,
                show_imports=show_imports,
                show_curtailment=show_curtailment,
                scenario_name=scenario_name,
                scenario_objective=scenario_objective,
                interactive=True,
            )
            
            # Enhance the plot title
            title_parts = [
                f"Scenario: {scenario_name}",
                f"Resolution: {resolution}",
                f"Start: {start_date_str}",
                f"Duration: {days} days",
                f"Regions: {', '.join(regions[:3])}{'...' if len(regions) > 3 else ''}",
            ]
            
            fig.update_layout(
                title=f"Dispatch Analysis<br><sub>{' | '.join(title_parts)}</sub>",
                height=700
            )
        
        # Display the plot
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error generating plot: {str(e)}")
        with st.expander("🐛 Debug Info"):
            st.exception(e)

if __name__ == "__main__":
    main()
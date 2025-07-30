import streamlit as st
import pandas as pd
from pathlib import Path
from functools import lru_cache
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
def get_scenarios():
    """Get available scenarios"""
    scen_dir = Path("results/scenarios")
    if scen_dir.exists():
        return {p.stem: str(p) for p in sorted(scen_dir.glob("*.nc"))}
    return {}

@st.cache_data
def load_scenario_objectives():
    """Load scenario objectives from CSV"""
    try:
        # Look for the CSV file (you may need to adjust the pattern)
        results_dir = Path("results/scenarios")
        csv_files = list(results_dir.glob("scenarios_summary_*.csv"))
        
        if not csv_files:
            st.warning("No scenarios_summary_*.csv file found in results/scenarios/")
            return {}
        
        # Use the most recent CSV file (or you could make this configurable)
        csv_file = sorted(csv_files)[-1]  # Get the latest one
        
        # Read only the first two columns (Scenario and Objective)
        df_results = pd.read_csv(csv_file, usecols=[0, 1])
        
        # Create a dictionary mapping scenario name to objective
        objectives = {}
        
        # Iterate through each row to get scenario name and objective
        for _, row in df_results.iterrows():
            scenario_name = str(row.iloc[0])  # First column (Scenario)
            objective = str(row.iloc[1])      # Second column (Objective)
            
            if pd.notna(scenario_name) and pd.notna(objective):
                # Process the objectives (replace \\n with actual newlines if needed)
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
    st.title("⚡ NEM High-Level Dispatch Analysis")
    st.markdown("Interactive visualisation of PyPSA dispatch scenarios")
    
    # Load scenarios and objectives
    scenarios = get_scenarios()
    scenario_objectives = load_scenario_objectives()
    
    if not scenarios:
        st.error("No scenarios found in `results/scenarios/` directory!")
        st.info("Please ensure your `.nc` files are in the `results/scenarios/` folder.")
        return
    
    # Sidebar controls
    st.sidebar.header("📊 Controls")
    
    # Scenario selection
    scenario_name = st.sidebar.selectbox(
        "Scenario:",
        options=list(scenarios.keys()),
        help="Select the energy scenario to analyze"
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
        default=network_info['regions'],  # Select all by default
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
        days = st.number_input(
            "Days:",
            min_value=1,
            max_value=90,
            value=7,
            help="Number of days to analyze"
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
            help="Show renewable curtailment"
        )
    
    # Get the objective from the loaded CSV data (no user input needed)
    # Map scenario file name to CSV scenario name by removing 'scenario_' prefix if present
    csv_scenario_name = scenario_name
        
    scenario_objective_from_csv = scenario_objectives.get(csv_scenario_name, "")
    
        
    # Auto-generate plot when inputs change
    if regions:  # Only generate if regions are selected
        generate_plot(
            scenario_name=scenario_name,
            scenario_path=scenarios[scenario_name],
            start_date=start_date,
            days=days,
            regions=regions,
            show_imports=show_imports,
            show_curtailment=show_curtailment,
            scenario_objective=scenario_objective_from_csv
        )
    
    # Info panel
    with st.sidebar.expander("ℹ️ Scenario Info"):
        st.write(f"**Available regions:** {len(network_info['regions'])}")
        st.write(f"**Date range:** {network_info['start_date']} to {network_info['end_date']}")
        st.write(f"**Selected regions:** {len(regions) if regions else 0}")
        if scenario_objectives:
            st.write(f"**Objectives loaded:** {len(scenario_objectives)} scenarios")
    
    # Show warning if no regions selected
    if not regions:
        st.sidebar.warning("⚠️ Please select at least one region to display the plot.")

def generate_plot(scenario_name, scenario_path, start_date, days, regions, show_imports, show_curtailment, scenario_objective=""):
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
        
        # Summary statistics
        # with st.expander("📈 Plot Summary"):
        #     col1, col2, col3, col4 = st.columns(4)
            
        #     with col1:
        #         st.metric("Scenario", scenario_name)
        #     with col2:
        #         st.metric("Regions", len(regions))
        #     with col3:
        #         st.metric("Duration", f"{days} days")
        #     with col4:
        #         st.metric("Start Date", start_date_str)
        
        # Export options
        # st.markdown("### 💾 Export Options")
        # col1, col2 = st.columns(2)
        
        # with col1:
        #     if st.button("📊 Download Plot Data"):
        #         st.info("Plot data export feature - implement based on your needs")
        
        # with col2:
        #     if st.button("🖼️ Save as HTML"):
        #         html_str = fig.to_html(include_plotlyjs='cdn')
        #         st.download_button(
        #             label="Download HTML",
        #             data=html_str,
        #             file_name=f"dispatch_{scenario_name}_{start_date_str}.html",
        #             mime="text/html"
        #         )
    
    except Exception as e:
        st.error(f"Error generating plot: {str(e)}")
        with st.expander("🐛 Debug Info"):
            st.exception(e)

if __name__ == "__main__":
    main()
# ⚡ pypsa_dispatch_app

A simple Streamlit web app for interactive visualization and analysis of electricity dispatch scenarios using [PyPSA](https://pypsa.org/).

---

## Features

- Load and explore energy dispatch scenarios from NetCDF and CSV files
- Interactive Plotly visualizations
- Region and date selection
- Export plot data as CSV

---

## Demo

_You can deploy your own version using [Streamlit Community Cloud](https://streamlit.io/cloud)._  

[Live Demo](https://your-app-name.streamlit.app/) 

---

## Installation

1. **Clone this repository**
    ```bash
    git clone https://github.com/chalg/pypsa_dispatch_app.git
    cd pypsa_dispatch_app
    ```

2. **Install dependencies**

    It’s recommended to use a virtual environment:
    ```bash
    python -m venv .venv
    source .venv/bin/activate     # On Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    ```

3. **Run the app**

    ```bash
    streamlit run streamlit_app.py
    ```

    The app will open at [http://localhost:8501](http://localhost:8501).

---

## Directory Structure

```plaintext
pypsa_dispatch_app/
│
├── streamlit_app.py # Main Streamlit app
├── plot_dispatch.py # Plotting functions
├── requirements.txt # Python dependencies
├── results/ # Results directory (contains scenario files)
│ └── scenarios/ # Put your scenario .nc and .csv files here
└── .streamlit/
└── config.toml # Streamlit settings (default to light theme)
```

--

## Theme

The app defaults to **light mode** for all users via `.streamlit/config.toml`:

```toml
[theme]
base="light"
```

Author
by Grant Chalmers


Made with [Streamlit](https://streamlit.io/) & [PyPSA](https://pypsa.org/).
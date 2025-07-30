# Plotting function for generation dispatch
# Interactive version (optional)
import pandas as pd
import numpy as np


def plot_dispatch(n, time="2024", days=None, regions=None,
                   show_imports=True, show_curtailment=True,
                   scenario_name=None, scenario_objective=None, interactive=False):
     """
     Plot a generation dispatch stack by carrier for a PyPSA network, with optional
     net imports/exports and a region‑filtered curtailment overlay.

     Parameters
     ----------
     n : pypsa.Network
         The PyPSA network to plot.
     time : str, default "2024"
         Start of the time window (e.g. "2024", "2024-07", or "2024-07-15").
     days : int, optional
         Number of days from `time` to include in the plot.
     regions : list of str, optional
         Region bus names to filter by. If None, the entire network is included.
     show_imports : bool, default True
         Whether to include net imports/exports in the dispatch stack.
     show_curtailment : bool, default True
         Whether to calculate and plot VRE curtailment (Solar, Wind, Rooftop Solar).
     scenario_name : str, optional
         Scenario label to display below the title.
     scenario_objective : str, optional
         Objective description to display next to the legend.
     interactive : bool, default False
         Whether to create an interactive plot using Plotly instead of matplotlib.

     Notes
     -----
     - All power values are converted to GW.
     - Curtailment is plotted as a dashed black line if enabled.
     - Demand (load) is plotted as a solid green line.
     - Storage charging and net exports (negative values) are shown below zero.
     """
     
     
     if interactive:
         import plotly.graph_objects as go
         from plotly.subplots import make_subplots
         import plotly.express as px
     else:
         import matplotlib.pyplot as plt
     
     # 1) REGION MASKS
     if regions is not None:
         gen_mask   = n.generators.bus.isin(regions)
         sto_mask   = n.storage_units.bus.isin(regions) if not n.storage_units.empty else []
         store_mask = n.stores.bus.isin(regions) if not n.stores.empty else []
         region_buses = set(regions)
         
     else:
        gen_mask = pd.Series(True, index=n.generators.index)
        sto_mask = pd.Series(True, index=n.storage_units.index) if not n.storage_units.empty else pd.Series(dtype=bool)
        store_mask = pd.Series(True, index=n.stores.index) if not n.stores.empty else pd.Series(dtype=bool)
        region_buses = set(n.buses.index)

     # 2) AGGREGATE BY CARRIER (GW)
     def _agg(df_t, df_stat, mask):
         return (
             df_t.loc[:, mask]
                 .T
                 .groupby(df_stat.loc[mask, 'carrier'])
                 .sum()
                 .T
                 .div(1e3)
         )

     p_by_carrier = _agg(n.generators_t.p, n.generators, gen_mask)
     if not n.storage_units.empty:
         p_by_carrier = pd.concat([p_by_carrier,
                                   _agg(n.storage_units_t.p, n.storage_units, sto_mask)],
                                  axis=1)
     if not n.stores.empty:
         p_by_carrier = pd.concat([p_by_carrier,
                                   _agg(n.stores_t.p, n.stores, store_mask)],
                                  axis=1)

     # 3) TIME WINDOW
     parts = time.split("-")
     if len(parts) == 1:
         start = pd.to_datetime(f"{parts[0]}-01-01")
     elif len(parts) == 2:
         start = pd.to_datetime(f"{parts[0]}-{parts[1]}-01")
     else:
         start = pd.to_datetime(time)

     if days is not None:
         end = start + pd.Timedelta(days=days) - pd.Timedelta(hours=1)
     elif len(parts) == 1:
         end = pd.to_datetime(f"{parts[0]}-12-31 23:00")
     elif len(parts) == 2:
         end = start + pd.offsets.MonthEnd(0) + pd.Timedelta(hours=23)
     else:
         end = start + pd.Timedelta(hours=23)

     p_slice = p_by_carrier.loc[start:end].copy()
     # drop carriers with zero activity
     zero = p_slice.columns[p_slice.abs().sum() == 0]
     p_slice.drop(columns=zero, inplace=True)

     # 4) IMPORTS/EXPORTS
     if show_imports:
         ac = ( n.lines_t.p0.loc[start:end, n.lines.bus1.isin(region_buses) & ~n.lines.bus0.isin(region_buses)].sum(axis=1)
              + n.lines_t.p1.loc[start:end, n.lines.bus0.isin(region_buses) & ~n.lines.bus1.isin(region_buses)].sum(axis=1) )
         dc = ( n.links_t.p0.loc[start:end, n.links.bus1.isin(region_buses) & ~n.links.bus0.isin(region_buses)].sum(axis=1)
              + n.links_t.p1.loc[start:end, n.links.bus0.isin(region_buses) & ~n.links.bus1.isin(region_buses)].sum(axis=1) )
         p_slice['Imports/Exports'] = (ac + dc).div(1e3)
         if 'Imports/Exports' not in n.carriers.index:
             n.carriers.loc['Imports/Exports','color']='#7f7f7f'

     # 5) LOAD SERIES
     if regions:
         load_cols = [c for c in n.loads[n.loads.bus.isin(regions)].index if c in n.loads_t.p_set]
         load_series = n.loads_t.p_set[load_cols].sum(axis=1)
     else:
         load_series = n.loads_t.p_set.sum(axis=1)
     load_series = load_series.loc[start:end].div(1e3)

     # 6) VRE CURTAILMENT (GW) if requested
     if show_curtailment:
         vre = ['Solar','Wind', 'Rooftop Solar']
         mask_vre = gen_mask & n.generators.carrier.isin(vre)
         avail = (n.generators_t.p_max_pu.loc[start:end, mask_vre]
                  .multiply(n.generators.loc[mask_vre,'p_nom'], axis=1))
         disp  = n.generators_t.p.loc[start:end, mask_vre]
         curtail = (avail.sub(disp, fill_value=0)
                        .clip(lower=0)
                        .sum(axis=1)
                        .div(1e3))
     else:
         curtail = None

     # 7) PLOT
     title_tail = f" for {', '.join(regions)}" if regions else ''
     plot_title = f"Dispatch by Carrier: {start.date()} to {end.date()}{title_tail}"
     
     if interactive:
         # PLOTLY INTERACTIVE PLOT
         fig = go.Figure()
         
         fig.update_layout(
            plot_bgcolor='#F0FFFF',
            xaxis=dict(gridcolor='#DDDDDD'),
            yaxis=dict(gridcolor='#DDDDDD')        # Plot area background
         ) 

         # Prepare data for stacked area plot
         positive_data = p_slice.where(p_slice > 0).fillna(0)
         negative_data = p_slice.where(p_slice < 0).fillna(0)
         
         # Add positive generation as stacked area
         for i, col in enumerate(positive_data.columns):
             if positive_data[col].sum() > 0:
                 color = n.carriers.loc[col, 'color']
                 # Only add points where value > 0.001
                 mask = positive_data[col].abs() > 0.001
                 if mask.any():
                     fig.add_trace(go.Scatter(
                         x=positive_data.index[mask],
                         y=positive_data[col][mask],
                         mode='lines',
                         fill='tonexty' if i > 0 else 'tozeroy',
                         line=dict(width=0, color=color),
                         fillcolor=color,
                         name=col,
                         stackgroup='positive',
                         hovertemplate='<b>%{fullData.name}</b><br>Power: %{y:.3f} GW<extra></extra>',
                         showlegend=True
                     ))
         
         # Add negative generation (storage charging, exports)
         for col in negative_data.columns:
             if negative_data[col].sum() < 0:
                 color = n.carriers.loc[col, 'color']
                 # Only add points where value < -0.001
                 mask = negative_data[col].abs() > 0.001
                 if mask.any():
                     fig.add_trace(go.Scatter(
                         x=negative_data.index[mask],
                         y=negative_data[col][mask],
                         mode='lines',
                         fill='tonexty',
                         line=dict(width=0, color=color),
                         fillcolor=color,
                         name=col,
                         stackgroup='negative',
                         hovertemplate='<b>%{fullData.name}</b><br>Power: %{y:.2f} GW<extra></extra>',
                         showlegend=True
                     ))
         
         # Add demand line (always show)
         fig.add_trace(go.Scatter(
             x=load_series.index,
             y=load_series,
             mode='lines',
             line=dict(color='green', width=2),
             name='Demand',
             hovertemplate='<b>Demand</b><br>Power: %{y:.2f} GW<extra></extra>',
             showlegend=True
         ))
         
         # Add curtailment line if requested
         if show_curtailment and curtail is not None:
             fig.add_trace(go.Scatter(
                 x=curtail.index,
                 y=curtail,
                 mode='lines',
                 line=dict(color='black', width=2, dash='dash'),
                 name='Curtailment',
                 hovertemplate='<b>Curtailment</b><br>Power: %{y:.2f} GW<extra></extra>',
                 showlegend=True
                 ))
         
         # Update layout
         fig.update_layout(
             title=plot_title,
             xaxis_title='Time',
             yaxis_title='GW',
             hovermode='x unified',
             hoverlabel=dict(
                 bgcolor="white",
                 bordercolor="black",
                 font_size=12,
             ),
             legend=dict(
                 x=1.02,
                 y=1,
                 bgcolor='rgba(255,255,255,0.8)',
                 bordercolor='rgba(0,0,0,0.2)',
                 borderwidth=1
             ),
             width=800,
             height=550
         )
         
         # Add scenario annotations
         annotations = []
         if scenario_name:
             annotations.append(
                 dict(
                     x=1.02, y=-0.05,
                     xref='paper', yref='paper',
                     text=f"Scenario: {scenario_name}",
                     showarrow=False,
                     font=dict(size=10, color='gray'),
                     xanchor='center',
                     yanchor='top'
                 )
             )
         
         if annotations:
             fig.update_layout(annotations=annotations)
         
        #  fig.show()
         return fig
         
     else:
         # MATPLOTLIB STATIC PLOT 
         fig, ax = plt.subplots(figsize=(8.4, 6.5)) #12,6.5
         cols = p_slice.columns.map(lambda c: n.carriers.loc[c,'color'])
         p_slice.where(p_slice>0).plot.area(ax=ax,linewidth=0,color=cols)
         neg = p_slice.where(p_slice<0).dropna(how='all',axis=1)
         if not neg.empty:
             neg_cols=[n.carriers.loc[c,'color'] for c in neg.columns]
             neg.plot.area(ax=ax,linewidth=0,color=neg_cols)
         load_series.plot(ax=ax,color='g',linewidth=1.5,label='Demand')
         if show_curtailment and curtail is not None:
             curtail.plot(ax=ax,color='k',linestyle='--',linewidth=1.2,label='Curtailment')

         # limits & legend
         up = max(p_slice.where(p_slice>0).sum(axis=1).max(),
                  load_series.max(),
                  curtail.max() if curtail is not None else 0)
         dn = min(p_slice.where(p_slice<0).sum(axis=1).min(), load_series.min())
         ax.set_ylim(dn if not np.isclose(up,dn) else dn-0.1, up)
        #  fig.patch.set_facecolor('#F0FFFF') 
         ax.set_facecolor('#F0FFFF')
         h,l = ax.get_legend_handles_labels()
         seen={} ; fh,fl=[],[]
         for hh,ll in zip(h,l):
             if ll not in seen: fh.append(hh);fl.append(ll);seen[ll]=True
         ax.legend(fh,fl,loc=(1.02,0.67), fontsize=9)

         # scenario text
         if scenario_objective:
             ax.text(1.02,0.01,f"Objective:\n{scenario_objective}",transform=ax.transAxes,
                     fontsize=8,va='bottom',ha='left',bbox=dict(facecolor='white',alpha=0.7,edgecolor='none'))
         if scenario_name:
             ax.text(1.02,-0.05,f"Scenario: {scenario_name}",transform=ax.transAxes,
                     fontsize=9,color='gray',ha='center',va='top')

         ax.set_ylabel('GW')
         ax.set_title(plot_title)
         plt.tight_layout()
        #  plt.show()
         return fig
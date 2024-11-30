import base64
import io
from typing import Any, Callable, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
from jinja2 import Environment, Template

from legacy.ds_extras import DSExtra
from xds.utils.helpers import is_pivot
from xds.utils.io import io_buffer
from xds.utils.logger import ic


class View:
    def __init__(self, report_spec: str, ds: DSExtra):
        self.spec: Dict[str, Any] = io_buffer(report_spec)
        self.df: pd.DataFrame = ds.df_humanized
        self.jenv: Environment = Environment()
        sns.set_theme(style='darkgrid')

    def render(self, jtmpl: str) -> str:
        layout = 'layout'
        template: Template = self.jenv.from_string(str(io_buffer(jtmpl)))
        names = [i['name'] for i in self.spec[layout]]
        elements = {}
        items: List[Tuple[str, Callable[[Dict[str, Any]], Any]]] = [
            ('pivots', self._df_pivot),
            ('charts', self._df_chart),
            ('tables', self._df_table),
        ]
        for k, v in items:
            if self.spec.get(k):
                elements[k] = {
                    name: v(spc)
                    for name, spc in self.spec[k].items()
                    if name in names
                }

        to_style: Dict[str, pd.DataFrame] = {
            **elements.get('pivots', {}),
            **elements.get('tables', {}),
        }
        styled_data = {
            name: self.df_style(data).to_html()
            for name, data in to_style.items()
        }

        return template.render(
            header=self.spec['header'],
            footer=self.spec['footer'],
            styled_data=styled_data,
            charts=elements.get('charts', {}),
            layout=self.spec[layout],
        )

    def _df_pivot(self, spec: Dict[str, Any]) -> pd.DataFrame:
        return pd.pivot_table(self.df, **spec)

    def _df_xyz(self, cparams: Dict[str, Any]) -> Dict[str, Any]:
        return {
            k: cparams[k]
            for k in [
                'x',
                'y',
                'hue',
            ]
            if k in cparams
        }

    def _df_chart(self, spec: Dict[str, Any]) -> Optional[str]:
        px_defaults = {
            'width': 2000,
            'height': 1000,
            'template': 'plotly_white',
        }
        chart_type = spec['type']
        if chart_type not in [
            'sankey',
            'line',
            'bar',
            'heatmap',
            'gantt',
            'histogram',
        ]:
            return None

        """
        for fld in ["x", "y", "z"]:
            if fld in spec and isinstance(spec[fld], str):
                spec[fld] = spec[fld].split(",")
        """

        cparams: Dict[str, Any] = {
            'data': self.df.sort_values(by=spec['x']),
            'x': spec['x'],
            'y': spec['y'],
            'hue': spec.get('z'),
        }
        palette = 'Reds' if cparams['y'] == 'Errors' else 'Blues'
        if cparams['hue']:
            cparams['palette'] = sns.color_palette(palette=palette)
            hue = cparams['hue']
            cparams['hue_order'] = sorted(self.df[hue].unique())

        if chart_type == 'heatmap':
            h_pivot = self.df.pivot_table(
                index=spec['z'],
                columns=spec['x'],
                values=spec['y'],
                aggfunc='sum',
            )
            labels = np.array(h_pivot.values).reshape(  # type: ignore  # noqa: PGH003
                len(h_pivot.index), len(h_pivot.columns)
            )
            labels = np.round(labels).astype(int)
            cparams = {'df': h_pivot, 'labels': labels}

        elif chart_type == 'gantt':
            cparams = {
                'data': self.df.head(20),
                'y': spec['x'],
                'x_start': spec['y'],
                'x_end': spec['z'],
                'text': spec['show'],
            }
        elif chart_type == 'histogram':
            bins = pd.date_range(
                start='2023-01-01', end='2024-02-01', freq='1M'
            )
            self.df['Bin'] = pd.cut(self.df[spec['x']], bins=bins)
            cols = [spec['x'], spec['z']]
            result = self.df.groupby(cols, as_index=False)[spec['y']].sum()
            cparams = {'data': result}

        plt.figure(figsize=(50, 50))  # Increase figure size
        fig: Any = None
        if chart_type in ['line', 'histogram']:
            fig = px.line(
                cparams['data'],
                x=spec.get('x'),
                y=spec.get('y'),
                color=spec.get('z'),
                markers=True,
                line_dash=spec.get('z'),
            )
        elif chart_type == 'bar':
            fig = px.bar(
                cparams['data'],
                x=cparams.get('x'),
                y=cparams.get('y'),
                color=cparams.get('hue'),
                barmode='group',
            )
        elif chart_type == 'heatmap':
            fig = px.imshow(
                cparams['df'],
                text_auto=True,
                aspect='auto',
            )
        elif chart_type == 'gantt':
            fig = px.timeline(
                cparams['data'],
                x_start=cparams['x_start'],
                x_end=cparams['x_end'],
                y=cparams['y'],
                text=cparams['text'],
            )
        elif chart_type == 'sankey':
            fig = self._sankey(self.df)

        fig.update_layout(**px_defaults)
        fig.show()
        plt.tight_layout()

        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight', dpi=300)
        img.seek(0)
        plt.close()

        return base64.b64encode(img.getvalue()).decode()

    def _sankey(self, df, levels, value_col, title) -> None:
        for level in levels:
            if level not in df.columns:
                raise ValueError(f"Column '{level}' not found in DataFrame")

        if value_col not in df.columns:
            raise ValueError(
                f"Value column '{value_col}' not found in DataFrame"
            )

        agg_dfs = []
        for i in range(len(levels)):
            agg_df = df.groupby(levels[: i + 1])[value_col].sum().reset_index()
            agg_df = agg_df.sort_values(
                by=levels[i]
            )  # Sort alphabetically at each level
            agg_dfs.append(agg_df)

        labels = []
        for i, agg_df in enumerate(agg_dfs):
            labels.extend(agg_df[levels[i]].unique().tolist())
        labels = sorted(dict.fromkeys(labels))

        label_indices = {label: i for i, label in enumerate(labels)}

        source = []
        target = []
        value = []

        for i in range(len(agg_dfs) - 1, 0, -1):
            for _, row in agg_dfs[i].iterrows():
                source.append(label_indices[row[levels[i - 1]]])
                target.append(label_indices[row[levels[i]]])
                value.append(row[value_col])

        def _hover_nodes() -> List:
            node_hover_text = []
            incoming_flows = {i: [] for i in range(len(labels))}
            outgoing_flows = {i: [] for i in range(len(labels))}

            for s, t, v in zip(source, target, value):
                outgoing_flows[s].append((labels[t], v))
                incoming_flows[t].append((labels[s], v))

            for i in range(len(labels)):
                in_text = '<br>'.join(
                    [f'From {s}: {v}' for s, v in incoming_flows[i]]
                )
                out_text = '<br>'.join(
                    [f'To {t}: {v}' for t, v in outgoing_flows[i]]
                )
                hover_text = f'{labels[i]}<br><br>Incoming:<br>{in_text}<br><br>Outgoing:<br>{out_text}'
                node_hover_text.append(hover_text)
            return node_hover_text

        def generate_colors(num_colors):
            colors = plt.cm.get_cmap('Set3', num_colors)
            return [
                'rgba({}, {}, {}, 0.8)'.format(
                    int(r * 255), int(g * 255), int(b * 255)
                )
                for r, g, b, _ in colors(np.linspace(0, 1, num_colors))
            ]

        # node_colors = generate_colors(len(labels))
        link_colors = generate_colors(len(source))

        fig = go.Figure(
            data=[
                go.Sankey(
                    node={
                        'pad': 25,
                        'thickness': 30,
                        'line': {'color': 'gray', 'width': 1.5},
                        'label': labels,
                        # "color": node_colors,
                    },
                    link={
                        'source': source,
                        'target': target,
                        'value': value,
                        'label': value,
                        'color': link_colors,
                        'hovertemplate': '%{source.label} → %{target.label}<br>Total: %{value}<extra></extra>',
                    },
                )
            ]
        )
        # node_hovers = _hover_nodes()
        # fig.update_traces(node={"hovertemplate": node_hovers})

        fig.update_layout(
            title_text=title,
            font_size=12,
        )
        fig.show()
        return fig

    def _annot(fig):
        value = []
        for i in range(len(value)):
            x_target = 0.9  # Adjust based on your layout
            y_position = (i + 0.5) / len(value)  # Distribute along the y-axis
            fig.add_annotation(
                x=x_target,  # X position for the annotation
                y=y_position,  # Y position for the annotation
                text=str(value[i]),  # Text to display
                showarrow=True,
                arrowhead=2,
                ax=0,
                ay=-40,  # Adjust this value to position the text above the link
            )

    def _df_table(self, spec: Dict[str, Any]) -> pd.DataFrame:
        return (
            self.df[spec['columns']]
            .sort_values(by=spec['columns'])
            .head(spec.get('rows', 10))
        )

    def df_style(
        self, df: pd.DataFrame, is_table: bool = False
    ) -> pd.io.formats.style.Styler:
        def _color_negative_red(val: Any) -> str:
            return f"color: {'red' if val < 0 else 'black'}"

        gradient = sns.light_palette('seagreen', as_cmap=True)
        style_kwargs = {
            'font-family': 'arial, sans-serif',
            'background-color': 'white',
            'font-size': 'medium',
            'text-align': 'right',
            'width': 'auto',
            'padding': '0px 20px 0px 0px',
        }
        table_styles: List[Dict[str, Any]] = [
            {
                'selector': 'td:hover',
                'props': [('background-color', '#EFEFE0')],
            },
            {
                'selector': '.index_name',
                'props': [
                    ('font-style', 'italic'),
                    ('color', 'black'),
                    ('font-size', '110%'),
                    ('font-weight', 'bold'),
                    ('padding', '0.5em'),
                    ('text-align', 'left'),
                ],
            },
            {
                'selector': 'th:not(.index_name)',
                'props': [
                    ('font-style', 'italic'),
                    ('color', 'black'),
                    ('font-size', '110%'),
                    ('font-weight', 'bold'),
                    ('padding', '0.5em'),
                    ('text-align', 'right'),
                ],
            },
            {'selector': 'td', 'props': [('padding', '0.3em')]},
            {'selector': 'tr', 'props': [('padding', '0.5em')]},
            {
                'selector': '',
                'props': [
                    ('padding', '0.5em'),
                    ('border-collapse', 'collapse'),
                ],
            },
        ]

        styled = (
            df.style.set_properties(**style_kwargs)  # type: ignore  # noqa: PGH003
            .format(precision=0, thousands=',', na_rep='')
            .background_gradient(cmap=gradient, axis=0)
            .highlight_null(color='transparent')  # type: ignore  # noqa: PGH003
        )
        styled.set_table_attributes('border="1" border-color="grey"')
        styled.set_table_styles(table_styles)  # type: ignore  # noqa: PGH003

        if not is_pivot(df) and 'key' not in df.columns:
            styled.hide(axis='index')

        num_columns = df.select_dtypes(include=['number']).columns
        styled.map(_color_negative_red, subset=num_columns)

        return styled

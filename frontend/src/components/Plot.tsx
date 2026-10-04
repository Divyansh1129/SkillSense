import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";
import { useUi } from "./ui";

const PlotlyPlot = createPlotlyComponent(Plotly);

// Okabe-Ito colour-blind-safe palette
export const PAL = { blue: "#0072B2", orange: "#E69F00", green: "#009E73", pink: "#CC79A7", vermillion: "#D55E00", sky: "#56B4E9" };

export default function Plot({ data, layout = {}, height = 320, label }: { data: any[]; layout?: any; height?: number; label: string }) {
  const { hc } = useUi();
  const fg = hc ? "#ffffff" : "#0f172a";
  const base = {
    autosize: true, height, margin: { l: 56, r: 16, t: 18, b: 100 }, paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: fg, size: 12 }, legend: { orientation: "h", x: 0.5, xanchor: "center", y: -0.38, yanchor: "top", font: { size: 11 }, tracegroupgap: 8 },
    xaxis: { gridcolor: hc ? "#666" : "#e2e8f0", tickmode: "auto", nticks: 8, tickangle: -25, automargin: true },
    yaxis: { gridcolor: hc ? "#666" : "#e2e8f0", automargin: true },
  };
  const plotLayout = {
    ...base, ...layout, margin: { ...base.margin, ...layout.margin },
    font: { ...base.font, ...layout.font }, legend: { ...base.legend, ...layout.legend },
    xaxis: { ...base.xaxis, ...layout.xaxis }, yaxis: { ...base.yaxis, ...layout.yaxis },
  };
  return (
    <div role="img" aria-label={label} className="plot-frame">
      <PlotlyPlot
        data={data}
        layout={plotLayout}
        config={{ displayModeBar: false, responsive: true }}
        useResizeHandler
        style={{ width: "100%", height }}
      />
    </div>
  );
}

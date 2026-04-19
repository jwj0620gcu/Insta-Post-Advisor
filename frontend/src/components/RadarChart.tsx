import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { RadarChart as EChartsRadar } from "echarts/charts";
import {
  TooltipComponent,
  RadarComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([EChartsRadar, TooltipComponent, RadarComponent, CanvasRenderer]);

interface Props {
  data: Record<string, number>;
}

const DIMENSION_LABELS: Record<string, string> = {
  content: "콘텐츠 품질",
  visual: "시각 완성도",
  growth: "성장 전략",
  user_reaction: "오디언스 반응",
  overall: "종합 점수",
};

export default function RadarChart({ data }: Props) {
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);

  const keys = Object.keys(DIMENSION_LABELS);
  const indicators = keys.map((key) => ({
    name: DIMENSION_LABELS[key],
    max: 100,
  }));
  const values = keys.map((key) => data[key] ?? 50);

  useEffect(() => {
    if (!chartRef.current) return;
    if (!instanceRef.current) {
      instanceRef.current = echarts.init(chartRef.current);
    }
    instanceRef.current.setOption({
      animationDuration: 1200,
      radar: {
        indicator: indicators,
        shape: "polygon" as const,
        splitNumber: 4,
        radius: "65%",
        axisName: { color: "#241628", fontSize: 12, fontWeight: 600 },
        splitLine: { lineStyle: { color: "rgba(214,41,118,0.14)" } },
        splitArea: { show: false },
        axisLine: { lineStyle: { color: "rgba(150,47,191,0.22)" } },
      },
      series: [
        {
          type: "radar",
          data: [
            {
              value: values,
              areaStyle: { color: "rgba(214,41,118,0.18)" },
              lineStyle: { color: "#d62976", width: 2 },
              itemStyle: { color: "#962fbf", borderColor: "#fff", borderWidth: 2 },
              symbol: "circle",
              symbolSize: 6,
            },
          ],
        },
      ],
      tooltip: {
        trigger: "item",
        backgroundColor: "#ffffff",
        borderColor: "rgba(214,41,118,0.18)",
        textStyle: { color: "#241628", fontSize: 13 },
      },
    });
  }, [data]);

  useEffect(() => {
    const handleResize = () => instanceRef.current?.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      instanceRef.current?.dispose();
    };
  }, []);

  return <div ref={chartRef} style={{ height: 280, width: "100%" }} />;
}

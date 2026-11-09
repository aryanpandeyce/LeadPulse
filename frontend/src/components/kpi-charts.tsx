"use client";

import React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface MonthlyTrendPoint {
  month: string;
  total_leads: number;
  converted_leads: number;
  lost_leads: number;
  revenue: number;
  conversion_rate_pct: number;
}

export interface LeadsBySourceItem {
  source: string;
  total_leads: number;
  converted_leads: number;
  revenue: number;
}

export default function KpiCharts({
  monthlyTrend,
  leadsBySource,
}: {
  monthlyTrend: MonthlyTrendPoint[];
  leadsBySource: LeadsBySourceItem[];
}) {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {/* Month-over-Month Trend Chart */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
        <h3 className="text-sm font-bold text-white">
          Month-over-Month Lead Volume & Conversions
        </h3>
        <p className="text-xs text-slate-400">
          Aggregated from 200,000+ leads via <code>monthly_kpis</code> Materialized View + Redis Cache-Aside.
        </p>
        <div className="mt-4 h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={monthlyTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="month" stroke="#94a3b8" fontSize={11} />
              <YAxis stroke="#94a3b8" fontSize={11} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#334155",
                  fontSize: "12px",
                }}
              />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
              <Line
                type="monotone"
                dataKey="total_leads"
                name="Total Leads"
                stroke="#3b82f6"
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="converted_leads"
                name="Converted"
                stroke="#10b981"
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="lost_leads"
                name="Lost"
                stroke="#ef4444"
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Leads & Revenue by Source */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
        <h3 className="text-sm font-bold text-white">
          Leads & Conversions by Acquisition Channel
        </h3>
        <p className="text-xs text-slate-400">
          Comparing website, referral, LinkedIn, cold outreach, and events.
        </p>
        <div className="mt-4 h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={leadsBySource}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="source" stroke="#94a3b8" fontSize={11} />
              <YAxis stroke="#94a3b8" fontSize={11} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#334155",
                  fontSize: "12px",
                }}
              />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
              <Bar dataKey="total_leads" name="Total Leads" fill="#3b82f6" />
              <Bar
                dataKey="converted_leads"
                name="Converted Leads"
                fill="#10b981"
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

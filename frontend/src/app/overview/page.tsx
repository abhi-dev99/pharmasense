"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, AlertTriangle, PackageOpen, TrendingUp } from "lucide-react";

export default function OverviewPage() {
  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Top Metrics Row */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Critical Drug Shortages</CardTitle>
            <AlertTriangle className="h-4 w-4 text-risk-critical" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-risk-critical">12</div>
            <p className="text-xs text-muted-foreground">Across 4 districts (next 14 days)</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Outbreak Signals</CardTitle>
            <Activity className="h-4 w-4 text-risk-high" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">3</div>
            <p className="text-xs text-muted-foreground">+1 since yesterday</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending Purchase Orders</CardTitle>
            <PackageOpen className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">24</div>
            <p className="text-xs text-muted-foreground">18 AI-drafted, 6 manual</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">System Health</CardTitle>
            <TrendingUp className="h-4 w-4 text-risk-low" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">99.9%</div>
            <p className="text-xs text-muted-foreground">All data pipelines synced</p>
          </CardContent>
        </Card>
      </div>

      {/* Middle Section */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        <Card className="col-span-4">
          <CardHeader>
            <CardTitle>Demand Forecast vs Actual Stock</CardTitle>
            <CardDescription>Predicted consumption across critical SKUs</CardDescription>
          </CardHeader>
          <CardContent className="h-[300px] flex items-center justify-center border-t border-dashed m-4 rounded-xl bg-muted/20">
            {/* Chart will go here */}
            <span className="text-muted-foreground text-sm">Interactive Chart Component Loading...</span>
          </CardContent>
        </Card>

        <Card className="col-span-3">
          <CardHeader>
            <CardTitle>Immediate Action Required</CardTitle>
            <CardDescription>AI has drafted these orders to prevent stockouts</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[
                { hospital: "Pune General", drug: "Paracetamol IV", risk: "critical", days: 3 },
                { hospital: "Baramati PHC", drug: "Doxycycline", risk: "high", days: 5 },
                { hospital: "Shirur Rural", drug: "ORS Sachets", risk: "moderate", days: 8 },
              ].map((alert, i) => (
                <div key={i} className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 transition-colors">
                  <div className="space-y-1">
                    <p className="text-sm font-medium leading-none">{alert.drug}</p>
                    <p className="text-xs text-muted-foreground">{alert.hospital} • {alert.days} days cover left</p>
                  </div>
                  <Badge variant={alert.risk === "critical" ? "destructive" : "secondary"}>
                    Approve PO
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

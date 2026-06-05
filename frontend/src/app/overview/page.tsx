"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, AlertTriangle, PackageOpen, TrendingUp } from "lucide-react";
import { RiskPanel } from "@/components/dashboard/RiskPanel";
import { OrderTable } from "@/components/dashboard/OrderTable";
import { AIBrief } from "@/components/dashboard/AIBrief";

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

      {/* Dynamic ML Integration Section */}
      <div className="grid gap-6 md:grid-cols-3">
        <div className="col-span-2 space-y-6">
          <RiskPanel districtId="dist_pune_001" />
          <OrderTable hospitalId="hosp_pune_general" />
        </div>
        <div className="col-span-1">
          <AIBrief hospitalId="hosp_pune_general" />
        </div>
      </div>
    </div>
  );
}

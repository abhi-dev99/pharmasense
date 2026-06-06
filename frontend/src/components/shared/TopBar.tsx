"use client";

import { usePathname } from "next/navigation";
import { Bell } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import useSWR from "swr";

const fetcher = (url: string) => fetch(url).then(r => r.json());

const HOSPITAL_ID = "a4174db7-8319-4494-9585-c4777f408ed9";

export function TopBar() {
  const pathname = usePathname();
  const { data } = useSWR(`/api/v1/hospitals/${HOSPITAL_ID}`, fetcher);

  let title = "Overview";
  if (pathname.includes("inventory")) title = "Inventory Manager";
  else if (pathname.includes("orders")) title = "Purchase Orders";
  else if (pathname.includes("intelligence")) title = "Outbreak Intelligence";
  else if (pathname.includes("simulate")) title = "Simulation Engine";
  else if (pathname.includes("settings")) title = "Settings";

  const hospitalName = data?.name ?? "Loading…";
  const districtName = data?.district_name ?? "…";

  return (
    <div className="h-16 border-b border-border bg-white flex items-center justify-between px-8 sticky top-0 z-10 w-full">
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-risk-low animate-pulse" />
          <span className="text-sm text-muted-foreground">Live · {new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
        
        <div className="flex items-center gap-3">
          <Badge variant="secondary" className="font-medium">{districtName}</Badge>
          <button className="relative p-2 text-muted-foreground hover:text-foreground transition-colors">
            <Bell className="w-5 h-5" />
            <span className="absolute top-1 right-1 w-2 h-2 bg-risk-high rounded-full" />
          </button>
        </div>
      </div>
    </div>
  );
}

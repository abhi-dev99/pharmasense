"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import useSWR from "swr";
import {
  LayoutDashboard,
  Package,
  ClipboardList,
  BrainCircuit,
  FlaskConical,
  Settings,
  LogOut,
} from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

const fetcher = (url: string) => fetch(url).then(r => r.json());
const HOSPITAL_ID = "a4174db7-8319-4494-9585-c4777f408ed9";

const navItems = [
  { name: "Overview",         href: "/overview",      icon: LayoutDashboard },
  { name: "Inventory",        href: "/inventory",     icon: Package },
  { name: "Purchase Orders",  href: "/orders",        icon: ClipboardList },
  { name: "Intelligence",     href: "/intelligence",  icon: BrainCircuit },
  { name: "Simulate",         href: "/simulate",      icon: FlaskConical },
];

export function Sidebar() {
  const pathname = usePathname();
  const { data: hospData } = useSWR(`/api/v1/hospitals/${HOSPITAL_ID}`, fetcher);

  const hospitalName = hospData?.name ?? "Loading…";
  const districtName = hospData?.district_name ?? "";
  const initials = hospitalName.split(" ").slice(0, 2).map((w: string) => w[0]).join("").toUpperCase();

  return (
    <div className="flex flex-col w-60 h-screen fixed left-0 top-0 border-r border-gray-200 bg-white">
      <div className="p-6 flex items-center">
        <span className="font-bold text-2xl tracking-tighter text-[#404040] select-none" style={{ letterSpacing: "-0.05em" }}>
          pharmasense
        </span>
      </div>

      <div className="flex-1 px-4 py-2 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                isActive
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
              )}
            >
              <Icon className="w-4 h-4" />
              {item.name}
            </Link>
          );
        })}
      </div>

      <div className="p-4 border-t border-border space-y-2">
        <Link
          href="/settings"
          className="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
        >
          <Settings className="w-4 h-4" />
          Settings
        </Link>
        <button className="flex w-full items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors">
          <LogOut className="w-4 h-4" />
          Sign Out
        </button>

        <div className="mt-4 flex items-center gap-3 px-3 py-2">
          <Avatar className="w-8 h-8 rounded-md">
            <AvatarFallback className="rounded-md bg-[#111111] text-white text-xs">{initials || "RG"}</AvatarFallback>
          </Avatar>
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-medium leading-none truncate">{hospitalName}</span>
            <span className="text-xs text-muted-foreground mt-1 truncate">{districtName}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

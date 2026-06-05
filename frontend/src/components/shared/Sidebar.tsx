"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
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

const navItems = [
  { name: "Overview", href: "/overview", icon: LayoutDashboard },
  { name: "Inventory", href: "/inventory", icon: Package },
  { name: "Purchase Orders", href: "/orders", icon: ClipboardList },
  { name: "Intelligence", href: "/intelligence", icon: BrainCircuit },
  { name: "Simulate", href: "/simulate", icon: FlaskConical },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex flex-col w-60 h-screen fixed left-0 top-0 border-r border-border bg-sidebar">
      <div className="p-6 flex items-center gap-3">
        {/* Logo Placeholder */}
        <div className="w-8 h-8 rounded bg-primary flex items-center justify-center">
          <div className="w-3 h-3 rounded-full bg-white" />
        </div>
        <span className="font-semibold text-lg tracking-tight">Pharmasense</span>
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
            <AvatarFallback className="rounded-md bg-accent text-white text-xs">PH</AvatarFallback>
          </Avatar>
          <div className="flex flex-col">
            <span className="text-sm font-medium leading-none">Pharmacist</span>
            <span className="text-xs text-muted-foreground mt-1">Pune General</span>
          </div>
        </div>
      </div>
    </div>
  );
}

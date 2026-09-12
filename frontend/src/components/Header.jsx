import React, { useState, useEffect } from 'react';
import { ShieldCheck, User, Cpu, AlertTriangle, ChevronDown, Check } from 'lucide-react';
import { getEgressMetrics, getSovereigntyStatus } from '../services/api';

export default function Header({
  workspaces = [],
  activeWorkspaceId = 'default-workspace',
  onWorkspaceChange,
  userRole = 'maintenance_engineer',
  onRoleChange
}) {
  const [timeStr, setTimeStr] = useState('');
  const [metrics, setMetrics] = useState({ blocked_attempts_count: 0, approved_connections_count: 0 });
  const [isAirGapped, setIsAirGapped] = useState(true);
  const [backendOnline, setBackendOnline] = useState(true);
  const [showRoleMenu, setShowRoleMenu] = useState(false);
  const [showWorkspaceMenu, setShowWorkspaceMenu] = useState(false);

  const availableRoles = [
    { id: 'operator', name: 'Plant Operator', clearance: 'Level 1: Read-Only' },
    { id: 'technician', name: 'Field Technician', clearance: 'Level 2: Diagnostics' },
    { id: 'maintenance_engineer', name: 'Maintenance Engineer', clearance: 'Level 3: Full Analysis & SecBox' },
    { id: 'supervisor', name: 'Shift Supervisor', clearance: 'Level 4: Approval & Mitigation' },
    { id: 'plant_manager', name: 'Plant Manager', clearance: 'Level 5: Executive Sign-off' },
  ];

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const time = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      const date = now.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
      setTimeStr(`${time} • ${date}`);
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    let mounted = true;
    const fetchSovereigntyData = async () => {
      try {
        const [m, s] = await Promise.all([getEgressMetrics(), getSovereigntyStatus()]);
        if (mounted) {
          setBackendOnline(true);
          if (m) setMetrics(m);
          if (s) setIsAirGapped(s.is_air_gapped !== false);
        }
      } catch (err) {
        if (mounted) {
          setBackendOnline(false);
        }
      }
    };

    fetchSovereigntyData();
    const metricInterval = setInterval(fetchSovereigntyData, 5000);
    return () => {
      mounted = false;
      clearInterval(metricInterval);
    };
  }, []);

  const currentRoleObj = availableRoles.find(r => r.id === userRole) || availableRoles[2];
  const currentWorkspaceObj = workspaces.find(w => w.id === activeWorkspaceId) || { name: 'CDU Unit-02 Maintenance' };

  return (
    <header className="h-16 border-b border-[#2e2a26] bg-[#171513] px-6 flex items-center justify-between z-40 sticky top-0 shadow-md">
      {/* Brand Logo & Workspace Switcher */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#24211d] border border-[#d9825b]/50 flex items-center justify-center text-[#d9825b] font-bold text-lg shadow-sm">
            <span className="font-mono tracking-tighter">❖</span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-display font-bold text-base tracking-wider text-[#f5f2ed]">CLORA</span>
              <span className="text-[#6d675e] text-xs font-mono">—</span>
              <span className="text-[#a09a90] text-xs font-semibold uppercase tracking-widest hidden md:inline">
                Sovereign Industrial AI Workbench
              </span>
            </div>
          </div>
        </div>

        {/* Workspace Dropdown */}
        <div className="relative hidden lg:block">
          <button
            onClick={() => {
              setShowWorkspaceMenu(!showWorkspaceMenu);
              setShowRoleMenu(false);
            }}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#1f1c19] border border-[#3b3630] hover:border-[#d9825b] text-xs text-[#f5f2ed] transition-all"
          >
            <span className="text-[#6d675e] font-mono text-[10px]">WORKSPACE:</span>
            <span className="font-semibold text-[#f5f2ed] max-w-[180px] truncate">{currentWorkspaceObj.name}</span>
            <ChevronDown size={13} className="text-[#a09a90]" />
          </button>

          {showWorkspaceMenu && (
            <div className="absolute top-full left-0 mt-1.5 w-64 bg-[#1b1917] border border-[#3b3630] rounded-xl shadow-2xl p-1.5 z-50 animate-in fade-in duration-150">
              <div className="px-2.5 py-1 text-[10px] font-mono text-[#6d675e] uppercase">Select Active Workspace</div>
              <div className="space-y-0.5">
                {(workspaces.length > 0 ? workspaces : [{ id: 'default-workspace', name: 'CDU Unit-02 Maintenance' }]).map((ws) => (
                  <button
                    key={ws.id}
                    onClick={() => {
                      if (onWorkspaceChange) onWorkspaceChange(ws.id);
                      setShowWorkspaceMenu(false);
                    }}
                    className={`w-full text-left px-2.5 py-2 rounded-lg text-xs flex items-center justify-between transition-colors ${
                      ws.id === activeWorkspaceId
                        ? 'bg-[#291f19] text-[#d9825b] font-bold'
                        : 'text-[#a09a90] hover:text-[#f5f2ed] hover:bg-[#25221e]'
                    }`}
                  >
                    <span className="truncate">{ws.name}</span>
                    {ws.id === activeWorkspaceId && <Check size={13} className="text-[#d9825b]" />}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Center/Right: Target Air-Gapped Mode Widget & Role Selector */}
      <div className="flex items-center gap-4">
        <div className="flex items-center bg-[#1c1a17] border border-[#2e2b26] rounded-xl px-4 py-1.5 shadow-inner">
          {/* Status Indicator */}
          <div className="flex items-center gap-2.5 pr-4 border-r border-[#2e2a25]">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                !backendOnline
                  ? 'bg-[#ef4444] animate-ping shadow-[0_0_8px_#ef4444]'
                  : isAirGapped
                  ? 'bg-[#10b981] animate-pulse-glow shadow-[0_0_8px_#10b981]'
                  : 'bg-[#f59e0b] animate-pulse shadow-[0_0_8px_#f59e0b]'
              }`}
            />
            <div className="flex flex-col">
              <span
                className={`font-semibold text-xs tracking-wide ${
                  !backendOnline
                    ? 'text-[#ef4444]'
                    : isAirGapped
                    ? 'text-[#10b981]'
                    : 'text-[#f59e0b]'
                }`}
              >
                {!backendOnline ? 'BACKEND OFFLINE' : isAirGapped ? 'AIR-GAPPED SOVEREIGN' : 'AIR-GAP ALERT'}
              </span>
              <span className="text-[#6d675e] text-[10px]">
                {!backendOnline ? 'Disconnected (127.0.0.1:8000)' : isAirGapped ? 'Zero external egress' : 'Unapproved egress detected'}
              </span>
            </div>
          </div>

          {/* Blocked Attempts */}
          <div className="flex flex-col px-4 border-r border-[#2e2a25] hidden sm:flex">
            <span className="text-[#6d675e] text-[10px]">Blocked Attempts</span>
            <span className="text-[#f5f2ed] font-mono font-bold text-xs">
              {metrics.blocked_attempts_count ?? 0}
            </span>
          </div>

          {/* Approved Local Requests */}
          <div className="flex flex-col px-4 border-r border-[#2e2a25] hidden md:flex">
            <span className="text-[#6d675e] text-[10px]">Local Approved</span>
            <span className="text-[#f5f2ed] font-mono font-bold text-xs">
              {metrics.approved_connections_count ?? 0}
            </span>
          </div>

          {/* Live Timestamp */}
          <div className="pl-4 text-[#a09a90] font-mono text-xs font-medium hidden sm:block">
            {timeStr}
          </div>
        </div>

        {/* Dynamic User Role Switcher Dropdown */}
        <div className="relative">
          <button
            onClick={() => {
              setShowRoleMenu(!showRoleMenu);
              setShowWorkspaceMenu(false);
            }}
            className="flex items-center gap-2.5 pl-2 py-1 rounded-xl hover:bg-[#221e1b] transition-colors border-l border-[#2e2a25]"
          >
            <div className="w-8 h-8 rounded-full bg-[#26231f] border border-[#3b3630] flex items-center justify-center text-[#d9825b]">
              <User size={15} />
            </div>
            <div className="hidden md:flex flex-col text-left pr-1">
              <span className="text-xs font-semibold text-[#f5f2ed] flex items-center gap-1">
                <span>{currentRoleObj.name}</span>
                <ChevronDown size={11} className="text-[#6d675e]" />
              </span>
              <span className="text-[10px] text-[#6e8c6e] font-medium">{currentRoleObj.clearance}</span>
            </div>
          </button>

          {showRoleMenu && (
            <div className="absolute top-full right-0 mt-1.5 w-72 bg-[#1b1917] border border-[#3b3630] rounded-xl shadow-2xl p-1.5 z-50 animate-in fade-in duration-150">
              <div className="px-3 py-1.5 text-[10px] font-mono text-[#6d675e] uppercase border-b border-[#2a2622]">
                Switch RBAC Role Simulation
              </div>
              <div className="space-y-1 mt-1">
                {availableRoles.map((role) => (
                  <button
                    key={role.id}
                    onClick={() => {
                      if (onRoleChange) onRoleChange(role.id);
                      setShowRoleMenu(false);
                    }}
                    className={`w-full text-left p-2 rounded-lg text-xs flex items-center justify-between transition-colors ${
                      role.id === userRole
                        ? 'bg-[#291f19] border border-[#d9825b]/50 text-[#f5f2ed]'
                        : 'text-[#a09a90] hover:text-[#f5f2ed] hover:bg-[#24211d]'
                    }`}
                  >
                    <div>
                      <div className="font-semibold">{role.name}</div>
                      <div className="text-[10px] text-[#6d675e] font-mono">{role.clearance}</div>
                    </div>
                    {role.id === userRole && <Check size={14} className="text-[#d9825b]" />}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

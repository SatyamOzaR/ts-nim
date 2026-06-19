"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  Panel,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { BACKEND_URL, apiHeaders } from "../lib/api";

interface GraphNode {
  id: string;
  label: string;
  company: string;
  role: string;
  is_member: boolean;
  strength: number;
}

interface GraphEdge {
  source: string;
  target: string;
  strength: number;
  source_member: string;
  interaction_count: number;
  sources: string[];
}

interface ScoreDetails {
  name: string;
  company: string;
  role: string;
  overall: number;
  recency: number;
  seniority: number;
  interaction_frequency: number;
  shared_connections: number;
  source_diversity: boolean;
  interaction_count: number;
  last_touch: string | null;
  known_by: string[];
}

function PersonNode({ data }: { data: { label: string; company: string; role: string; isMember: boolean; strength: number } }) {
  return (
    <div
      className={`rounded-lg border px-3 py-2 text-center shadow-lg ${
        data.isMember
          ? "border-indigo-500 bg-indigo-950 text-indigo-100"
          : "border-zinc-600 bg-zinc-900 text-zinc-200"
      }`}
      style={{
        minWidth: 100,
        fontSize: 11,
      }}
    >
      <Handle type="target" position={Position.Left} className="!bg-zinc-500 !w-1.5 !h-1.5" />
      <div className="font-semibold text-xs">{data.label}</div>
      <div className="text-[10px] text-zinc-400 mt-0.5">
        {data.role || "N/A"}
      </div>
      <div className="text-[10px] text-zinc-500">{data.company}</div>
      {data.isMember && (
        <div className="mt-1 rounded bg-indigo-500/30 px-1 py-0.5 text-[9px] font-bold text-indigo-300">
          TEAM
        </div>
      )}
      <Handle type="source" position={Position.Right} className="!bg-zinc-500 !w-1.5 !h-1.5" />
    </div>
  );
}

const nodeTypes = { person: PersonNode };

function buildLayout(graphNodes: GraphNode[]): Node[] {
  const companies = new Map<string, GraphNode[]>();
  for (const n of graphNodes) {
    const group = companies.get(n.company) || [];
    group.push(n);
    companies.set(n.company, group);
  }

  const nodes: Node[] = [];
  let colIndex = 0;

  // Put TSI members on the left
  const members = graphNodes.filter((n) => n.is_member);
  members.forEach((m, i) => {
    nodes.push({
      id: m.id,
      type: "person",
      position: { x: 0, y: i * 100 },
      data: {
        label: m.label,
        company: m.company || "",
        role: m.role || "",
        isMember: true,
        strength: m.strength,
      },
    });
  });

  colIndex = 1;
  for (const [, group] of companies) {
    const contacts = group.filter((n) => !n.is_member);
    if (contacts.length === 0) continue;
    contacts.forEach((c, i) => {
      if (nodes.find((n) => n.id === c.id)) return;
      nodes.push({
        id: c.id,
        type: "person",
        position: { x: 250 * colIndex, y: i * 90 },
        data: {
          label: c.label,
          company: c.company || "",
          role: c.role || "",
          isMember: false,
          strength: c.strength,
        },
      });
    });
    colIndex++;
  }

  return nodes;
}

function buildEdges(graphEdges: GraphEdge[]): Edge[] {
  return graphEdges.map((e, i) => ({
    id: `e-${i}`,
    source: e.source,
    target: e.target,
    label: e.strength > 0 ? e.strength.toFixed(2) : undefined,
    style: {
      stroke: "#6366f1",
      strokeWidth: Math.max(1, e.strength * 4),
      opacity: 0.6,
    },
    labelStyle: { fontSize: 9, fill: "#a1a1aa" },
  }));
}

export function GraphViewer() {
  const [graphData, setGraphData] = useState<{
    nodes: GraphNode[];
    edges: GraphEdge[];
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterCompany, setFilterCompany] = useState("");
  const [filterRole, setFilterRole] = useState("");
  const [selected, setSelected] = useState<ScoreDetails | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/graph/all`, { headers: apiHeaders() })
      .then(async (r) => {
        const data = await r.json();
        if (!r.ok) {
          const msg =
            typeof data?.detail === "string"
              ? data.detail
              : `HTTP ${r.status}`;
          throw new Error(msg);
        }
        return data;
      })
      .then((data) => {
        setGraphData(data);
        setLoading(false);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });
  }, []);

  const filteredData = useMemo(() => {
    if (!graphData) return null;
    let filteredNodes = graphData.nodes;
    if (filterCompany) {
      filteredNodes = filteredNodes.filter(
        (n) =>
          n.is_member ||
          n.company?.toLowerCase().includes(filterCompany.toLowerCase())
      );
    }
    if (filterRole) {
      filteredNodes = filteredNodes.filter(
        (n) =>
          n.is_member ||
          n.role?.toLowerCase().includes(filterRole.toLowerCase())
      );
    }
    const ids = new Set(filteredNodes.map((n) => n.id));
    const filteredEdges = graphData.edges.filter(
      (e) => ids.has(e.source) && ids.has(e.target)
    );
    return { nodes: filteredNodes, edges: filteredEdges };
  }, [graphData, filterCompany, filterRole]);

  useEffect(() => {
    if (!filteredData) return;
    setNodes(buildLayout(filteredData.nodes));
    setEdges(buildEdges(filteredData.edges));
  }, [filteredData, setNodes, setEdges]);

  const onNodeClick = useCallback(
    async (_: React.MouseEvent, node: Node) => {
      try {
        const resp = await fetch(
          `${BACKEND_URL}/api/graph/score?person_id=${encodeURIComponent(node.id)}`,
          { headers: apiHeaders() }
        );
        if (resp.ok) {
          setSelected(await resp.json());
        }
      } catch {
        // ignore
      }
    },
    []
  );

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-zinc-500">Loading graph...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-red-400">
          Failed to load graph: {error}. Is the backend running?
        </p>
      </div>
    );
  }

  return (
    <div className="relative h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#27272a" gap={20} />
        <Controls className="!bg-zinc-800 !border-zinc-700 !rounded-lg [&>button]:!bg-zinc-800 [&>button]:!border-zinc-700 [&>button]:!text-zinc-400 [&>button:hover]:!bg-zinc-700" />
        <MiniMap
          nodeColor={(n) =>
            n.data?.isMember ? "#6366f1" : "#3f3f46"
          }
          maskColor="rgba(0,0,0,0.7)"
          className="!bg-zinc-900 !border-zinc-700 !rounded-lg"
        />

        <Panel position="top-left" className="flex gap-2">
          <input
            type="text"
            value={filterCompany}
            onChange={(e) => setFilterCompany(e.target.value)}
            placeholder="Filter by company..."
            className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500"
          />
          <input
            type="text"
            value={filterRole}
            onChange={(e) => setFilterRole(e.target.value)}
            placeholder="Filter by role..."
            className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-indigo-500"
          />
        </Panel>
      </ReactFlow>

      {/* Sidebar */}
      {selected && (
        <div className="absolute right-0 top-0 h-full w-72 overflow-y-auto border-l border-zinc-700 bg-zinc-900 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold">{selected.name}</h3>
            <button
              onClick={() => setSelected(null)}
              className="text-zinc-500 hover:text-zinc-300"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
              </svg>
            </button>
          </div>
          <p className="text-xs text-zinc-400">
            {selected.role} @ {selected.company}
          </p>

          <div className="mt-4 space-y-3">
            {/* Overall */}
            <div>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="text-zinc-400">Overall strength</span>
                <span className="font-bold text-indigo-400">
                  {selected.overall?.toFixed(2)}
                </span>
              </div>
              <div className="h-2 rounded-full bg-zinc-700">
                <div
                  className="h-2 rounded-full bg-indigo-500"
                  style={{ width: `${(selected.overall ?? 0) * 100}%` }}
                />
              </div>
            </div>

            {/* Dimensions */}
            {[
              { label: "Recency",       value: selected.recency,              weight: "25%" },
              { label: "Seniority",     value: selected.seniority,            weight: "25%" },
              { label: "Interactions",  value: selected.interaction_frequency, weight: "10%" },
              { label: "Src diversity", value: selected.source_diversity ? 1 : 0, weight: "20%" },
            ].map((b) => (
              <div key={b.label}>
                <div className="mb-1 flex items-center justify-between text-[11px]">
                  <span className="text-zinc-500">{b.label}</span>
                  <span className="text-zinc-400">{b.value?.toFixed(2)} <span className="text-zinc-600">({b.weight})</span></span>
                </div>
                <div className="h-1 rounded-full bg-zinc-700">
                  <div
                    className="h-1 rounded-full bg-zinc-400"
                    style={{ width: `${(b.value ?? 0) * 100}%` }}
                  />
                </div>
              </div>
            ))}

            {/* Interaction metadata */}
            {(selected.interaction_count > 0 || selected.last_touch) && (
              <div className="rounded-lg border border-zinc-700/60 bg-zinc-800/40 p-2.5 text-[11px] text-zinc-400 space-y-1">
                {selected.interaction_count > 0 && (
                  <p>
                    <span className="text-zinc-500">Interactions:</span>{" "}
                    <span className="text-zinc-200">{selected.interaction_count}</span>
                  </p>
                )}
                {selected.last_touch && (
                  <p>
                    <span className="text-zinc-500">Last touch:</span>{" "}
                    <span className="text-zinc-200">{selected.last_touch}</span>
                  </p>
                )}
                <p>
                  <span className="text-zinc-500">Shared connections:</span>{" "}
                  <span className="text-zinc-200">{selected.shared_connections}</span>
                </p>
              </div>
            )}

            {/* Known by */}
            {selected.known_by?.length > 0 && (
              <div>
                <p className="mb-1 text-[11px] font-medium text-zinc-400">Known by</p>
                <div className="flex flex-wrap gap-1">
                  {selected.known_by.map((name) => (
                    <span
                      key={name}
                      className="rounded-md bg-indigo-500/15 px-2 py-0.5 text-[10px] text-indigo-300"
                    >
                      {name}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

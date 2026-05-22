"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Loader2,
  Plus,
  Trash2,
  UserCheck,
  Users,
  X,
} from "lucide-react";
import api from "@/lib/api";
import { API_ROUTES } from "@/lib/constants";

interface ClientRelationship {
  id: string;
  organization_id: string;
  organization_name: string;
  organization_gstin: string;
  status: string;
  referral_commission_rate: string;
  created_at: string;
}

export default function CAClientsPage() {
  const [clients, setClients] = useState<ClientRelationship[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [gstin, setGstin] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState("");
  const [removingId, setRemovingId] = useState<string | null>(null);

  async function loadClients() {
    try {
      const r = await api.get(API_ROUTES.CA_FIRMS.CLIENTS);
      setClients(r.data.data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadClients();
  }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const g = gstin.trim().toUpperCase();
    if (g.length !== 15) {
      setAddError("GSTIN must be exactly 15 characters.");
      return;
    }
    setAdding(true);
    setAddError("");
    try {
      await api.post(API_ROUTES.CA_FIRMS.CLIENTS, {
        gstin: g,
        commission_rate: 0.15,
      });
      setShowAddModal(false);
      setGstin("");
      await loadClients();
    } catch (err: unknown) {
      setAddError(err instanceof Error ? err.message : "Failed to add client. Please try again.");
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(orgId: string) {
    if (!confirm("Remove this client from your firm?")) return;
    setRemovingId(orgId);
    try {
      await api.delete(API_ROUTES.CA_FIRMS.CLIENT(orgId));
      await loadClients();
    } catch {
      // ignore
    } finally {
      setRemovingId(null);
    }
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Client Management</h1>
          <p className="text-gray-500 text-sm mt-0.5">
            Add and manage client organisations in your CA firm portal
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 bg-blue-700 text-white font-semibold px-4 py-2.5 rounded-xl text-sm hover:bg-blue-800 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Client
        </button>
      </div>

      {/* Info */}
      <div className="bg-blue-50 border border-blue-100 rounded-2xl p-4 flex gap-3">
        <UserCheck className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
        <p className="text-xs text-blue-800 leading-relaxed">
          Add clients by their GSTIN. You will earn a referral commission on each subscription
          payment they make. Commission rates are configurable per client (default 15%).
        </p>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-blue-700 animate-spin" />
        </div>
      )}

      {!loading && clients.length === 0 && (
        <div className="bg-white border border-gray-100 rounded-2xl p-14 text-center shadow-sm">
          <Users className="w-14 h-14 text-gray-300 mx-auto mb-4" />
          <h2 className="text-lg font-bold text-gray-900 mb-2">No clients yet</h2>
          <p className="text-gray-500 text-sm max-w-sm mx-auto mb-6">
            Add client organisations by their GSTIN to start earning commissions.
          </p>
          <button
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center gap-2 bg-blue-700 text-white font-semibold px-5 py-2.5 rounded-xl text-sm hover:bg-blue-800 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Your First Client
          </button>
        </div>
      )}

      {!loading && clients.length > 0 && (
        <div className="bg-white border border-gray-100 rounded-2xl shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {["Organisation", "GSTIN", "Commission Rate", "Added On", "Actions"].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {clients.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900 text-sm">{c.organization_name}</div>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">
                    {c.organization_gstin}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-700">
                    {(parseFloat(c.referral_commission_rate) * 100).toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {new Date(c.created_at).toLocaleDateString("en-IN")}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Link
                        href={`/ca/clients/${c.organization_id}`}
                        className="text-xs font-semibold text-blue-700 hover:text-blue-800 transition-colors"
                      >
                        View
                      </Link>
                      <button
                        onClick={() => handleRemove(c.organization_id)}
                        disabled={removingId === c.organization_id}
                        className="p-1 text-gray-400 hover:text-red-600 disabled:opacity-40 transition-colors"
                      >
                        {removingId === c.organization_id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Client Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm px-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-900">Add Client Organisation</h2>
              <button
                onClick={() => { setShowAddModal(false); setAddError(""); setGstin(""); }}
                className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAdd} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-gray-700 block mb-1.5">
                  Client GSTIN
                </label>
                <input
                  type="text"
                  value={gstin}
                  onChange={(e) => {
                    setGstin(e.target.value.toUpperCase());
                    setAddError("");
                  }}
                  placeholder="e.g. 29ABCDE1234F1Z5"
                  maxLength={15}
                  className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {addError && <p className="text-xs text-red-600 font-medium">{addError}</p>}

              <button
                type="submit"
                disabled={adding}
                className="w-full flex items-center justify-center gap-2 bg-blue-700 text-white font-semibold py-2.5 rounded-xl text-sm hover:bg-blue-800 disabled:opacity-60 transition-colors"
              >
                {adding ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Adding...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" />
                    Add Client
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

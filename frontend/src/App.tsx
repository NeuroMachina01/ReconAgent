import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Link, useNavigate, useParams, useLocation } from 'react-router-dom';
import axios from 'axios';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Activity, ShieldCheck, Zap, Database, BrainCircuit, UploadCloud, CheckCircle2, AlertTriangle, BarChart3, Network, ChevronRight } from 'lucide-react';
import { motion } from 'framer-motion';
import { Receipt } from './components/Receipt';
import { Toaster, toast } from 'sonner';

const queryClient = new QueryClient();
const API_URL = "https://reconagent-5vr5.onrender.com";

const Layout = ({ children }: { children: React.ReactNode }) => {
  const location = useLocation();
  return (
    <div className="min-h-screen bg-[#0A0A0A] text-chalk font-sans selection:bg-signal selection:text-black flex flex-col">
      <header className="border-b border-ink/40 bg-black/50 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center space-x-3 group">
            <div className="w-8 h-8 rounded-none border border-signal flex items-center justify-center bg-signal/10 group-hover:bg-signal/20 transition-colors">
              <Zap size={16} className="text-signal" />
            </div>
            <span className="font-display text-xl tracking-tight text-white">RECON<span className="text-signal">AGENT</span></span>
          </Link>
          <nav className="flex space-x-8 font-mono text-xs uppercase tracking-widest text-chalk/60">
            <Link to="/" className={location.pathname === '/' ? "text-signal" : "hover:text-chalk"}>System Info</Link>
          </nav>
        </div>
      </header>
      <main className="flex-grow p-6 md:p-12 relative overflow-hidden">
        {/* Subtle background grid pattern */}
        <div className="absolute inset-0 pointer-events-none opacity-[0.03]" style={{ backgroundImage: 'linear-gradient(to right, #ffffff 1px, transparent 1px), linear-gradient(to bottom, #ffffff 1px, transparent 1px)', backgroundSize: '40px 40px' }}></div>
        <div className="max-w-7xl mx-auto relative z-10">
          {children}
        </div>
      </main>
      <footer className="border-t border-ink/40 bg-black p-6 font-mono text-xs text-chalk/40 text-center">
        RECON_AGENT // AUTONOMOUS FINANCIAL CONTROLLER // V1.0.0
      </footer>
    </div>
  );
};

const Home = () => {
  const navigate = useNavigate();
  const [pmtFile, setPmtFile] = useState<File | null>(null);
  const [invFile, setInvFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  
  const handleRun = async () => {
    if (!pmtFile || !invFile) return alert("Upload both JSON files");
    setLoading(true);
    const fd = new FormData();
    fd.append("payments_file", pmtFile);
    fd.append("invoices_file", invFile);
    try {
      const res = await axios.post(`${API_URL}/reconcile/batch`, fd);
      toast.success("Agent dispatched. Triage initiated.");
      navigate(`/job/${res.data.job_id}/live`);
    } catch (e: any) {
      alert("Error: " + e.message);
      toast.error("Failed to start batch.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid lg:grid-cols-2 gap-16 items-center">
      <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.8 }}>
        <div className="inline-flex items-center space-x-2 bg-signal/10 border border-signal/20 px-3 py-1 rounded-full mb-6">
          <span className="w-2 h-2 rounded-full bg-signal animate-pulse"></span>
          <span className="font-mono text-xs text-signal uppercase tracking-wider">Enterprise B2B Reconciliation</span>
        </div>
        
        <h1 className="text-5xl md:text-6xl font-display text-white mb-6 leading-tight">
          Resolve payments with <br/>
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-signal to-blue-400">Agentic Precision.</span>
        </h1>
        
        <p className="text-lg text-chalk/80 mb-10 leading-relaxed max-w-xl">
          ReconAgent is an autonomous financial controller that ingests dirty payment data, filters out the noise with deterministic rules, and unleashes a localized LLM agent to intelligently resolve garbled references, partial payments, and multi-invoice settlements.
        </p>

        <div className="bg-paper border border-ink/50 p-8 shadow-2xl relative overflow-hidden group">
          <div className="absolute top-0 left-0 w-1 h-full bg-signal"></div>
          <h2 className="font-mono text-sm mb-6 text-chalk/60 uppercase tracking-widest flex items-center">
            <UploadCloud size={16} className="mr-2" /> Start Reconciliation Batch
          </h2>
          <div className="space-y-4 font-mono text-sm">
            <div className="flex items-center space-x-4">
              <div className="w-1/3 text-chalk/80 text-right">PAYMENTS.JSON</div>
              <input type="file" className="w-2/3 bg-ink/30 border border-ink/50 p-2 text-chalk file:mr-4 file:py-1 file:px-3 file:border-0 file:bg-signal file:text-black file:font-bold hover:file:bg-signal/80 transition-colors" onChange={e => setPmtFile(e.target.files?.[0] || null)} />
            </div>
            <div className="flex items-center space-x-4">
              <div className="w-1/3 text-chalk/80 text-right">INVOICES.JSON</div>
              <input type="file" className="w-2/3 bg-ink/30 border border-ink/50 p-2 text-chalk file:mr-4 file:py-1 file:px-3 file:border-0 file:bg-signal file:text-black file:font-bold hover:file:bg-signal/80 transition-colors" onChange={e => setInvFile(e.target.files?.[0] || null)} />
            </div>
          </div>
          <button 
            onClick={handleRun}
            disabled={!pmtFile || !invFile || loading}
            className="w-full mt-8 bg-signal text-black font-display text-lg py-4 hover:bg-white transition-all disabled:opacity-50 disabled:hover:bg-signal flex items-center justify-center space-x-2"
          >
            <span>{loading ? "INITIALIZING AGENT..." : "EXECUTE BATCH"}</span>
            {!loading && <ChevronRight size={20} />}
          </button>
        </div>
      </motion.div>

      <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.8, delay: 0.2 }} className="relative">
        <div className="absolute inset-0 bg-gradient-to-tr from-signal/5 to-transparent blur-3xl pointer-events-none"></div>
        <div className="bg-[#111] border border-ink/40 p-8 relative z-10 space-y-8 font-mono shadow-2xl">
          <div className="text-center pb-6 border-b border-ink/30">
            <h3 className="text-white text-lg mb-2 flex items-center justify-center"><Network className="mr-2 text-signal" size={20}/> Agent Architecture</h3>
            <p className="text-xs text-chalk/50">Multi-Layer Triaging System</p>
          </div>

          <div className="relative space-y-6">
            <div className="absolute left-6 top-10 bottom-10 w-px bg-gradient-to-b from-signal/50 via-signal/20 to-alarm/50"></div>
            
            <div className="flex items-start space-x-6 relative z-10">
              <div className="w-12 h-12 bg-black border border-signal rounded-full flex items-center justify-center shrink-0">
                <Database size={20} className="text-signal" />
              </div>
              <div className="pt-2">
                <h4 className="text-signal font-bold mb-1">LAYER 0: Deterministic Rules</h4>
                <p className="text-xs text-chalk/60">Instantly clears ~90% of payments with exact amount & date matches. Zero AI cost.</p>
              </div>
            </div>

            <div className="flex items-start space-x-6 relative z-10">
              <div className="w-12 h-12 bg-black border border-blue-400 rounded-full flex items-center justify-center shrink-0">
                <BrainCircuit size={20} className="text-blue-400" />
              </div>
              <div className="pt-2">
                <h4 className="text-blue-400 font-bold mb-1">LAYER 1: Semantic Retrieval</h4>
                <p className="text-xs text-chalk/60">TF-IDF + fuzzy matching fetches the top 5 most likely invoice candidates for anomalies.</p>
              </div>
            </div>

            <div className="flex items-start space-x-6 relative z-10">
              <div className="w-12 h-12 bg-black border border-purple-400 rounded-full flex items-center justify-center shrink-0">
                <Activity size={20} className="text-purple-400" />
              </div>
              <div className="pt-2">
                <h4 className="text-purple-400 font-bold mb-1">LAYER 2: LLM Reasoning</h4>
                <p className="text-xs text-chalk/60">An autonomous agent analyzes candidates, extracts garbled context, and outputs a strict JSON decision.</p>
              </div>
            </div>

            <div className="flex items-start space-x-6 relative z-10">
              <div className="w-12 h-12 bg-black border border-alarm rounded-full flex items-center justify-center shrink-0">
                <AlertTriangle size={20} className="text-alarm" />
              </div>
              <div className="pt-2">
                <h4 className="text-alarm font-bold mb-1">LAYER 3: Human Escalation</h4>
                <p className="text-xs text-chalk/60">Irresolvable orphans or low-confidence matches are safely quarantined for human review.</p>
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

const LiveRun = () => {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const { data } = useQuery({
    queryKey: ['progress', jobId],
    queryFn: () => axios.get(`${API_URL}/reconcile/${jobId}/progress`).then(r => r.data),
    refetchInterval: (query) => query.state?.data?.status === 'completed' || query.state?.data?.status === 'error' ? false : 500,
  });

  const metrics = data?.metrics || {};
  const isDone = data?.status === 'completed';

  return (
    <div className="max-w-4xl mx-auto mt-12 fade-in">
       <div className="text-center mb-12">
          {isDone ? (
             <CheckCircle2 size={48} className="text-signal mx-auto mb-4" />
          ) : (
             <div className="inline-block relative">
               <div className="w-16 h-16 rounded-full border-2 border-ink/30 border-t-signal animate-spin mx-auto mb-4"></div>
               <BrainCircuit size={24} className="text-signal absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 -mt-2" />
             </div>
          )}
          <h2 className="text-4xl font-display text-white mb-2">
             {isDone ? "Batch Reconciliation Complete" : "Live Triage Processing..."}
          </h2>
          <p className="font-mono text-sm text-chalk/60">
             {isDone ? "All layers have finished processing." : "Streaming state directly from Autonomous Agent..."}
          </p>
       </div>

       {/* The Live Funnel */}
       <div className="flex flex-col items-center space-y-1 mb-16">
          {/* Layer 0 */}
          <motion.div 
             layout
             className="bg-[#00FF9D]/5 border-t border-[#00FF9D]/40 flex flex-col items-center justify-center py-6 relative"
             style={{ clipPath: 'polygon(0 0, 100% 0, 95% 100%, 5% 100%)', width: '100%', maxWidth: '600px', minHeight: '120px' }}
          >
             <div className="absolute inset-0 bg-gradient-to-b from-[#00FF9D]/10 to-transparent opacity-50"></div>
             <span className="font-mono text-xs text-[#00FF9D] uppercase tracking-widest mb-1 z-10">Layer 0: Deterministic Rules</span>
             <span className="text-5xl font-display text-white z-10">{metrics.layer0_matched || 0}</span>
             <span className="font-mono text-[10px] text-chalk/50 mt-1 z-10">CLEARED INSTANTLY</span>
          </motion.div>

          {/* Layer 1 & 2 */}
          <motion.div 
             layout
             className="bg-[#60A5FA]/5 border-t border-[#60A5FA]/40 flex flex-col items-center justify-center py-6 relative"
             style={{ clipPath: 'polygon(5% 0, 95% 0, 80% 100%, 20% 100%)', width: '100%', maxWidth: '600px', minHeight: '120px' }}
          >
             <div className="absolute inset-0 bg-gradient-to-b from-[#60A5FA]/10 to-transparent opacity-50"></div>
             <span className="font-mono text-xs text-[#60A5FA] uppercase tracking-widest mb-2 z-10">Layer 1 & 2: Agentic Resolution</span>
             <div className="flex space-x-12 text-center z-10">
                 <div>
                    <span className="text-4xl font-display text-white">{(metrics.layer1_for_llm || 0) - (metrics.layer2_resolved || 0) - (metrics.layer2_exceptions || 0)}</span>
                    <p className="font-mono text-[10px] text-chalk/50 mt-1">QUEUED FOR LLM</p>
                 </div>
                 <div>
                    <span className="text-4xl font-display text-white">{metrics.layer2_resolved || 0}</span>
                    <p className="font-mono text-[10px] text-chalk/50 mt-1">SOLVED BY LLM</p>
                 </div>
             </div>
          </motion.div>

          {/* Layer 3 / Exceptions */}
          <motion.div 
             layout
             className="bg-[#FF3366]/5 border-t border-b border-[#FF3366]/40 flex flex-col items-center justify-center py-6 relative"
             style={{ clipPath: 'polygon(20% 0, 80% 0, 70% 100%, 30% 100%)', width: '100%', maxWidth: '600px', minHeight: '100px' }}
          >
             <div className="absolute inset-0 bg-gradient-to-b from-[#FF3366]/10 to-transparent opacity-50"></div>
             <span className="font-mono text-xs text-[#FF3366] uppercase tracking-widest mb-1 z-10">Layer 3: Human Escalation</span>
             <span className="text-4xl font-display text-white z-10">{metrics.total_exceptions || metrics.layer2_exceptions || metrics.layer1_escalated || 0}</span>
             <span className="font-mono text-[10px] text-chalk/50 mt-1 z-10">QUARANTINED EXCEPTIONS</span>
          </motion.div>
       </div>

       {isDone && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="text-center">
             <button onClick={() => navigate(`/job/${jobId}/dashboard`)} className="bg-signal text-black font-display px-8 py-4 text-xl hover:bg-white transition-colors flex items-center justify-center mx-auto space-x-2">
                <span>VIEW FINAL REPORT</span>
                <ChevronRight size={24} />
             </button>
          </motion.div>
       )}
    </div>
  );
};

const DashboardTabs = ({ active, jobId }: { active: string, jobId: string }) => (
  <div className="flex space-x-1 border-b border-ink/50 mb-8 font-mono text-sm">
    <Link to={`/job/${jobId}/dashboard`} className={`px-6 py-3 border-b-2 ${active === 'overview' ? 'border-signal text-signal bg-signal/5' : 'border-transparent text-chalk/60 hover:text-white'}`}>
      OVERVIEW
    </Link>
    <Link to={`/job/${jobId}/transactions`} className={`px-6 py-3 border-b-2 ${active === 'transactions' ? 'border-signal text-signal bg-signal/5' : 'border-transparent text-chalk/60 hover:text-white'}`}>
      ALL TRANSACTIONS
    </Link>
    <Link to={`/job/${jobId}/evaluate`} className={`px-6 py-3 border-b-2 ${active === 'evaluate' ? 'border-signal text-signal bg-signal/5' : 'border-transparent text-chalk/60 hover:text-white'}`}>
      GROUND TRUTH EVAL
    </Link>
  </div>
);

const Dashboard = () => {
  const { jobId } = useParams();
  const { data: metricsReq } = useQuery({
    queryKey: ['metrics', jobId],
    queryFn: () => axios.get(`${API_URL}/reconcile/${jobId}/metrics`).then(r => r.data)
  });
  
  const metrics = metricsReq?.metrics;
  if (!metrics) return <div className="text-center font-mono py-20 animate-pulse">LOADING DASHBOARD...</div>;

  const total = metrics.total_reconciled + metrics.total_exceptions;
  
  const pieData = [
    { name: 'Layer 0 (Rules)', value: metrics.layer0_matched || 0, color: '#00FF9D' },
    { name: 'Layer 2 (LLM)', value: metrics.layer2_resolved || 0, color: '#60A5FA' },
    { name: 'Escalated', value: metrics.total_exceptions || 0, color: '#FF3366' }
  ].filter(d => d.value > 0);

  return (
    <div className="max-w-6xl mx-auto fade-in">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-4xl font-display text-white mb-2">Reconciliation Report</h1>
          <p className="font-mono text-sm text-chalk/60">JOB_ID: {jobId}</p>
        </div>
        <Link to={`/job/${jobId}/exceptions`} className="bg-alarm/10 border border-alarm/30 text-alarm font-mono text-sm py-2 px-4 hover:bg-alarm hover:text-white transition-colors flex items-center">
          <AlertTriangle size={16} className="mr-2" />
          VIEW ESCALATIONS ({metrics.total_exceptions})
        </Link>
      </div>
      
      <DashboardTabs active="overview" jobId={jobId!} />
      
      <div className="grid md:grid-cols-2 gap-8">
        <div className="bg-paper border border-ink/50 p-8 relative">
          <h2 className="text-xl font-display mb-6 border-b border-ink/30 pb-4 flex items-center">
            <BarChart3 size={20} className="mr-2 text-signal" /> Resolution by Layer
          </h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0A0A0A', borderColor: '#2A2A2A', fontFamily: 'monospace', fontSize: '12px' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{ fontFamily: 'monospace', fontSize: '12px' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-paper border border-ink/50 p-8 flex flex-col justify-center">
          <h2 className="text-xl font-display mb-8 border-b border-ink/30 pb-4">Key Metrics</h2>
          <div className="grid grid-cols-2 gap-8">
            <div>
              <p className="font-mono text-xs text-chalk/50 mb-1">TOTAL PROCESSED</p>
              <p className="text-4xl font-display text-white">{total}</p>
            </div>
            <div>
              <p className="font-mono text-xs text-chalk/50 mb-1">AUTONOMOUS MATCH RATE</p>
              <p className="text-4xl font-display text-signal">
                {((metrics.total_reconciled / total) * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <p className="font-mono text-xs text-chalk/50 mb-1">L0 DETERMINISTIC</p>
              <p className="text-2xl font-mono text-white">{metrics.layer0_matched}</p>
            </div>
            <div>
              <p className="font-mono text-xs text-chalk/50 mb-1">L2 AI RESOLVED</p>
              <p className="text-2xl font-mono text-white">{metrics.layer2_resolved}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const Transactions = () => {
  const { jobId } = useParams();
  const { data: resultsReq } = useQuery({
    queryKey: ['results', jobId],
    queryFn: () => axios.get(`${API_URL}/reconcile/${jobId}/results`).then(r => r.data)
  });
  
  const results = resultsReq?.results || [];

  return (
    <div className="max-w-6xl mx-auto fade-in">
      <div className="mb-8">
        <h1 className="text-4xl font-display text-white mb-2">Reconciliation Report</h1>
        <p className="font-mono text-sm text-chalk/60">JOB_ID: {jobId}</p>
      </div>
      <DashboardTabs active="transactions" jobId={jobId!} />
      
      <div className="bg-paper border border-ink/50 overflow-hidden">
        <table className="w-full text-left font-mono text-sm">
          <thead className="bg-ink/30 text-chalk/60 border-b border-ink/50">
            <tr>
              <th className="p-4 font-normal">PAYMENT ID</th>
              <th className="p-4 font-normal">INVOICE IDS</th>
              <th className="p-4 font-normal">LAYER</th>
              <th className="p-4 font-normal">DECISION</th>
              <th className="p-4 font-normal">CONF</th>
              <th className="p-4 font-normal text-right">TRACE</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink/20">
            {results.map((r: any) => (
              <tr key={r.payment_id} className="hover:bg-ink/10 transition-colors">
                <td className="p-4 text-white">{r.payment_id}</td>
                <td className="p-4 text-chalk/80">{r.invoice_ids?.join(', ') || 'NONE'}</td>
                <td className="p-4">
                  {r.method === 'deterministic' ? (
                    <span className="text-signal bg-signal/10 px-2 py-1">L0</span>
                  ) : r.method === 'llm_reasoning' ? (
                    <span className="text-blue-400 bg-blue-400/10 px-2 py-1">L2</span>
                  ) : (
                    <span className="text-alarm bg-alarm/10 px-2 py-1">ESCALATED</span>
                  )}
                </td>
                <td className="p-4 font-bold">{r.decision}</td>
                <td className="p-4">{r.confidence ? r.confidence.toFixed(2) : '-'}</td>
                <td className="p-4 text-right">
                  <Link to={`/job/${jobId}/trace/${r.payment_id}`} className="text-signal hover:underline">VIEW &rarr;</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const EvaluateTab = () => {
  const { jobId } = useParams();
  const [file, setFile] = useState<File | null>(null);
  const [evalData, setEvalData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleEvaluate = async () => {
    if (!file) return;
    setLoading(true);
    setError("");
    const fd = new FormData();
    fd.append("ground_truth_file", file);
    try {
      const res = await axios.post(`${API_URL}/reconcile/${jobId}/evaluate`, fd);
      setEvalData(res.data);
      toast.success(`Evaluation Complete: ${(res.data.precision * 100).toFixed(1)}% Precision!`);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message);
      toast.error("Evaluation Failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto fade-in">
      <div className="mb-8">
        <h1 className="text-4xl font-display text-white mb-2">Reconciliation Report</h1>
        <p className="font-mono text-sm text-chalk/60">JOB_ID: {jobId}</p>
      </div>
      <DashboardTabs active="evaluate" jobId={jobId!} />
      
      {!evalData && (
        <div className="bg-paper border border-ink/50 p-8 max-w-xl text-center mx-auto">
          <ShieldCheck size={48} className="mx-auto text-signal mb-6 opacity-50" />
          <h2 className="text-2xl font-display mb-4">Validate Accuracy</h2>
          <p className="font-mono text-sm text-chalk/60 mb-8">Upload a ground truth JSON file to compute precision, recall, and a detailed confusion matrix against the autonomous agent's output.</p>
          
          <input type="file" className="block w-full text-sm text-chalk/60 file:mr-4 file:py-2 file:px-4 file:rounded-none file:border-0 file:text-sm file:font-mono file:bg-ink file:text-white hover:file:bg-ink/80 mb-6 mx-auto cursor-pointer" onChange={e => setFile(e.target.files?.[0] || null)} />
          
          <button 
            onClick={handleEvaluate}
            disabled={!file || loading}
            className="bg-signal text-black font-display px-8 py-3 w-full hover:bg-white transition-colors disabled:opacity-50"
          >
            {loading ? "EVALUATING..." : "RUN EVALUATION"}
          </button>
          
          {error && <p className="text-alarm font-mono text-sm mt-4">{error}</p>}
        </div>
      )}

      {evalData && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">
          <div className="grid grid-cols-2 gap-8">
            <div className="bg-paper border border-ink/50 p-6 flex flex-col justify-center items-center">
              <p className="font-mono text-sm text-chalk/60 mb-2">PRECISION (ACCURACY)</p>
              <p className="text-6xl font-display text-signal">{(evalData.precision * 100).toFixed(1)}%</p>
              <p className="font-mono text-xs text-chalk/40 mt-4 text-center">Percentage of autonomous matches that were perfectly correct.</p>
            </div>
            <div className="bg-paper border border-ink/50 p-6 flex flex-col justify-center items-center">
              <p className="font-mono text-sm text-chalk/60 mb-2">RECALL (AUTOMATION RATE)</p>
              <p className="text-6xl font-display text-blue-400">{(evalData.recall * 100).toFixed(1)}%</p>
              <p className="font-mono text-xs text-chalk/40 mt-4 text-center">Percentage of edge cases the agent successfully resolved.</p>
            </div>
          </div>

          <div className="bg-paper border border-ink/50 p-8 overflow-x-auto">
            <h3 className="text-xl font-display mb-6 border-b border-ink/30 pb-4">Confusion Matrix</h3>
            <table className="w-full text-left font-mono text-sm">
              <thead className="bg-ink/30 text-chalk/60">
                <tr>
                  <th className="p-4 font-normal">ACTUAL CATEGORY</th>
                  <th className="p-4 font-normal">MATCH</th>
                  <th className="p-4 font-normal">PARTIAL</th>
                  <th className="p-4 font-normal">MULTI</th>
                  <th className="p-4 font-normal">ESCALATE</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink/20">
                {["exact", "orphan", "partial", "multi", "garbled_ref", "timing_offset", "currency_rounding"].map(cat => {
                   const row = evalData.confusion[cat] || {};
                   const hasData = row["MATCH"] || row["PARTIAL_MATCH"] || row["MULTI_MATCH"] || row["ESCALATE"];
                   if (!hasData) return null;
                   return (
                     <tr key={cat} className="hover:bg-ink/10 transition-colors">
                       <td className="p-4 text-white uppercase">{cat.replace('_', ' ')}</td>
                       <td className="p-4">{row["MATCH"] || 0}</td>
                       <td className="p-4">{row["PARTIAL_MATCH"] || 0}</td>
                       <td className="p-4">{row["MULTI_MATCH"] || 0}</td>
                       <td className="p-4 text-alarm font-bold">{row["ESCALATE"] || 0}</td>
                     </tr>
                   );
                })}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}
    </div>
  );
};

const Exceptions = () => {
  const { jobId } = useParams();
  const { data: resultsReq } = useQuery({
    queryKey: ['results', jobId],
    queryFn: () => axios.get(`${API_URL}/reconcile/${jobId}/results`).then(r => r.data)
  });
  
  const exceptions = (resultsReq?.results || []).filter((r: any) => r.status === 'exception' || r.decision === 'ESCALATE');
  
  return (
    <div className="max-w-6xl mx-auto">
      <Link to={`/job/${jobId}/dashboard`} className="text-signal hover:underline font-mono text-sm mb-6 inline-block">{"<-"} BACK TO DASHBOARD</Link>
      <h1 className="text-3xl font-display text-white mb-8 text-alarm">Escalations Queue</h1>
      
      <div className="bg-paper border border-alarm/30 overflow-hidden">
        <table className="w-full text-left font-mono text-sm">
          <thead className="bg-alarm/10 text-alarm">
            <tr>
              <th className="p-4 font-normal">PAYMENT ID</th>
              <th className="p-4 font-normal">CONFIDENCE</th>
              <th className="p-4 font-normal">METHOD</th>
              <th className="p-4 font-normal text-right">ACTION</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink/30">
            {exceptions.map((e: any) => (
              <tr key={e.payment_id} className="hover:bg-ink/20">
                <td className="p-4 text-white">{e.payment_id}</td>
                <td className="p-4 text-alarm">{(e.confidence || 0).toFixed(2)}</td>
                <td className="p-4 text-chalk/60">{e.method}</td>
                <td className="p-4 text-right">
                  <Link to={`/job/${jobId}/trace/${e.payment_id}`} className="text-signal hover:underline">VIEW RECEIPT</Link>
                </td>
              </tr>
            ))}
            {exceptions.length === 0 && (
              <tr><td colSpan={4} className="p-8 text-center text-chalk/40">No exceptions found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const Trace = () => {
  const { jobId, paymentId } = useParams();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['trace', jobId, paymentId],
    queryFn: () => axios.get(`${API_URL}/reconcile/${jobId}/trace/${paymentId}`).then(r => r.data)
  });

  if (isLoading) return <div className="font-mono text-center mt-20 text-signal animate-pulse">DECRYPTING RECEIPT...</div>;
  if (isError) return <div className="font-mono text-center mt-20 text-alarm">TRACE CORRUPTED / NOT FOUND</div>;

  return (
    <div className="max-w-4xl mx-auto fade-in">
      <Link to={-1 as any} className="text-signal hover:underline font-mono text-sm mb-6 inline-block flex items-center">
        <ChevronRight className="rotate-180 mr-1" size={16}/> BACK
      </Link>
      <Receipt trace={data} />
    </div>
  );
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Toaster theme="dark" position="bottom-right" />
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/job/:jobId/live" element={<LiveRun />} />
            <Route path="/job/:jobId/dashboard" element={<Dashboard />} />
            <Route path="/job/:jobId/transactions" element={<Transactions />} />
            <Route path="/job/:jobId/evaluate" element={<EvaluateTab />} />
            <Route path="/job/:jobId/exceptions" element={<Exceptions />} />
            <Route path="/job/:jobId/trace/:paymentId" element={<Trace />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;

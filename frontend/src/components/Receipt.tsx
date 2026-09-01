

export const Receipt = ({ trace }: { trace: any }) => {
  if (!trace) return null;
  
  return (
    <div className="max-w-md mx-auto w-full filter drop-shadow-md my-8">
      <div className="bg-paper p-6 pb-12 font-mono text-sm relative text-chalk">
        
        {/* Header */}
        <div className="text-center mb-6 border-b border-ink/50 pb-4">
          <div className="text-lg font-bold">RECON_AGENT // TRACE</div>
          <div className="text-xs text-chalk/60 mt-1">
            PMT_ID: {trace.trace?.payment_id}
          </div>
          <div className="text-xs text-chalk/60">
            TS: {trace.trace?.timestamp || new Date().toISOString()}
          </div>
        </div>
        
        {/* Itemized section */}
        <div className="space-y-4">
          <div className="flex justify-between border-b border-ink/50 pb-2">
            <span className="text-chalk/60">DECISION</span>
            <span className={trace.trace?.decision === "MATCH" ? "text-ledger" : trace.trace?.decision === "PARTIAL_MATCH" ? "text-flag" : "text-alarm"}>
              {trace.trace?.decision || "ESCALATE"}
            </span>
          </div>
          
          <div className="flex justify-between border-b border-ink/50 pb-2">
            <span className="text-chalk/60">CONFIDENCE</span>
            <span>{(trace.trace?.confidence || 0).toFixed(2)}</span>
          </div>
          
          <div className="flex justify-between border-b border-ink/50 pb-2">
            <span className="text-chalk/60">LAYER</span>
            <span>{trace.method}</span>
          </div>
          
          <div className="flex justify-between border-b border-ink/50 pb-2">
            <span className="text-chalk/60">INVOICE_IDS</span>
            <span>{(trace.trace?.invoice_ids || []).join(', ') || 'NONE'}</span>
          </div>
          
          {trace.candidates_shown && (
            <div className="border-b border-ink/50 pb-2">
              <span className="text-chalk/60 block mb-1">CANDIDATES_SHOWN</span>
              <div className="pl-4 border-l border-ink/50 space-y-1">
                {trace.candidates_shown.slice(0, 3).map((c: any) => (
                  <div key={c.invoice_id} className="flex justify-between text-xs">
                    <span>{c.invoice_id}</span>
                    <span className="text-chalk/40">rrf:{c.rrf_score?.toFixed(3)} d_amt:{c.amount_delta}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          <div className="pt-2">
            <span className="text-chalk/60 block mb-2">REASONING_LOG</span>
            <div className="bg-ink/30 p-3 text-xs leading-relaxed border-l-2 border-signal">
              {trace.trace?.reasoning || "N/A"}
            </div>
          </div>
        </div>
      </div>
      
      {/* Tear edge */}
      <div className="h-6 w-full bg-transparent" style={{
        backgroundImage: 'radial-gradient(circle at 10px 10px, transparent 10px, #121B2E 11px)',
        backgroundSize: '20px 20px',
        backgroundPosition: '-10px -10px',
        marginTop: '-1px'
      }} />
    </div>
  );
};

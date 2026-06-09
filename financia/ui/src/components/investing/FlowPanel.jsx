import { useState } from 'react';
import FlowSteps, { FLOW_META } from './FlowSteps';

// Side window shown next to a stock's report, holding the buy or sell flow.
export default function FlowPanel({ flow, onClose }) {
  const [openId, setOpenId] = useState(null);
  const meta = FLOW_META[flow];

  return (
    <div
      className="bg-gray-900 border border-gray-700 rounded-xl w-full md:w-[380px] md:shrink-0 max-h-[92vh] overflow-y-auto"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between p-3 border-b border-gray-800 sticky top-0 bg-gray-900 z-10">
        <h2 className="text-base font-bold text-white">{meta?.label || 'Akış'}</h2>
        <button onClick={onClose} className="text-red-400 hover:text-red-300 text-xl px-2" title="Akışı kapat">✕</button>
      </div>
      <div className="p-3">
        <FlowSteps flow={flow} openId={openId} setOpenId={setOpenId} />
      </div>
    </div>
  );
}

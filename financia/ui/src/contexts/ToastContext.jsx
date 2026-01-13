import React, { createContext, useContext, useState, useCallback } from 'react';
import { X, CheckCircle, AlertTriangle, Info, AlertOctagon } from 'lucide-react';

const ToastContext = createContext(null);

export const useToast = () => useContext(ToastContext);

export const ToastProvider = ({ children }) => {
    const [toasts, setToasts] = useState([]);

    const addToast = useCallback((message, type = 'info', duration = 4000) => {
        const id = Date.now() + Math.random();
        setToasts(prev => [...prev, { id, message, type, duration }]);

        if (duration > 0) {
            setTimeout(() => {
                removeToast(id);
            }, duration);
        }
    }, []);

    const removeToast = useCallback((id) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    return (
        <ToastContext.Provider value={{ addToast, removeToast }}>
            {children}
            <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-3 w-full max-w-sm pointer-events-none">
                {toasts.map(toast => (
                    <div
                        key={toast.id}
                        className={`
                            pointer-events-auto transform transition-all duration-300 ease-out animate-slide-in-right
                            flex items-start gap-3 p-4 rounded-xl shadow-2xl backdrop-blur-md border
                            ${toast.type === 'success' ? 'bg-green-900/90 border-green-500/30 text-green-100' : ''}
                            ${toast.type === 'error' ? 'bg-red-900/90 border-red-500/30 text-red-100' : ''}
                            ${toast.type === 'warning' ? 'bg-yellow-900/90 border-yellow-500/30 text-yellow-100' : ''}
                            ${toast.type === 'info' ? 'bg-gray-800/90 border-gray-600/30 text-gray-100' : ''}
                        `}
                    >
                        <div className="mt-0.5 shrink-0">
                            {toast.type === 'success' && <CheckCircle size={20} className="text-green-400" />}
                            {toast.type === 'error' && <AlertOctagon size={20} className="text-red-400" />}
                            {toast.type === 'warning' && <AlertTriangle size={20} className="text-yellow-400" />}
                            {toast.type === 'info' && <Info size={20} className="text-blue-400" />}
                        </div>
                        <div className="flex-1 text-sm font-medium leading-relaxed">
                            {toast.message}
                        </div>
                        <button
                            onClick={() => removeToast(toast.id)}
                            className="shrink-0 opacity-50 hover:opacity-100 transition-opacity p-0.5"
                        >
                            <X size={16} />
                        </button>
                    </div>
                ))}
            </div>
        </ToastContext.Provider>
    );
};

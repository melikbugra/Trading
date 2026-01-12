import { useState } from 'react';
import { Lock } from 'lucide-react';

export default function PinLogin({ onLogin }) {
    const [pin, setPin] = useState("");
    const [error, setError] = useState(false);

    // Default PIN is 1234 if not set in environment
    const CORRECT_PIN = import.meta.env.VITE_APP_PIN || "1234";

    const handleSubmit = (e) => {
        e.preventDefault();
        if (pin === CORRECT_PIN) {
            onLogin();
            localStorage.setItem("auth_token", "valid"); // Simple session persistence
        } else {
            setError(true);
            setPin("");
            setTimeout(() => setError(false), 2000);
        }
    };

    return (
        <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center p-4">
            <div className="bg-gray-900 border border-gray-800 p-8 rounded-2xl shadow-2xl w-full max-w-sm text-center">
                <div className="mx-auto w-16 h-16 bg-blue-900/30 rounded-full flex items-center justify-center mb-6">
                    <Lock size={32} className="text-blue-400" />
                </div>

                <h2 className="text-2xl font-bold text-white mb-2">Giriş Yapın</h2>
                <p className="text-gray-500 text-sm mb-6">Panele erişmek için erişim kodunu girin.</p>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <input
                        type="password"
                        value={pin}
                        onChange={(e) => setPin(e.target.value)}
                        className={`w-full bg-black/50 border ${error ? 'border-red-500' : 'border-gray-700 focus:border-blue-500'} rounded-xl px-4 py-3 text-white text-center text-2xl tracking-[0.5em] outline-none transition-all`}
                        placeholder="••••"
                        maxLength={6}
                        autoFocus
                    />

                    {error && (
                        <div className="text-red-400 text-xs font-medium animate-pulse">
                            Hatalı PIN. Tekrar deneyin.
                        </div>
                    )}

                    <button
                        type="submit"
                        className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-bold py-3 rounded-xl transition-all active:scale-95"
                    >
                        GİRİŞ
                    </button>

                    <div className="text-xs text-gray-700 mt-4">
                        Varsayılan PIN: 1234
                    </div>
                </form>
            </div>
        </div>
    );
}

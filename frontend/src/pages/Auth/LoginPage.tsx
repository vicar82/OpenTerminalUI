import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../../contexts/AuthContext";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { login, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email.includes("@")) {
      setError("Введите корректный email");
      return;
    }
    if (password.length < 8) {
      setError("Пароль должен быть не менее 8 символов");
      return;
    }
    try {
      await login(email, password);
      const redirectParam = new URLSearchParams(location.search).get("redirect");
      const target = redirectParam || (location.state as { from?: string } | undefined)?.from || "/equity/stocks";
      navigate(target, { replace: true });
    } catch {
      setError("Неверные учётные данные");
    }
  };

  return (
    <div className="mx-auto mt-16 max-w-md rounded border border-terminal-border bg-terminal-panel p-5">
      <h1 className="mb-4 text-lg font-semibold text-terminal-accent">Вход</h1>
      <form className="space-y-3" onSubmit={onSubmit}>
        <input className="w-full rounded border border-terminal-border bg-terminal-bg px-3 py-2 text-sm" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="w-full rounded border border-terminal-border bg-terminal-bg px-3 py-2 text-sm" placeholder="Пароль" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {error ? <div className="text-xs text-terminal-neg">{error}</div> : null}
        <button disabled={isLoading} className="w-full rounded border border-terminal-accent px-3 py-2 text-sm text-terminal-accent disabled:opacity-60">
          {isLoading ? "Вход..." : "Войти"}
        </button>
      </form>
      <div className="mt-3 text-xs text-terminal-muted">
        Нет аккаунта? <Link className="text-terminal-accent underline" to="/register">Зарегистрироваться</Link>
      </div>
    </div>
  );
}

import { useState } from "react";
import { useLocation } from "wouter";
import { Loader2 } from "lucide-react";
import { verifyToken } from "../utils/api-client";
import { storage } from "../utils/storage";
import { useTitle } from "../hooks/use-title";
import "./login.css";

export default function Login() {
  const [token, setToken] = useState(storage.get("auth-token") || "");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [, setLocation] = useLocation();

  useTitle("Login");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token.trim()) {
      setError("Please enter your Authorization Key");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const isValid = await verifyToken(token.trim());
      if (isValid) {
        storage.set("auth-token", token.trim());
        setLocation("/dashboard");
      } else {
        setError("Invalid Authorization Key");
      }
    } catch {
      setError("Verification failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <h1>Twilight</h1>
          <p>A Himawari Satellite Data Visualization System</p>
        </div>
        <form onSubmit={handleSubmit} className="login-form">
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Authorization Key"
            autoFocus
          />
          <button type="submit" className="login-button" disabled={isLoading}>
            {isLoading ? <Loader2 size={16} className="animate-spin" /> : "Continue"}
          </button>
          <div className="error-row">
            {error && <span className="login-error">{error}</span>}
          </div>
        </form>
      </div>
    </main>
  );
}